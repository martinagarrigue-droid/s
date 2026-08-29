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


@app.get("/")
async def read_index(request: Request):
    return templates.TemplateResponse(request, "index.html")


@app.post("/api/calculate")
async def calculate(payload: ChartRequest):
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
