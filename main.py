import asyncio
import logging
import os
import re
import tempfile
import uuid
from contextlib import asynccontextmanager
from datetime import date as date_type, time as time_type
from pathlib import Path

import mercadopago
import requests
from fastapi import BackgroundTasks, FastAPI, HTTPException, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, EmailStr, field_validator

from email_engine import EmailEngineError, send_admin_alert_email, send_report_email
from natal_engine import (
    EphemerisCalculationError,
    GeocodingTimeoutError,
    InvalidDateTimeError,
    InvalidHouseSystemError,
    LocationNotFoundError,
    MissingBirthTimeError,
    generate_natal_chart,
)
from pdf_engine import PDFExportError, generate_pdf
from report_engine import (
    LLMGenerationError,
    LLMRefusalError,
    MissingAPIKeyError,
    generate_report,
)
from teaser_copy import build_teaser

logger = logging.getLogger("siderea.webhook")

# REPORTS_DIR es la cola transaccional persistente (.pending/.lock/.done) --
# ver _claim_payment/_fulfill_payment/_recover_pending_payments. Configurable
# vía env var a propósito: el default (una carpeta relativa al código) vive
# en el disco EFÍMERO de un servicio web de Render -- se borra en cada
# redeploy y no está garantizado que sobreviva un restart de infraestructura.
# Sin un disco persistente de Render montado y REPORTS_DIR apuntando ahí,
# esta cola no cumple "cero pérdida de transacciones ante reinicios
# abruptos": la recuperación al arrancar escanearía un disco nuevo y vacío,
# sin encontrar nada que recuperar -- fallaría en silencio, dando falsa
# confianza. Ver el resumen de esta entrega para el detalle.
REPORTS_DIR = Path(os.environ.get("REPORTS_DIR", str(Path(__file__).resolve().parent / "generated_reports")))
REPORTS_DIR.mkdir(exist_ok=True, parents=True)

_PENDING_PAYMENT_ID_RE = re.compile(r"^webhook-(\d+)\.pending$")


