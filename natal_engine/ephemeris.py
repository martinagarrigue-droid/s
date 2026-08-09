"""Calculos astronomicos puros: fecha/hora -> Julian Day -> posiciones.

Este modulo no sabe nada de LLMs ni de PDFs. Su unico trabajo es producir
numeros astronomicos correctos a partir de un instante y un lugar.
"""

from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import swisseph as swe

from natal_engine.config import ZODIAC_SIGNS, MOSHIER_FLAG, SWISS_EPHE_FLAG
from natal_engine.exceptions import EphemerisCalculationError, InvalidDateTimeError


def local_to_utc(date_str: str, time_str: str, tz_name: str) -> tuple[datetime, datetime]:
    """Combina fecha+hora local con un timezone IANA y devuelve (local, utc).

    date_str: 'YYYY-MM-DD'. time_str: 'HH:MM' o 'HH:MM:SS'.
    """
    fmt = "%Y-%m-%d %H:%M:%S" if time_str.count(":") == 2 else "%Y-%m-%d %H:%M"
    try:
        naive_dt = datetime.strptime(f"{date_str} {time_str}", fmt)
    except ValueError as exc:
        raise InvalidDateTimeError(
            f"Fecha/hora invalida: date='{date_str}' time='{time_str}'. "
            f"Formato esperado: 'YYYY-MM-DD' y 'HH:MM' (o 'HH:MM:SS')."
        ) from exc

    try:
        tz = ZoneInfo(tz_name)
    except ZoneInfoNotFoundError as exc:
        raise InvalidDateTimeError(f"Timezone desconocido: '{tz_name}'.") from exc

    local_dt = naive_dt.replace(tzinfo=tz)
    utc_dt = local_dt.astimezone(ZoneInfo("UTC"))
    return local_dt, utc_dt


def datetime_to_julian_day(utc_dt: datetime) -> float:
    """Convierte un datetime UTC a Julian Day (UT1) para usar con swisseph."""
    try:
        _jd_et, jd_ut = swe.utc_to_jd(
            utc_dt.year, utc_dt.month, utc_dt.day,
            utc_dt.hour, utc_dt.minute, utc_dt.second + utc_dt.microsecond / 1e6,
            swe.GREG_CAL,
        )
    except swe.Error as exc:
        raise EphemerisCalculationError(f"No se pudo calcular Julian Day: {exc}") from exc
    return jd_ut


def longitude_to_sign(longitude: float) -> tuple[str, float]:
    """Longitud eclipse absoluta (0-360) -> (nombre de signo, grado 0-30)."""
    longitude = longitude % 360
    sign_index = int(longitude // 30)
    sign_degree = longitude - (sign_index * 30)
    return ZODIAC_SIGNS[sign_index], sign_degree


def find_house_of_longitude(longitude: float, cusps: tuple[float, ...]) -> int:
    """Determina en que casa (1-12) cae una longitud, dados los 12 cusps.

    cusps[i] es la cuspide de la casa i+1. Maneja el caso en que una casa
    "cruza" los 0 grados (ej. cuspide 11 en 350 y cuspide 12 en 20).
    """
    longitude = longitude % 360
    for i in range(12):
        start = cusps[i] % 360
        end = cusps[(i + 1) % 12] % 360
        if start <= end:
            if start <= longitude < end:
                return i + 1
        else:
            if longitude >= start or longitude < end:
                return i + 1
    # No deberia ocurrir: los 12 cusps siempre cubren el circulo completo.
    raise EphemerisCalculationError(
        f"No se pudo asignar casa para longitud {longitude}."
    )


def calculate_planet(jd_ut: float, planet_code: int, use_swiss_ephe: bool = False) -> dict:
    """Calcula posicion/velocidad de un cuerpo en un instante dado.

    Por defecto usa el efemeride Moshier (semi-analitico, embebido en
    pyswisseph, sin archivos externos) -- suficiente para uso astrologico
    (~1 arcsegundo de precision) y funciona out-of-the-box en Colab. Si se
    llamo antes a swe.set_ephe_path(...) con archivos .se1 disponibles,
    use_swiss_ephe=True usa el efemeride Swiss de mayor precision.
    """
    flag = SWISS_EPHE_FLAG if use_swiss_ephe else MOSHIER_FLAG
    try:
        xx, _ret_flag = swe.calc_ut(jd_ut, planet_code, flag)
    except swe.Error as exc:
        raise EphemerisCalculationError(
            f"Fallo swe.calc_ut para el cuerpo {planet_code}: {exc}"
        ) from exc

    longitude, latitude, distance_au, speed_longitude, speed_latitude, speed_distance = xx
    return {
        "longitude": longitude,
        "latitude": latitude,
        "distance_au": distance_au,
        "speed_longitude": speed_longitude,
        "retrograde": speed_longitude < 0,
    }


def calculate_houses(
    jd_ut: float, latitude: float, longitude: float, house_system_code: bytes
) -> tuple[tuple[float, ...], tuple[float, ...]]:
    """Devuelve (cusps, ascmc). cusps[0..11] = casas 1-12.

    ascmc[0] = Ascendente, ascmc[1] = Medio Cielo (resto de indices no se
    usan en este MVP: ARMC, Vertex, etc.)
    """
    try:
        cusps, ascmc = swe.houses(jd_ut, latitude, longitude, house_system_code)
    except swe.Error as exc:
        raise EphemerisCalculationError(
            f"Fallo swe.houses (lat={latitude}, lon={longitude}): {exc}"
        ) from exc
    return cusps, ascmc
