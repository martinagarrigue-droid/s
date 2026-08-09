"""Demo end-to-end de las Etapas 1 + 2: carta natal -> informe generado por Claude.

Requiere una API key de Anthropic real en la variable de entorno
ANTHROPIC_API_KEY (nunca la hardcodees). En Colab:

    import os
    from getpass import getpass
    os.environ["ANTHROPIC_API_KEY"] = getpass("Anthropic API key: ")

Genera 8 secciones (una llamada a la API por seccion) para el mismo dato de
prueba de la Etapa 1. Con claude-opus-5 y effort=high esto tarda unos
minutos y tiene un costo real de API -- no es gratis correrlo.

Uso:
    python examples/stage2_demo.py
"""

import os

from natal_engine.chart import generate_natal_chart
from report_engine.exceptions import MissingAPIKeyError, LLMGenerationError, LLMRefusalError
from report_engine.generator import generate_report

DATOS_DE_PRUEBA = dict(
    name="Persona de Prueba",
    date_str="1990-05-14",
    time_str="14:32",
    latitude=-34.6037,
    longitude=-58.3816,
)


def main():
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print(
            "Falta ANTHROPIC_API_KEY en el entorno. Este demo hace llamadas "
            "reales a la API de Anthropic (con costo). Segui las instrucciones "
            "del docstring de este archivo antes de correrlo."
        )
        return

    print("--- Etapa 1: calculando carta natal ---")
    chart = generate_natal_chart(**DATOS_DE_PRUEBA)
    print(
        f"Sol en {chart['planets'][0]['sign']}, "
        f"Ascendente en {chart['angles']['ascendant']['sign']}, "
        f"{len(chart['aspects'])} aspectos."
    )

    print("\n--- Etapa 2: generando informe seccion por seccion ---")
    try:
        report = generate_report(chart)
    except MissingAPIKeyError as exc:
        print(f"Falta configurar la API key: {exc}")
        return
    except LLMRefusalError as exc:
        print(f"El modelo rechazo una seccion: {exc}")
        return
    except LLMGenerationError as exc:
        print(f"Fallo la generacion: {exc}")
        return

    for section in report["sections"]:
        print(f"  [{section['key']}] {len(section['text'])} caracteres generados")

    usage = report["usage"]
    print(
        f"\nTokens totales -- input: {usage['input_tokens']}, "
        f"output: {usage['output_tokens']}, "
        f"cache_read: {usage['cache_read_input_tokens']}, "
        f"cache_creation: {usage['cache_creation_input_tokens']}"
    )

    output_path = "informe_demo.md"
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(f"# Informe natal -- {report['subject_name']}\n\n")
        f.write(report["full_text"])
    print(f"\nInforme completo guardado en {output_path} (input para la Etapa 3).")


if __name__ == "__main__":
    main()
