"""Constantes astrologicas y de configuracion del motor.

Todo lo que sea "regla astrologica" (regencias, orbes, sistemas de casas)
vive aca para que ajustarlo no implique tocar la logica de calculo.
"""

import swisseph as swe

# ---------------------------------------------------------------------------
# Cuerpos calculados en el MVP: Sol a Pluton + Nodo Norte medio.
# El Nodo Sur no se pide a swisseph: es siempre el opuesto exacto del Norte.
# No se incluyen Quiron ni Lilith en este MVP (se pueden sumar despues sin
# romper el schema, agregando entradas a este dict).
# ---------------------------------------------------------------------------
PLANET_CODES = {
    "Sun": swe.SUN,
    "Moon": swe.MOON,
    "Mercury": swe.MERCURY,
    "Venus": swe.VENUS,
    "Mars": swe.MARS,
    "Jupiter": swe.JUPITER,
    "Saturn": swe.SATURN,
    "Uranus": swe.URANUS,
    "Neptune": swe.NEPTUNE,
    "Pluto": swe.PLUTO,
    "North Node": swe.MEAN_NODE,
}

ZODIAC_SIGNS = [
    "Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo",
    "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces",
]

# Regencia clasica/tradicional (pre-descubrimiento de Urano/Neptuno/Pluton).
# Escorpio=Marte, Acuario=Saturno, Piscis=Jupiter -- a proposito, no moderna.
TRADITIONAL_RULERS = {
    "Aries": "Mars",
    "Taurus": "Venus",
    "Gemini": "Mercury",
    "Cancer": "Moon",
    "Leo": "Sun",
    "Virgo": "Mercury",
    "Libra": "Venus",
    "Scorpio": "Mars",
    "Sagittarius": "Jupiter",
    "Capricorn": "Saturn",
    "Aquarius": "Saturn",
    "Pisces": "Jupiter",
}

# Sistemas de casas soportados -> codigo de 1 letra que espera swisseph.
HOUSE_SYSTEMS = {
    "Placidus": b"P",
    "Koch": b"K",
    "Whole Sign": b"W",
    "Equal": b"E",
    "Regiomontanus": b"R",
    "Campanus": b"C",
    "Porphyry": b"O",
}

DEFAULT_HOUSE_SYSTEM = "Placidus"

# Aspectos mayores: nombre -> angulo exacto.
ASPECTS = {
    "conjunction": 0,
    "sextile": 60,
    "square": 90,
    "trine": 120,
    "opposition": 180,
}

# Orbes por defecto en grados, editables por llamada.
DEFAULT_ASPECT_ORBS = {
    "conjunction": 8,
    "opposition": 8,
    "square": 7,
    "trine": 8,
    "sextile": 6,
}

# Cuerpos que participan en el calculo de aspectos ademas de los planetas.
# El Descendente y el IC quedan afuera a proposito: son el opuesto exacto
# de Ascendente/Medio Cielo, incluirlos duplicaria cada aspecto.
ANGLE_BODIES = ["Ascendant", "Midheaven"]

SWISS_EPHE_FLAG = swe.FLG_SWIEPH | swe.FLG_SPEED
MOSHIER_FLAG = swe.FLG_MOSEPH | swe.FLG_SPEED
