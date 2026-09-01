import os
import re
import uuid
from datetime import date as date_type, time as time_type
from pathlib import Path

import mercadopago
import requests
from fastapi import FastAPI, HTTPException, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, field_validator

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
}

# Precio de referencia del informe completo. Vive acá (no hardcodeado en el
# payload de Mercado Pago) para que el día que haya un solo lugar que
# cambiar sea este. Placeholder -- ajustar antes de lanzar.
FULL_REPORT_PRICE_ARS = 15000
FULL_REPORT_TITLE = "Sidérea - Lectura Óptica Integral"

_mp_sdk: mercadopago.SDK | None = None


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


def _payment_error_page(request: Request, message: str, status_code: int = 400):
    return templates.TemplateResponse(
        request, "payment_error.html", {"message": message}, status_code=status_code
    )


@app.get("/success")
async def payment_success(
    request: Request,
    preference_id: str | None = None,
    payment_id: str | None = None,
):
    """Entrega automática del informe tras un pago aprobado.

    Mercado Pago redirige acá con `preference_id` y `payment_id` en la
    query string después del checkout -- pero esos query params son
    trivialmente falsificables por cualquiera que visite la URL a mano.
    Nunca confiamos en ellos solos: `payment_id` se usa para consultar el
    pago real contra la API de Mercado Pago (con nuestro access token) y
    solo generamos el informe si esa consulta confirma `status == "approved"`.

    Los datos de nacimiento viajan en el `metadata` que le pusimos a la
    preferencia al crearla (ver /api/create-preference) -- Mercado Pago los
    copia al pago resultante, así que no hace falta pedírselos de nuevo al
    usuario ni guardar estado propio entre la preferencia y el pago.

    `preference_id` se acepta porque Mercado Pago lo manda, pero no hace
    falta para la lógica: `payment_id` (verificado contra la API) ya es
    suficiente para reconstruir todo.
    """
    if not payment_id:
        return _payment_error_page(
            request,
            "No encontramos información de tu pago. Si ya pagaste, "
            "escribinos con tu número de operación y lo resolvemos a mano.",
        )

    try:
        sdk = _get_mp_sdk()
    except HTTPException as exc:
        return _payment_error_page(request, str(exc.detail), status_code=exc.status_code)

    try:
        payment_result = await run_in_threadpool(sdk.payment().get, payment_id)
        payment_result.raise_for_status()
    except mercadopago.MercadoPagoError as exc:
        return _payment_error_page(
            request, f"No pudimos verificar tu pago con Mercado Pago: {exc}", status_code=502
        )
    except requests.exceptions.RequestException:
        return _payment_error_page(
            request,
            "No pudimos conectar con Mercado Pago para verificar tu pago. Probá de nuevo en un rato.",
            status_code=502,
        )

    payment = payment_result["response"]

    if payment.get("status") != "approved":
        return _payment_error_page(
            request,
            "Tu pago todavía no está aprobado. Si acabás de pagar, esperá "
            "unos segundos y volvé a abrir el enlace que te mandó Mercado Pago.",
            status_code=402,
        )

    metadata = payment.get("metadata") or {}
    date_str = metadata.get("date")
    time_str = metadata.get("time")
    location = metadata.get("location")

    if not (date_str and time_str and location):
        return _payment_error_page(
            request,
            "Tu pago está aprobado, pero no encontramos los datos de tu "
            "carta asociados. Escribinos con tu número de pago y te lo "
            "mandamos a mano.",
            status_code=422,
        )

    try:
        chart = await run_in_threadpool(
            generate_natal_chart,
            name="Consultante",
            date_str=date_str,
            time_str=time_str,
            place_text=location,
        )
        report = await run_in_threadpool(generate_report, chart)

        pdf_path = REPORTS_DIR / f"{uuid.uuid4().hex}.pdf"
        await run_in_threadpool(generate_pdf, chart, report, str(pdf_path))
    except Exception:
        return _payment_error_page(
            request,
            "Tu pago está aprobado, pero hubo un error generando tu informe. "
            "Escribinos con tu número de pago y te lo mandamos a mano.",
            status_code=500,
        )

    return FileResponse(
        pdf_path,
        media_type="application/pdf",
        filename="Siderea_Lectura_Optica.pdf",
    )


@app.post("/api/create-preference")
async def create_preference(payload: ChartRequest, request: Request):
    """Crea una preferencia real de Checkout Pro de Mercado Pago.

    Los datos de nacimiento van en `metadata` para no perderlos después del
    pago -- el webhook (a implementar) los va a leer de ahí para disparar
    /api/generate-report sin pedírselos de nuevo al usuario.
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
        # Datos de la carta para poder generar el informe una vez
        # confirmado el pago, sin pedírselos de nuevo al usuario.
        "metadata": {
            "date": payload.date.isoformat(),
            "time": payload.time.strftime("%H:%M"),
            "location": payload.location,
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

    preference = result["response"]
    return {
        "preference_id": preference.get("id"),
        "init_point": preference.get("init_point") or preference.get("sandbox_init_point"),
    }
