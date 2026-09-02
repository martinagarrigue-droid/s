import logging
import os
import re
import tempfile
import uuid
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

app = FastAPI(title="Sidérea")

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

REPORTS_DIR = Path(__file__).resolve().parent / "generated_reports"
REPORTS_DIR.mkdir(exist_ok=True)

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

# Idempotencia rápida, en memoria, a nivel de request del webhook -- ver
# advertencia sobre su límite en mercadopago_webhook() más abajo. La
# defensa durable de verdad (sobrevive a un restart) es el archivo
# marcador dentro de _fulfill_payment.
processed_payments: set[str] = set()


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

    Corre en un hilo de BackgroundTasks después de que /api/webhook ya le
    respondió 200 OK a Mercado Pago -- por eso es sincrónica de punta a
    punta (sin async/await): no hay un loop de eventos esperándola, y
    Starlette ya la ejecuta fuera del hilo principal.

    Cada etapa (verificación del pago, natal_engine, report_engine/
    Anthropic, pdf_engine/WeasyPrint, envío del mail) tiene su propio
    try/except: un pago aprobado que no se puede entregar es plata
    perdida y un cliente sin su informe, así que ninguna excepción se
    traga en silencio -- todas disparan una alerta por mail a SMTP_EMAIL
    con el payment_id, el email del cliente y el detalle del error, para
    poder resolverlo a mano.

    Idempotente con un archivo marcador (independiente del set en memoria
    de mercadopago_webhook, que se pierde en cada restart): si Mercado
    Pago reintenta la notificación o alguien reenvía el mismo payment_id
    después de que YA se entregó, no se regenera el informe ni se
    remanda el mail -- cada regeneración dispara ~8 llamadas reales a
    Claude, así que un duplicado sin controlar sale caro. El marcador
    solo se escribe tras un envío exitoso, para que un pago todavía
    pendiente o con metadata incompleta pueda completarse en un reintento
    posterior.
    """
    marker_path = REPORTS_DIR / f"webhook-{payment_id}.done"
    if marker_path.exists():
        logger.info("payment_id=%s ya fue entregado antes; se ignora la notificación duplicada.", payment_id)
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

        marker_path.touch()
        logger.info("Informe entregado por mail a %s (payment_id=%s).", customer_email, payment_id)

    except Exception as exc:
        # Red de seguridad final: cualquier cosa no prevista en las etapas de
        # arriba (un bug propio, algo que se nos escapó) tampoco se pierde en
        # silencio.
        logger.exception("Fallo no clasificado procesando payment_id=%s.", payment_id)
        _alert_admin(payment_id, customer_email, "desconocido", exc)
    finally:
        if pdf_path:
            try:
                os.unlink(pdf_path)
            except OSError:
                pass


@app.post("/api/webhook")
async def mercadopago_webhook(request: Request, background_tasks: BackgroundTasks):
    """Notificaciones (IPN/Webhooks) de Mercado Pago.

    Respondemos 200 OK enseguida, sin esperar a verificar nada -- Mercado
    Pago reintenta agresivamente si la respuesta tarda o falla, y no
    necesitamos que espere a que generemos el informe. El trabajo real
    (verificar el pago, generar el PDF, mandar el mail) queda en
    BackgroundTasks, después de que esta respuesta ya salió.

    Acepta tanto el formato actual de webhooks (JSON body
    {"type": "payment", "data": {"id": "..."}}) como el IPN legado
    (query string ?topic=payment&id=...), porque Mercado Pago todavía
    manda ambos según cómo esté configurada la integración.

    Idempotencia básica en memoria: si el payment_id ya está en
    `processed_payments`, no se agenda nada de nuevo. OJO -- esto es un
    set en memoria del proceso, así que se vacía en cada restart/deploy, y
    marca el payment_id como visto apenas llega la PRIMERA notificación,
    sea cual sea su estado. Para medios de pago con confirmación
    asincrónica (transferencia, Rapipago, etc.) Mercado Pago puede mandar
    primero un aviso en estado "pending" y más tarde el de "approved" para
    el mismo payment_id -- con este set, ese segundo aviso legítimo
    también quedaría descartado acá. La defensa que sí es durable y sí
    distingue "ya entregado" de "todavía no aprobado" es el archivo
    marcador dentro de _fulfill_payment; este set es solo una primera
    barrera rápida contra reintentos casi inmediatos, tal como fue pedido.
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
        # siempre numéricos; validar esto ANTES de tocar el filesystem
        # (marker_path en _fulfill_payment se arma con f"...{payment_id}...")
        # o de mandarlo a la API evita que un valor con "../" o similar
        # termine construyendo una ruta fuera de REPORTS_DIR.
        if not payment_id.isdigit():
            logger.warning("payment_id con formato inesperado, se ignora: %r", payment_id)
            return {"status": "ignored"}
        if payment_id in processed_payments:
            logger.info("payment_id=%s ya está en processed_payments; se ignora el webhook duplicado.", payment_id)
            return {"status": "already_processed"}
        processed_payments.add(payment_id)
        background_tasks.add_task(_fulfill_payment, payment_id)
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
