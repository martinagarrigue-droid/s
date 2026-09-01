"""Prueba de fuego: natal_engine -> report_engine -> pdf_engine con datos
simulados y una llamada REAL a la API de Anthropic.

Script temporal de validación manual -- no es parte de la app FastAPI ni se
importa desde otro módulo. Requiere ANTHROPIC_API_KEY en el entorno (y
consume créditos reales: genera 8 llamadas a Claude, una por sección del
informe).

Uso:
    ANTHROPIC_API_KEY=sk-... python test_pipeline.py
"""

import os
import sys

from natal_engine import GeocodingTimeoutError, LocationNotFoundError, generate_natal_chart
from pdf_engine import generate_pdf
from report_engine import generate_report

NAME = "Consultante de Prueba"
DATE_STR = "2026-08-23"
TIME_STR = "15:33"
PLACE_TEXT = "Buenos Aires, Argentina"

# Fallback si el geocoding no tiene salida a internet en este entorno
# (algunos sandboxes bloquean Nominatim) -- coordenadas reales de Buenos
# Aires, para poder validar report_engine/pdf_engine igual.
FALLBACK_LAT, FALLBACK_LON = -34.6037, -58.3816

OUTPUT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "reporte_prueba.pdf")


def build_chart():
    try:
        print(f"Geocodificando '{PLACE_TEXT}'...")
        return generate_natal_chart(
            name=NAME, date_str=DATE_STR, time_str=TIME_STR, place_text=PLACE_TEXT,
        )
    except (LocationNotFoundError, GeocodingTimeoutError) as exc:
        print(
            f"Geocoding no disponible en este entorno ({exc}); "
            "usando coordenadas fijas de Buenos Aires como fallback."
        )
        return generate_natal_chart(
            name=NAME,
            date_str=DATE_STR,
            time_str=TIME_STR,
            latitude=FALLBACK_LAT,
            longitude=FALLBACK_LON,
        )


def main():
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print(
            "ERROR: ANTHROPIC_API_KEY no está seteada en el entorno. "
            "report_engine la necesita para la llamada real a Claude.",
            file=sys.stderr,
        )
        sys.exit(1)

    print("1/3 -- natal_engine: calculando carta...")
    chart = build_chart()
    sun_sign = next(p for p in chart["planets"] if p["name"] == "Sun")["sign"]
    print(f"   Sol: {sun_sign}  Ascendente: {chart['angles']['ascendant']['sign']}")

    print("2/3 -- report_engine: generando informe con Claude (llamada real, consume créditos)...")
    report = generate_report(chart)
    print(f"   {len(report['sections'])} secciones generadas, modelo {report['model']}.")

    print("3/3 -- pdf_engine: renderizando PDF...")
    generate_pdf(chart, report, OUTPUT_PATH)
    print(f"Listo: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
