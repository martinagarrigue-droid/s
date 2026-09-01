import os
import re
import uuid
from datetime import date as date_type, time as time_type
from pathlib import Path

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
# cambiar sea este.
FULL_REPORT_PRICE_ARS = 9900


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


@app.get("/api/test-pdf")
async def test_pdf_pipeline(token: str | None = None):
    """TEMPORAL -- prueba de fuego manual del pipeline completo con datos
    fijos, usando la ANTHROPIC_API_KEY real de este servidor.

    Corre natal_engine -> report_engine -> pdf_engine para un nacimiento de
    prueba (23 ago 2026, 15:33, Buenos Aires) y devuelve el PDF resultante
    para descarga directa. Cada request dispara ~8 llamadas reales a Claude
    (una por sección del informe) y consume créditos.

    Protegido por un token compartido: sin la env var TEST_PDF_TOKEN
    seteada en el servidor, este endpoint responde 404 (como si no
    existiera). Con ella seteada, hay que pasar ?token=<mismo valor>. Sin
    esto, cualquiera que encuentre la URL podría gastar créditos de la
    cuenta repetidamente sin límite.

    Sacá esta ruta del código (o al menos desactivá TEST_PDF_TOKEN) una vez
    que termines de validar el informe -- es de un solo uso, no un
    endpoint de producto.
    """
    expected_token = os.environ.get("TEST_PDF_TOKEN")
    if not expected_token or token != expected_token:
        raise HTTPException(status_code=404)

    try:
        chart = await run_in_threadpool(
            generate_natal_chart,
            name="Consultante de Prueba",
            date_str="2026-08-23",
            time_str="15:33",
            place_text="Buenos Aires, Argentina",
        )
        report = await run_in_threadpool(generate_report, chart)

        pdf_path = REPORTS_DIR / "test-pdf.pdf"
        await run_in_threadpool(generate_pdf, chart, report, str(pdf_path))
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"Falló la generación de prueba: {exc}"
        ) from exc

    return FileResponse(
        pdf_path,
        media_type="application/pdf",
        filename="reporte_prueba.pdf",
    )


@app.post("/api/create-preference")
async def create_preference(payload: ChartRequest):
    """Stub del inicio de checkout de Mercado Pago.

    Todavía no crea una preferencia real. Cuando se conecte el SDK, esto
    pasaría a ser algo como:

        import mercadopago
        sdk = mercadopago.SDK(os.environ["MERCADOPAGO_ACCESS_TOKEN"])
        preference_data = {
            "items": [{
                "title": "Informe completo Sidérea",
                "quantity": 1,
                "currency_id": "ARS",
                "unit_price": FULL_REPORT_PRICE_ARS,
            }],
            "back_urls": {
                "success": f"{BASE_URL}/pago/exito",
                "failure": f"{BASE_URL}/pago/error",
                "pending": f"{BASE_URL}/pago/pendiente",
            },
            "auto_return": "approved",
            "notification_url": f"{BASE_URL}/api/payments/webhook",
            # Datos de la carta para poder generar el informe una vez
            # confirmado el pago, sin pedírselos de nuevo al usuario.
            "metadata": {
                "date": payload.date.isoformat(),
                "time": payload.time.strftime("%H:%M"),
                "location": payload.location,
            },
        }
        preference = sdk.preference().create(preference_data)["response"]
        return {"preference_id": preference["id"], "init_point": preference["init_point"]}

    El webhook de confirmación de pago (POST /api/payments/webhook, a
    implementar) sería el que dispare /api/generate-report para el
    consultante correspondiente.
    """
    return {
        "status": "pending_integration",
        "preference_id": None,
        "init_point": None,
        "price_ars": FULL_REPORT_PRICE_ARS,
        "message": (
            "La pasarela de pago está en preparación. "
            "Pronto vas a poder completar tu compra acá."
        ),
    }
