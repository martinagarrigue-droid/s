"""Demo end-to-end de las 3 etapas: carta natal -> informe LLM -> PDF final.

Si hay ANTHROPIC_API_KEY configurada, corre las 3 etapas de punta a punta con
el informe real generado por Claude (con costo de API). Si no hay key, igual
genera el PDF final usando texto de relleno en lugar de la Etapa 2, para que
puedas revisar el diseño del documento sin gastar en la API.

Uso:
    python examples/full_pipeline_demo.py
"""

import os

from natal_engine.chart import generate_natal_chart
from pdf_engine.exporter import generate_pdf

DATOS_DE_PRUEBA = dict(
    name="Persona de Prueba",
    date_str="1990-05-14",
    time_str="14:32",
    latitude=-34.6037,
    longitude=-58.3816,
)

_PLACEHOLDER_SECTIONS = [
    ("introduccion", "Introduccion operativa"),
    ("identidad_nuclear", "Identidad nuclear: Sol, Luna, Ascendente"),
    ("sintesis", "Sintesis final accionable"),
]


def _placeholder_report(chart: dict) -> dict:
    """Informe de relleno (NO generado por Claude) solo para probar la Etapa 3."""
    return {
        "subject_name": chart["subject"]["name"],
        "model": None,
        "sections": [
            {
                "key": key,
                "title": title,
                "text": (
                    f"[Texto de relleno -- la Etapa 2 no corrio porque falta "
                    f"ANTHROPIC_API_KEY. Esta seccion ('{title}') se veria "
                    f"reemplazada por el analisis real generado por Claude a "
                    f"partir de los datos de la carta natal calculados en la "
                    f"Etapa 1.]\n\nParrafo de ejemplo para verificar el "
                    f"espaciado y la tipografia del diseño final."
                ),
            }
            for key, title in _PLACEHOLDER_SECTIONS
        ],
        "full_text": "",
        "usage": {"input_tokens": 0, "output_tokens": 0, "cache_read_input_tokens": 0, "cache_creation_input_tokens": 0},
    }


def main():
    print("--- Etapa 1: calculando carta natal ---")
    chart = generate_natal_chart(**DATOS_DE_PRUEBA)
    print(
        f"Sol en {chart['planets'][0]['sign']}, "
        f"Ascendente en {chart['angles']['ascendant']['sign']}, "
        f"{len(chart['aspects'])} aspectos."
    )

    if os.environ.get("ANTHROPIC_API_KEY"):
        print("\n--- Etapa 2: generando informe con Claude (llamadas reales, con costo) ---")
        from report_engine.generator import generate_report

        report = generate_report(chart)
        for section in report["sections"]:
            print(f"  [{section['key']}] {len(section['text'])} caracteres generados")
    else:
        print(
            "\n--- Etapa 2 omitida: no hay ANTHROPIC_API_KEY en el entorno. "
            "Usando texto de relleno para poder probar la Etapa 3 igual. ---"
        )
        report = _placeholder_report(chart)

    print("\n--- Etapa 3: exportando a PDF ---")
    output_path = "informe_natal.pdf"
    generate_pdf(chart, report, output_path)
    print(f"PDF generado en {output_path}")


if __name__ == "__main__":
    main()
