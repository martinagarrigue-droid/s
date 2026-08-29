from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

app = FastAPI(title="Sidérea")

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")


class ChartRequest(BaseModel):
    date: str
    time: str
    location: str


@app.get("/")
async def read_index(request: Request):
    return templates.TemplateResponse(request, "index.html")


@app.post("/api/calculate")
async def calculate(payload: ChartRequest):
    # TODO: wire up to natal_engine.generate_natal_chart, then
    # report_engine.generate_report and pdf_engine.generate_pdf. Not
    # implemented yet.
    return {"status": "not_implemented", "received": payload}
