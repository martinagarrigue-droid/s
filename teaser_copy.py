"""Copy fijo para el extracto óptico gratuito (teaser) de la carta.

Deliberadamente NO pasa por report_engine: la vista previa gratuita no debe
disparar el costo de una llamada a Claude. Eso queda reservado al informe
completo, después del pago (ver main.py: /api/calculate vs
/api/generate-report).
"""

SIGN_LABELS_ES = {
    "Aries": "Aries",
    "Taurus": "Tauro",
    "Gemini": "Géminis",
    "Cancer": "Cáncer",
    "Leo": "Leo",
    "Virgo": "Virgo",
    "Libra": "Libra",
    "Scorpio": "Escorpio",
    "Sagittarius": "Sagitario",
    "Capricorn": "Capricornio",
    "Aquarius": "Acuario",
    "Pisces": "Piscis",
}

# Una frase por signo solar, en el mismo lenguaje óptico/lumínico que el
# resto del sitio (aura, halo, núcleo) — no genérica de horóscopo.
SUN_SIGN_PHRASES = {
    "Aries": "Núcleo de ignición: luz que se enciende antes de pensarse dos veces.",
    "Taurus": "Luz de baja frecuencia y alta persistencia: brilla constante, no destella.",
    "Gemini": "Doble haz: dos frecuencias de luz alternando en el mismo punto.",
    "Cancer": "Luz reflejada, no emitida: absorbe el ambiente y lo devuelve transformado.",
    "Leo": "Fuente central de irradiación constante: la luz que necesita ser vista para confirmarse a sí misma.",
    "Virgo": "Luz filtrada, de espectro angosto y preciso: ilumina el detalle, no el conjunto.",
    "Libra": "Luz en equilibrio dinámico: dos focos que se balancean para no proyectar una sola sombra.",
    "Scorpio": "Luz concentrada bajo presión: opaca por fuera, incandescente en el núcleo.",
    "Sagittarius": "Haz de largo alcance: la luz que se dispara hacia el horizonte, no hacia el suelo.",
    "Capricorn": "Luz de combustión lenta: tarda en encender, no se apaga.",
    "Aquarius": "Luz difractada en patrón: no es un punto, es una red de puntos coherentes entre sí.",
    "Pisces": "Luz sin bordes definidos: se filtra por cualquier superficie porosa que encuentre.",
}

DEFAULT_PHRASE = "Un patrón de luz propio, todavía por describir."


def build_teaser(chart: dict) -> dict:
    """Arma el extracto óptico gratuito a partir del chart de natal_engine."""
    sun = next(p for p in chart["planets"] if p["name"] == "Sun")
    ascendant = chart["angles"]["ascendant"]

    sun_sign_en = sun["sign"]
    ascendant_sign_en = ascendant["sign"]

    return {
        "sun_sign": SIGN_LABELS_ES.get(sun_sign_en, sun_sign_en),
        "ascendant_sign": SIGN_LABELS_ES.get(ascendant_sign_en, ascendant_sign_en),
        "phrase": SUN_SIGN_PHRASES.get(sun_sign_en, DEFAULT_PHRASE),
    }
