"""Orquestador de la Etapa 1: arma el JSON de carta natal completo.

`generate_natal_chart(...)` es el unico punto de entrada publico que va a
consumir la Etapa 2 (armado del prompt para el LLM).
"""

from natal_engine.aspects import AspectBody, compute_aspects
from natal_engine.config import (
    ANGLE_BODIES,
    DEFAULT_ASPECT_ORBS,
    DEFAULT_HOUSE_SYSTEM,
    HOUSE_SYSTEMS,
    PLANET_CODES,
    TRADITIONAL_RULERS,
)
from natal_engine.ephemeris import (
    calculate_houses,
    calculate_planet,
    datetime_to_julian_day,
    find_house_of_longitude,
    local_to_utc,
    longitude_to_sign,
)
from natal_engine.exceptions import InvalidHouseSystemError, MissingBirthTimeError
from natal_engine.location import geocode_place, resolve_timezone

import swisseph as swe

SCHEMA_VERSION = "1.0"


def generate_natal_chart(
    name: str,
    date_str: str,
    time_str: str,
    place_text: str | None = None,
    latitude: float | None = None,
    longitude: float | None = None,
    house_system: str = DEFAULT_HOUSE_SYSTEM,
    aspect_orbs: dict | None = None,
    ephe_path: str | None = None,
) -> dict:
    """Calcula una carta natal completa y la devuelve como dict JSON-serializable.

    Args:
        name: nombre del consultante (metadata, no afecta el calculo).
        date_str: fecha de nacimiento 'YYYY-MM-DD'.
        time_str: hora exacta de nacimiento 'HH:MM' o 'HH:MM:SS'. Requerida:
            este MVP no soporta carta sin hora conocida (ver
            MissingBirthTimeError).
        place_text: lugar de nacimiento en texto libre (ej. 'Rosario,
            Argentina'). Se resuelve via geocoding. Si se pasan latitude y
            longitude directamente, place_text es opcional.
        latitude, longitude: coordenadas directas, alternativa a place_text.
        house_system: uno de natal_engine.config.HOUSE_SYSTEMS.
        aspect_orbs: dict opcional para sobreescribir orbes por defecto,
            ej. {'conjunction': 6}.
        ephe_path: path a archivos de efemerides Swiss (.se1) para mayor
            precision. Si no se pasa, usa el efemeride Moshier embebido
            (preciso a ~1 arcsegundo, sin dependencias externas -- anda
            directo en Google Colab).

    Returns:
        dict con el schema acordado: meta, subject, settings, angles,
        houses, planets, aspects.

    Raises:
        MissingBirthTimeError, InvalidDateTimeError, InvalidHouseSystemError,
        LocationNotFoundError, GeocodingTimeoutError, EphemerisCalculationError.
    """
    if not date_str or not time_str:
        raise MissingBirthTimeError(
            "Se requiere fecha y hora exacta de nacimiento. Este motor no "
            "soporta cartas con hora desconocida en el MVP."
        )

    if house_system not in HOUSE_SYSTEMS:
        raise InvalidHouseSystemError(
            f"Sistema de casas '{house_system}' no soportado. "
            f"Opciones: {sorted(HOUSE_SYSTEMS)}."
        )

    if place_text:
        lat, lon, resolved_place_name = geocode_place(place_text)
    elif latitude is not None and longitude is not None:
        lat, lon, resolved_place_name = latitude, longitude, None
    else:
        raise ValueError(
            "Hay que pasar 'place_text' o bien 'latitude' y 'longitude'."
        )

    tz_name = resolve_timezone(lat, lon)
    local_dt, utc_dt = local_to_utc(date_str, time_str, tz_name)
    jd_ut = datetime_to_julian_day(utc_dt)

    if ephe_path:
        swe.set_ephe_path(ephe_path)
    use_swiss_ephe = bool(ephe_path)

    house_code = HOUSE_SYSTEMS[house_system]
    cusps, ascmc = calculate_houses(jd_ut, lat, lon, house_code)
    asc_longitude, mc_longitude = ascmc[0], ascmc[1]

    # --- planetas -----------------------------------------------------
    planets = []
    for planet_name, planet_code in PLANET_CODES.items():
        data = calculate_planet(jd_ut, planet_code, use_swiss_ephe=use_swiss_ephe)
        sign, sign_degree = longitude_to_sign(data["longitude"])
        planets.append({
            "name": planet_name,
            "longitude": data["longitude"],
            "latitude": data["latitude"],
            "distance_au": data["distance_au"],
            "speed_longitude": data["speed_longitude"],
            "retrograde": data["retrograde"],
            "sign": sign,
            "sign_degree": sign_degree,
            "house": find_house_of_longitude(data["longitude"], cusps),
        })

    # Nodo Sur: siempre exactamente opuesto al Nodo Norte, misma velocidad.
    north_node = next(p for p in planets if p["name"] == "North Node")
    south_longitude = (north_node["longitude"] + 180) % 360
    south_sign, south_sign_degree = longitude_to_sign(south_longitude)
    planets.append({
        "name": "South Node",
        "longitude": south_longitude,
        "latitude": -north_node["latitude"],
        "distance_au": north_node["distance_au"],
        "speed_longitude": north_node["speed_longitude"],
        "retrograde": north_node["retrograde"],
        "sign": south_sign,
        "sign_degree": south_sign_degree,
        "house": find_house_of_longitude(south_longitude, cusps),
    })

    # --- angulos (Asc, MC, Desc, IC) -----------------------------------
    asc_sign, asc_degree = longitude_to_sign(asc_longitude)
    mc_sign, mc_degree = longitude_to_sign(mc_longitude)
    desc_longitude = (asc_longitude + 180) % 360
    ic_longitude = (mc_longitude + 180) % 360
    desc_sign, desc_degree = longitude_to_sign(desc_longitude)
    ic_sign, ic_degree = longitude_to_sign(ic_longitude)

    angles = {
        "ascendant": {"longitude": asc_longitude, "sign": asc_sign, "sign_degree": asc_degree},
        "midheaven": {"longitude": mc_longitude, "sign": mc_sign, "sign_degree": mc_degree},
        "descendant": {"longitude": desc_longitude, "sign": desc_sign, "sign_degree": desc_degree},
        "imum_coeli": {"longitude": ic_longitude, "sign": ic_sign, "sign_degree": ic_degree},
    }

    # --- casas, con regente tradicional del signo en la cuspide --------
    houses = []
    for house_number in range(1, 13):
        cusp_longitude = cusps[house_number - 1]
        sign, sign_degree = longitude_to_sign(cusp_longitude)
        houses.append({
            "number": house_number,
            "cusp_longitude": cusp_longitude,
            "sign": sign,
            "sign_degree": sign_degree,
            "ruler": TRADITIONAL_RULERS[sign],
        })

    # --- aspectos: planetas + nodos + Ascendente + Medio Cielo ---------
    aspect_bodies = [
        AspectBody(name=p["name"], longitude=p["longitude"], speed_longitude=p["speed_longitude"])
        for p in planets
    ]
    if "Ascendant" in ANGLE_BODIES:
        aspect_bodies.append(AspectBody(name="Ascendant", longitude=asc_longitude, speed_longitude=0.0))
    if "Midheaven" in ANGLE_BODIES:
        aspect_bodies.append(AspectBody(name="Midheaven", longitude=mc_longitude, speed_longitude=0.0))
    aspects = compute_aspects(aspect_bodies, orbs=aspect_orbs)
    # North Node / South Node siempre estan en oposicion exacta por
    # construccion (South = North + 180): no es un aspecto real, es ruido
    # garantizado en cada carta. Se descarta igual que Asc-Desc / MC-IC.
    aspects = [
        a for a in aspects
        if {a["body_a"], a["body_b"]} != {"North Node", "South Node"}
    ]

    return {
        "meta": {
            "schema_version": SCHEMA_VERSION,
            "engine": {
                "ephemeris_source": "swiss" if use_swiss_ephe else "moshier",
                "zodiac_type": "tropical",
                "house_system": house_system,
            },
            "warnings": [],
        },
        "subject": {
            "name": name,
            "birth": {
                "input_date": date_str,
                "input_time": time_str,
                "local_datetime": local_dt.isoformat(),
                "utc_datetime": utc_dt.isoformat(),
                "timezone_name": tz_name,
                "utc_offset_hours": local_dt.utcoffset().total_seconds() / 3600,
                "dst_applied": bool(local_dt.dst()),
            },
            "place": {
                "input_text": place_text,
                "resolved_display_name": resolved_place_name,
                "latitude": lat,
                "longitude": lon,
            },
        },
        "settings": {
            "house_system": house_system,
            "zodiac_type": "tropical",
            "aspect_orbs_deg": {**DEFAULT_ASPECT_ORBS, **(aspect_orbs or {})},
        },
        "angles": angles,
        "houses": houses,
        "planets": planets,
        "aspects": aspects,
    }
