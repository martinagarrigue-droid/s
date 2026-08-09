"""Script definitivo end-to-end para Google Colab: datos de nacimiento -> PDF final.

Encadena las 3 etapas completas:
  1. natal_engine.generate_natal_chart()  -> JSON de la carta natal
  2. report_engine.generate_report()      -> informe generado por Claude
                                              (8 llamadas reales a la API,
                                              una por seccion -- tiene costo,
                                              ver estimacion en el mensaje
                                              que acompaña este script)
  3. pdf_engine.generate_pdf()            -> PDF final

A diferencia de examples/full_pipeline_demo.py (que degrada a texto de
relleno si falta la API key, pensado para probar el diseño sin gastar),
este script SIEMPRE hace la llamada real -- es la corrida final, no un demo.

Uso en Colab -- ver el checklist paso a paso en la respuesta de Claude que
entrego este script. Resumen:

    !pip install -q -r requirements.txt
    import os
    from getpass import getpass
    os.environ["ANTHROPIC_API_KEY"] = getpass("Anthropic API key: ")
    !python examples/run_full_pipeline.py

O import'ando main() directo en una celda si preferis no usar subprocess.
"""

import os
import sys
import time

from natal_engine.chart import generate_natal_chart
from natal_engine.exceptions import (
    EphemerisCalculationError,
    GeocodingTimeoutError,
    InvalidDateTimeError,
    InvalidHouseSystemError,
    LocationNotFoundError,
    MissingBirthTimeError,
)
from pdf_engine.exceptions import PDFExportError
from pdf_engine.exporter import generate_pdf
from report_engine.exceptions import LLMGenerationError, LLMRefusalError, MissingAPIKeyError
from report_engine.generator import generate_report

# ---------------------------------------------------------------------------
# DATOS DE NACIMIENTO -- reemplaza esto con los datos reales antes de correr.
# Opcion A: place_text (se resuelve por geocoding).
# Opcion B: comenta place_text y descomenta latitude=/longitude= si ya
#           conoces las coordenadas exactas (evita depender del geocoder).
# ---------------------------------------------------------------------------
DATOS_DE_NACIMIENTO = dict(
    name="Nombre Apellido",
    date_str="1990-05-14",  # YYYY-MM-DD
    time_str="14:32",  # HH:MM, hora local EXACTA de nacimiento
    place_text="Buenos Aires, Argentina",
    # latitude=-34.6037, longitude=-58.3816,
)

OUTPUT_PDF_PATH = "informe_natal_final.pdf"


def etapa_1_carta_natal() -> dict:
    print("=== Etapa 1: calculando carta natal ===")
    try:
        chart = generate_natal_chart(**DATOS_DE_NACIMIENTO)
    except LocationNotFoundError as exc:
        print(
            f"ERROR: no se pudo resolver el lugar de nacimiento.\n"
            f"  Detalle: {exc}\n"
            f"  Accion: revisa que 'place_text' este bien escrito y sea "
            f"especifico (ej. 'Rosario, Santa Fe, Argentina' en vez de solo "
            f"'Rosario'), o reemplazalo por latitude= y longitude= directo "
            f"en DATOS_DE_NACIMIENTO si ya conoces las coordenadas exactas."
        )
        sys.exit(1)
    except GeocodingTimeoutError as exc:
        print(
            f"ERROR: el servicio de geocoding (Nominatim/OpenStreetMap) no "
            f"respondio a tiempo.\n"
            f"  Detalle: {exc}\n"
            f"  Esto NO deberia pasar en Colab en condiciones normales (Colab "
            f"tiene salida a internet sin restricciones, a diferencia de "
            f"algunos entornos sandboxeados). Si aun asi ocurre, suele ser "
            f"saturacion puntual del servicio publico y gratuito de "
            f"Nominatim.\n"
            f"  Accion: esperá unos segundos y volvé a correr esta celda. Si "
            f"persiste, reemplazá place_text por latitude= / longitude= "
            f"directo en DATOS_DE_NACIMIENTO para evitar el geocoding por "
            f"completo (podes buscar las coordenadas en Google Maps: click "
            f"derecho sobre el lugar -> copian las coordenadas)."
        )
        sys.exit(1)
    except (MissingBirthTimeError, InvalidDateTimeError, InvalidHouseSystemError) as exc:
        print(
            f"ERROR de datos de entrada: {exc}\n"
            f"  Accion: revisa DATOS_DE_NACIMIENTO -- formato de fecha "
            f"'YYYY-MM-DD', hora 'HH:MM' de 24hs."
        )
        sys.exit(1)
    except EphemerisCalculationError as exc:
        print(f"ERROR de calculo astronomico: {exc}")
        sys.exit(1)

    print(
        f"  OK -- Sol en {chart['planets'][0]['sign']}, "
        f"Ascendente en {chart['angles']['ascendant']['sign']}, "
        f"{len(chart['aspects'])} aspectos mayores detectados."
    )
    return chart


def etapa_2_informe(chart: dict) -> dict:
    print("\n=== Etapa 2: generando informe con Claude (8 llamadas a la API) ===")
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print(
            "ERROR: falta ANTHROPIC_API_KEY en el entorno.\n"
            "  Accion: corré primero la celda que configura la key -- ver "
            "el checklist paso a paso antes de este script."
        )
        sys.exit(1)

    start = time.time()
    try:
        report = generate_report(chart)
    except MissingAPIKeyError as exc:
        print(f"ERROR: {exc}")
        sys.exit(1)
    except LLMRefusalError as exc:
        print(
            f"ERROR: Claude rechazo generar una seccion (stop_reason=refusal).\n"
            f"  Detalle: {exc}\n"
            f"  Es infrecuente para contenido psicologico/analitico legitimo "
            f"como este. Si persiste en la misma seccion, probá ajustar la "
            f"directiva de esa seccion en report_engine/config.py."
        )
        sys.exit(1)
    except LLMGenerationError as exc:
        print(
            f"ERROR: fallo la generacion despues de reintentos automaticos.\n"
            f"  Detalle: {exc}\n"
            f"  Accion: volve a correr la celda -- la mayoria de estos "
            f"errores son transitorios (rate limit o sobrecarga temporal del "
            f"servicio de Anthropic)."
        )
        sys.exit(1)

    elapsed = time.time() - start
    usage = report["usage"]
    total_tokens = usage["input_tokens"] + usage["output_tokens"] + usage["cache_creation_input_tokens"]
    print(f"  OK -- {len(report['sections'])} secciones generadas en {elapsed:.0f}s")
    print(
        f"  Tokens -- input: {usage['input_tokens']}, output: {usage['output_tokens']}, "
        f"cache_read: {usage['cache_read_input_tokens']}, "
        f"cache_creation: {usage['cache_creation_input_tokens']}"
    )
    return report


def etapa_3_pdf(chart: dict, report: dict) -> str:
    print("\n=== Etapa 3: exportando a PDF ===")
    try:
        generate_pdf(chart, report, OUTPUT_PDF_PATH)
    except PDFExportError as exc:
        print(f"ERROR: fallo la renderizacion del PDF.\n  Detalle: {exc}")
        sys.exit(1)
    print(f"  OK -- PDF guardado en {OUTPUT_PDF_PATH}")
    return OUTPUT_PDF_PATH


def main():
    chart = etapa_1_carta_natal()
    report = etapa_2_informe(chart)
    output_path = etapa_3_pdf(chart, report)
    print(f"\nListo. Informe completo en: {output_path}")


if __name__ == "__main__":
    main()
