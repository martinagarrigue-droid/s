"""Demo end-to-end de la Etapa 1: cálculo astronómico.

Corré esto en Colab (o local) con las dependencias de requirements.txt
instaladas. Genera una carta natal de prueba y la imprime como JSON,
lista para ser el input de la Etapa 2 (prompt + LLM).

Uso:
    python examples/stage1_demo.py
"""

import json

from natal_engine.chart import generate_natal_chart
from natal_engine.exceptions import (
    GeocodingTimeoutError,
    LocationNotFoundError,
    MissingBirthTimeError,
)

DATOS_DE_PRUEBA = dict(
    name="Persona de Prueba",
    date_str="1990-05-14",
    time_str="14:32",
)


def demo_con_lugar_en_texto():
    """Camino principal: el usuario escribe la ciudad, se geocodifica sola."""
    print("--- Intentando geocoding desde texto libre ('Rosario, Argentina') ---")
    try:
        chart = generate_natal_chart(
            **DATOS_DE_PRUEBA,
            place_text="Rosario, Santa Fe, Argentina",
        )
        return chart
    except LocationNotFoundError as exc:
        print(f"Lugar no encontrado: {exc}")
    except GeocodingTimeoutError as exc:
        print(f"Geocoding no disponible ahora mismo: {exc}")
    return None


def demo_con_coordenadas_directas():
    """Camino alternativo: lat/long directo, sin depender de un geocoder externo."""
    print("--- Generando carta con lat/long directos (Rosario, AR) ---")
    return generate_natal_chart(
        **DATOS_DE_PRUEBA,
        latitude=-32.9468,
        longitude=-60.6393,
    )


def demo_error_sin_hora():
    """Muestra el manejo de errores: falta la hora de nacimiento."""
    print("--- Probando manejo de error: hora de nacimiento faltante ---")
    try:
        generate_natal_chart(
            name="Sin Hora",
            date_str="1990-05-14",
            time_str="",
            latitude=-32.9468,
            longitude=-60.6393,
        )
    except MissingBirthTimeError as exc:
        print(f"OK, error esperado capturado: {exc}")


if __name__ == "__main__":
    chart = demo_con_lugar_en_texto()
    if chart is None:
        chart = demo_con_coordenadas_directas()

    print("\n--- JSON resultante (input listo para la Etapa 2) ---")
    print(json.dumps(chart, indent=2, ensure_ascii=False, default=str))

    print(
        f"\nResumen: Sol en {chart['planets'][0]['sign']} "
        f"{chart['planets'][0]['sign_degree']:.1f}°, "
        f"Ascendente en {chart['angles']['ascendant']['sign']}, "
        f"{len(chart['aspects'])} aspectos detectados."
    )

    demo_error_sin_hora()