def _find_recoverable_payment_ids() -> list[str]:
    """Escanea REPORTS_DIR por transacciones interrumpidas (.pending sin .done).

    Función pura y testeable a propósito, separada de _recover_pending_payments
    (que además agenda las tareas de fondo, algo que solo tiene sentido
    correr dentro del lifespan real de la app).

    Por cada .pending encontrado, si también hay un .lock para el mismo
    payment_id, se lo borra antes de devolver ese payment_id -- esta función
    corre durante el arranque, ANTES de que el server acepte tráfico, así
    que para una única instancia (el caso por default salvo que se escale
    horizontalmente) cualquier .lock que quede en este momento es de un
    proceso anterior que ya está muerto, nunca de un trabajo legítimamente
    en curso.

    ADVERTENCIA de alcance: con múltiples instancias/workers corriendo en
    paralelo sobre el mismo disco compartido, esta asunción no se sostiene
    -- un .lock podría pertenecer a un proceso hermano todavía vivo. Ese
    escenario necesita un lock real con expiración (o un broker externo),
    no archivos locales; no está resuelto acá.
    """
    payment_ids = []
    for pending_path in sorted(REPORTS_DIR.glob("webhook-*.pending")):
        match = _PENDING_PAYMENT_ID_RE.match(pending_path.name)
        if not match:
            logger.warning("Archivo .pending con nombre inesperado, se ignora: %s", pending_path.name)
            continue

        payment_id = match.group(1)

        stale_lock = REPORTS_DIR / f"webhook-{payment_id}.lock"
        if stale_lock.exists():
            logger.warning(
                "payment_id=%s tenía un .lock de un proceso anterior interrumpido; "
                "se limpia antes de reintentar.", payment_id,
            )
            try:
                stale_lock.unlink()
            except OSError:
                pass

        payment_ids.append(payment_id)

    return payment_ids


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Rutina de resurrección: reencola al arrancar cualquier pago que haya
    quedado en .pending de un proceso anterior interrumpido (deploy, OOM,
    restart de infraestructura) antes de terminar -- así ese pago no se
    pierde para siempre solo porque Mercado Pago ya recibió su 200 OK y
    nunca va a reintentar la notificación.
    """
    payment_ids = _find_recoverable_payment_ids()
    if payment_ids:
        logger.warning(
            "Recuperación de arranque: %d pago(s) quedaron interrumpidos. Reencolando: %s",
            len(payment_ids), payment_ids,
        )
        # Referencia obligatoria: un asyncio.Task sin nada que lo referencie
        # puede ser recolectado por el garbage collector a mitad de camino
        # ("Task was destroyed but it is pending"). app.state vive mientras
        # vive la app, así que ancla las tareas hasta que terminen solas.
        app.state.recovery_tasks = [
            asyncio.create_task(run_in_threadpool(_fulfill_payment, payment_id))
            for payment_id in payment_ids
        ]
    yield


app = FastAPI(title="Sidérea", lifespan=lifespan)

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

_REPORT_ID_RE = re.compile(r"^[0-9a-f]{32}$")

_FIELD_LABELS = {
    "date": "la fecha de nacimiento",
    "time": "la hora exacta",
    "location": "el lugar de nacimiento",
    "email": "el email",
}

# Precio de referencia del informe completo. Vive acá (no hardcodeado en el
# payload de Mercado Pago) para que el día que haya un solo lugar que
# cambiar sea este. Valor de prueba -- ajustar antes de lanzar.
FULL_REPORT_PRICE_ARS = 1000.00
FULL_REPORT_TITLE = "Sidérea - Lectura Óptica Integral"

_mp_sdk: mercadopago.SDK | None = None


def _claim_payment(payment_id: str) -> bool:
    """Reclama atómicamente un payment_id para su procesamiento.

    Usa creación exclusiva de archivo (Path.touch(exist_ok=False), que
    internamente es open() con O_EXCL) como primitiva atómica real a nivel
    de sistema operativo -- a diferencia de un "if not exists(): create()",
    que tiene una ventana de carrera entre el chequeo y la creación donde
    dos llamadas concurrentes pueden pasar las dos, esto no puede ser
    ganado por más de una a la vez: el sistema operativo garantiza que como
    mucho una sola creación exclusiva tiene éxito.

    Devuelve True si ESTA llamada reclamó el pago (nadie lo tenía reclamado
    todavía); False si ya estaba reclamado -- una entrega duplicada de
    Mercado Pago llegó primero (incluso en otro worker/proceso, si
    comparten disco) o ya está completamente entregado.
    """
    done_path = REPORTS_DIR / f"webhook-{payment_id}.done"
    if done_path.exists():
        return False

    pending_path = REPORTS_DIR / f"webhook-{payment_id}.pending"
    try:
        pending_path.touch(exist_ok=False)
        return True
    except FileExistsError:
        return False


def _get_mp_sdk() -> mercadopago.SDK:
    """Construye el SDK de Mercado Pago de forma perezosa.

    Perezosa a propósito: si se instanciara a nivel de módulo, un servidor
    sin MERCADOPAGO_ACCESS_TOKEN configurada (dev local, tests) no podría ni
    arrancar. Así, el resto de la app funciona igual y el error queda
    acotado a este endpoint.
    """
    global _mp_sdk
    if _mp_sdk is None:
        access_token = os.environ.get("MERCADOPAGO_ACCESS_TOKEN")
        if not access_token:
            raise HTTPException(
                status_code=500,
                detail="La pasarela de pago no está configurada (falta MERCADOPAGO_ACCESS_TOKEN).",
            )
        _mp_sdk = mercadopago.SDK(access_token)
    return _mp_sdk


class ChartRequest(BaseModel):
    date: date_type
    time: time_type
    location: str
    email: EmailStr

    @field_validator("location")
    @classmethod
    def location_not_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("El lugar de nacimiento no puede estar vacío.")
        return value


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    messages = []
    for error in exc.errors():
        field = error["loc"][-1] if error["loc"] else None
        label = _FIELD_LABELS.get(field, str(field))
        messages.append(f"Revisá {label}: el formato no es válido.")
    detail = " ".join(messages) if messages else "Los datos enviados no son válidos."
    return JSONResponse(status_code=422, content={"detail": detail})


def _raise_for_natal_error(exc: Exception) -> None:
    """Mapea las excepciones de natal_engine a una respuesta HTTP clara."""
    if isinstance(
        exc,
        (
            LocationNotFoundError,
            MissingBirthTimeError,
            InvalidHouseSystemError,
            InvalidDateTimeError,
        ),
    ):
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if isinstance(exc, (GeocodingTimeoutError, EphemerisCalculationError)):
        raise HTTPException(
            status_code=502, detail=f"No pudimos calcular tu carta: {exc}"
        ) from exc
    raise HTTPException(
        status_code=500, detail="Ocurrió un error inesperado procesando tu carta."
    ) from exc


@app.get("/")
async def read_index(request: Request):
    return templates.TemplateResponse(request, "index.html")


@app.post("/api/calculate")
async def calculate(payload: ChartRequest):
    """Vista previa gratuita: solo natal_engine (rápido, sin costo de LLM).

    Devuelve un "extracto óptico" — Sol, Ascendente y una frase fija de
    arquitectura de aura — como destello de valor antes de ofrecer el
    informe completo pago. No llama a report_engine ni a pdf_engine.
    """
    date_str = payload.date.isoformat()
    time_str = payload.time.strftime("%H:%M")

    try:
        chart = await run_in_threadpool(
            generate_natal_chart,
            name="Consultante",
            date_str=date_str,
            time_str=time_str,
            place_text=payload.location,
        )
    except Exception as exc:
        _raise_for_natal_error(exc)

    return {
        "subject": chart["subject"],
        "teaser": build_teaser(chart),
        "full_report_price_ars": FULL_REPORT_PRICE_ARS,
    }


@app.post("/api/generate-report")
async def generate_report_endpoint(payload: ChartRequest):
    """Informe completo (LLM + PDF): reservado para después del pago.

    Todavía no está gateado por una confirmación de pago real — eso llega
    con el webhook de Mercado Pago (ver /api/create-preference) — pero
    vive en su propio endpoint, separado de la vista previa gratuita, para
    que ese enganche sea un solo punto de cambio cuando se implemente.
    """
    date_str = payload.date.isoformat()
    time_str = payload.time.strftime("%H:%M")

    try:
        chart = await run_in_threadpool(
            generate_natal_chart,
            name="Consultante",
            date_str=date_str,
            time_str=time_str,
            place_text=payload.location,
        )
        report = await run_in_threadpool(generate_report, chart)

        report_id = uuid.uuid4().hex
        pdf_path = REPORTS_DIR / f"{report_id}.pdf"
        await run_in_threadpool(generate_pdf, chart, report, str(pdf_path))
    except (
        LocationNotFoundError,
        MissingBirthTimeError,
        InvalidHouseSystemError,
        InvalidDateTimeError,
    ) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except (GeocodingTimeoutError, EphemerisCalculationError) as exc:
        raise HTTPException(
            status_code=502, detail=f"No pudimos calcular tu carta: {exc}"
        ) from exc
    except MissingAPIKeyError as exc:
        raise HTTPException(
            status_code=500,
            detail="El servidor no tiene configurada la generación de informes.",
        ) from exc
    except (LLMGenerationError, LLMRefusalError) as exc:
        raise HTTPException(
            status_code=502, detail=f"No pudimos generar tu informe: {exc}"
        ) from exc
    except PDFExportError as exc:
        raise HTTPException(
            status_code=500, detail=f"No pudimos generar el PDF: {exc}"
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail="Ocurrió un error inesperado procesando tu carta."
        ) from exc

    return {
        "subject": chart["subject"],
        "report_text": report["full_text"],
        "pdf_url": f"/api/download/{report_id}",
    }


@app.get("/api/download/{report_id}")
async def download_report(report_id: str):
    if not _REPORT_ID_RE.match(report_id):
        raise HTTPException(status_code=404, detail="Informe no encontrado.")
    pdf_path = REPORTS_DIR / f"{report_id}.pdf"
    if not pdf_path.is_file():
        raise HTTPException(status_code=404, detail="Informe no encontrado.")
    return FileResponse(
        pdf_path, media_type="application/pdf", filename="carta-natal-siderea.pdf"
    )


@app.get("/success")
async def payment_success(request: Request):
    """Página de confirmación post-pago -- pura UX, sin lógica.

    La entrega ya no depende de que el usuario vuelva a este navegador ni
    de que espere a que termine de cargar: /api/webhook confirma el pago y
    dispara la generación + el envío del informe por mail de forma
    asincrónica y server-to-server, sin importar qué haga esta pestaña.
    """
    return templates.TemplateResponse(request, "success.html")


def _alert_admin(payment_id: str, customer_email: str | None, stage: str, error: BaseException) -> None:
    """Best-effort: avisa a SMTP_EMAIL que un pago aprobado no se entregó.

    Nunca deja que un fallo acá se propague -- si ni la alerta se puede
    mandar (ej. las mismas credenciales SMTP están rotas), el único
    recurso que queda es el log, así que como mínimo lo dejamos en CRITICAL
    para que sea imposible de no notar en los logs del servidor.
    """
    try:
        send_admin_alert_email(
            payment_id=payment_id,
            customer_email=customer_email or "desconocido",
            stage=stage,
            error=error,
        )
    except Exception:
        logger.critical(
            "No se pudo enviar NI LA ALERTA de administrador para payment_id=%s "
            "(stage=%s, error original=%r). Requiere revisión manual inmediata.",
            payment_id, stage, error,
        )


def _fulfill_payment(payment_id: str) -> None:
    """Verifica un pago, genera el informe y lo entrega por mail.

    Se invoca desde dos lugares: /api/webhook (recién claimeado un
    payment_id nuevo) y _recover_pending_payments en el arranque (un
    .pending sobrevivió a un proceso anterior interrumpido). Corre fuera
    del hilo principal en ambos casos (BackgroundTasks o
    run_in_threadpool) -- por eso es sincrónica de punta a punta, sin
    async/await.

    Cada etapa (verificación del pago, natal_engine, report_engine/
    Anthropic, pdf_engine/WeasyPrint, envío del mail) tiene su propio
    try/except: un pago aprobado que no se puede entregar es plata
    perdida y un cliente sin su informe, así que ninguna excepción se
    traga en silencio -- todas disparan una alerta por mail a SMTP_EMAIL
    con el payment_id, el email del cliente y el detalle del error, para
    poder resolverlo a mano.

    Cola transaccional persistente (.pending/.lock/.done), pensada para
    sobrevivir a un reinicio abrupto del proceso, no solo a una
    notificación duplicada:
    - .pending ya existe al entrar acá (lo crea _claim_payment antes de
      responder 200 a Mercado Pago, o ya estaba ahí si esto es una
      recuperación de arranque). Se borra recién cuando TODO termina bien.
    - .lock se reclama acá mismo, de forma atómica, para que dos intentos
      concurrentes de procesar el MISMO payment_id (una recuperación de
      arranque solapada con una notificación real, o dos workers sobre el
      mismo disco) no dupliquen el trabajo -- el que no consigue el lock
      se retira sin tocar nada. Se libera siempre en el `finally`, haya
      éxito o error, para no bloquear un reintento futuro.
    - .done se crea solo tras un envío de mail exitoso. Mientras no exista,
      un pago sigue siendo candidato a reintento (por una notificación
      posterior de Mercado Pago o por la recuperación de arranque) --
      justamente lo que se necesita si el proceso muere a mitad de camino.
    """
    done_path = REPORTS_DIR / f"webhook-{payment_id}.done"
    pending_path = REPORTS_DIR / f"webhook-{payment_id}.pending"
    lock_path = REPORTS_DIR / f"webhook-{payment_id}.lock"

    if done_path.exists():
        logger.info("payment_id=%s ya fue entregado antes; se ignora la notificación duplicada.", payment_id)
        return

    try:
        lock_path.touch(exist_ok=False)
    except FileExistsError:
        logger.info(
            "payment_id=%s ya se está procesando en otro hilo/proceso; se omite este intento.",
            payment_id,
        )
        return

    customer_email: str | None = None
    pdf_path: str | None = None

    try:
        # --- Etapa 1: verificar el pago contra la API real ------------------
        try:
            sdk = _get_mp_sdk()
            payment_result = sdk.payment().get(payment_id)
            payment_result.raise_for_status()
            payment = payment_result.get("response") or {}
        except (mercadopago.MercadoPagoError, requests.exceptions.RequestException, HTTPException) as exc:
            logger.exception("No se pudo verificar payment_id=%s contra Mercado Pago.", payment_id)
            _alert_admin(payment_id, customer_email, "verificacion_mercadopago", exc)
            return

        if payment.get("status") != "approved":
            # No es un error -- es un estado normal y transitorio (pendiente,
            # rechazado). No alertamos; un reintento posterior de Mercado
            # Pago, una vez que cambie el estado, va a completar la entrega.
            logger.info("payment_id=%s todavía no está aprobado (status=%s).", payment_id, payment.get("status"))
            return

        metadata = payment.get("metadata") or {}
        date_str = metadata.get("date")
        time_str = metadata.get("time")
        location = metadata.get("location")
        customer_email = metadata.get("email")

        if not (date_str and time_str and location and customer_email):
            logger.warning("payment_id=%s aprobado pero falta metadata: %r", payment_id, metadata)
            _alert_admin(
                payment_id, customer_email, "metadata_incompleta",
                ValueError(f"metadata incompleta en un pago aprobado: {metadata!r}"),
            )
            return

        # --- Etapa 2: natal_engine -------------------------------------------
        try:
            chart = generate_natal_chart(
                name="Consultante", date_str=date_str, time_str=time_str, place_text=location
            )
        except Exception as exc:
            logger.exception("natal_engine falló para payment_id=%s.", payment_id)
            _alert_admin(payment_id, customer_email, "natal_engine", exc)
            return

        # --- Etapa 3: report_engine (llamada real a la API de Anthropic) ----
        try:
            report = generate_report(chart)
        except (MissingAPIKeyError, LLMGenerationError, LLMRefusalError) as exc:
            logger.exception("report_engine (Anthropic) falló para payment_id=%s.", payment_id)
            _alert_admin(payment_id, customer_email, "report_engine_anthropic", exc)
            return
        except Exception as exc:
            logger.exception("Fallo inesperado en report_engine para payment_id=%s.", payment_id)
            _alert_admin(payment_id, customer_email, "report_engine_anthropic", exc)
            return

        # --- Etapa 4: pdf_engine (WeasyPrint), a un archivo temporal --------
        # Archivo temporal seguro en vez de un nombre propio bajo
        # REPORTS_DIR: este PDF se manda por mail y se descarta, no se sirve
        # después por URL como el de /api/generate-report -- no hace falta
        # que sobreviva más allá de este envío, y el `finally` de abajo
        # garantiza que se borre, ocurra un error o no.
        tmp_file = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
        tmp_file.close()
        pdf_path = tmp_file.name

        try:
            generate_pdf(chart, report, pdf_path)
        except PDFExportError as exc:
            logger.exception("pdf_engine (WeasyPrint) falló para payment_id=%s.", payment_id)
            _alert_admin(payment_id, customer_email, "pdf_engine_weasyprint", exc)
            return
        except Exception as exc:
            logger.exception("Fallo inesperado en pdf_engine para payment_id=%s.", payment_id)
            _alert_admin(payment_id, customer_email, "pdf_engine_weasyprint", exc)
            return

        # --- Etapa 5: entrega por mail al cliente ----------------------------
        try:
            send_report_email(customer_email, pdf_path)
        except EmailEngineError as exc:
            logger.exception("No se pudo enviar el informe a %s (payment_id=%s).", customer_email, payment_id)
            _alert_admin(payment_id, customer_email, "email_delivery", exc)
            return

        # Transición atómica de estado: primero el nuevo estado (.done),
        # después se retira el viejo (.pending). Si el proceso muriera
        # justo entre estas dos líneas, .pending Y .done coexistirían --
        # pero eso es seguro: el chequeo de done_path.exists() al principio
        # de esta función sigue ganando, así que un reintento posterior no
        # reprocesaría ni remandaría el mail.
        done_path.touch()
        try:
            pending_path.unlink()
        except FileNotFoundError:
            pass
        logger.info("Informe entregado por mail a %s (payment_id=%s).", customer_email, payment_id)

    except Exception as exc:
        # Red de seguridad final: cualquier cosa no prevista en las etapas de
        # arriba (un bug propio, algo que se nos escapó) tampoco se pierde en
        # silencio. .pending queda intacto a propósito -- un reintento
        # (notificación posterior o recuperación de arranque) todavía puede
        # completar la entrega.
        logger.exception("Fallo no clasificado procesando payment_id=%s.", payment_id)
        _alert_admin(payment_id, customer_email, "desconocido", exc)
    finally:
        if pdf_path:
            try:
                os.unlink(pdf_path)
            except OSError:
                pass
        try:
            lock_path.unlink()
        except FileNotFoundError:
            pass


@app.post("/api/webhook")
async def mercadopago_webhook(request: Request, background_tasks: BackgroundTasks):
    """Notificaciones (IPN/Webhooks) de Mercado Pago.

    Acepta tanto el formato actual de webhooks (JSON body
    {"type": "payment", "data": {"id": "..."}}) como el IPN legado
    (query string ?topic=payment&id=...), porque Mercado Pago todavía
    manda ambos según cómo esté configurada la integración.

    Registro garantizado ANTES del 200: si el payment_id es válido,
    _claim_payment() crea su archivo .pending en disco de forma síncrona,
    en esta misma request, antes de que la función retorne. Esto pasa
    ANTES de agendar el BackgroundTask y ANTES del `return` que produce el
    200 OK -- es la garantía real. Si el proceso se cae un milisegundo
    después de que Mercado Pago reciba ese 200 (un redeploy, un restart
    por límite de recursos) y la BackgroundTask nunca llega a correr, el
    .pending ya está en disco: no se perdió, y _recover_pending_payments
    lo va a reencolar en el próximo arranque (ver advertencia sobre disco
    persistente junto a REPORTS_DIR más arriba en este archivo).

    _claim_payment() es también la defensa de concurrencia: usa creación
    exclusiva de archivo, atómica a nivel de sistema operativo, así que
    dos notificaciones casi simultáneas para el mismo payment_id (o dos
    workers sobre el mismo disco) nunca agendan la tarea dos veces.
    """
    payment_id = None

    try:
        body = await request.json()
    except Exception:
        body = None

    if isinstance(body, dict) and body.get("type") == "payment":
        payment_id = (body.get("data") or {}).get("id")

    if not payment_id:
        query = request.query_params
        if query.get("topic") == "payment":
            payment_id = query.get("id")
        elif query.get("type") == "payment":
            payment_id = query.get("data.id") or query.get("id")

    if payment_id:
        payment_id = str(payment_id)
        # payment_id llega de un POST público, sin verificación de firma --
        # nunca confiar en su forma. Los IDs de pago de Mercado Pago son
        # siempre numéricos; validar esto ANTES de tocar el filesystem o de
        # mandarlo a la API evita que un valor con "../" o similar termine
        # construyendo una ruta fuera de REPORTS_DIR.
        if not payment_id.isdigit():
            logger.warning("payment_id con formato inesperado, se ignora: %r", payment_id)
            return {"status": "ignored"}

        if _claim_payment(payment_id):
            background_tasks.add_task(_fulfill_payment, payment_id)
        else:
            logger.info(
                "payment_id=%s ya estaba reclamado (en curso o ya entregado); no se agenda de nuevo.",
                payment_id,
            )
    else:
        logger.info("Webhook recibido sin payment_id reconocible, se ignora: %r", body)

    return {"status": "received"}


@app.post("/api/create-preference")
async def create_preference(payload: ChartRequest, request: Request):
    """Crea una preferencia real de Checkout Pro de Mercado Pago.

    Los datos de nacimiento y el email van en `metadata` para no perderlos
    después del pago -- POST /api/webhook los lee de ahí (vía el pago
    resultante) para generar el informe y mandarlo por mail sin pedírselos
    de nuevo al usuario.

    IMPORTANTE: la URL de este webhook (`{base_url}/api/webhook`) hay que
    configurarla en el panel de Mercado Pago (Tu negocio → Webhooks) -- no
    se manda acá como `notification_url` porque esa vía está deprecada.
    """
    sdk = _get_mp_sdk()
    base_url = str(request.base_url).rstrip("/")

    preference_data = {
        "items": [
            {
                "title": FULL_REPORT_TITLE,
                "quantity": 1,
                "currency_id": "ARS",
                "unit_price": FULL_REPORT_PRICE_ARS,
            }
        ],
        "back_urls": {
            "success": f"{base_url}/success",
            "failure": f"{base_url}/failure",
            "pending": f"{base_url}/pending",
        },
        "auto_return": "approved",
        # Datos de la carta y el email para poder generar el informe y
        # mandarlo una vez confirmado el pago (ver /api/webhook), sin
        # pedírselos de nuevo al usuario. Mercado Pago copia este metadata
        # al pago resultante.
        "metadata": {
            "date": payload.date.isoformat(),
            "time": payload.time.strftime("%H:%M"),
            "location": payload.location,
            "email": str(payload.email),
        },
    }

    try:
        result = await run_in_threadpool(sdk.preference().create, preference_data)
        result.raise_for_status()
    except mercadopago.MercadoPagoError as exc:
        raise HTTPException(
            status_code=502, detail=f"No pudimos iniciar el pago: {exc}"
        ) from exc
    except requests.exceptions.RequestException as exc:
        # Esta versión del SDK de mercadopago no envuelve fallos de red
        # (timeouts, DNS, proxy) en su propia jerarquía de excepciones --
        # llegan como requests.exceptions.* crudas. Sin este catch, un corte
        # de red devuelve un 500 sin cuerpo en vez de un error prolijo.
        raise HTTPException(
            status_code=502, detail="No pudimos conectar con Mercado Pago. Probá de nuevo en un rato."
        ) from exc

    preference = result.get("response") or {}
    return {
        "preference_id": preference.get("id"),
        "init_point": preference.get("init_point") or preference.get("sandbox_init_point"),
    }
