"""Resolucion de lugar de nacimiento: texto -> lat/long -> timezone."""

from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderServiceError, GeocoderUnavailable
from timezonefinder import TimezoneFinder

from natal_engine.exceptions import GeocodingTimeoutError, LocationNotFoundError

_GEOCODER_USER_AGENT = "natal_chart_engine_mvp"

# TimezoneFinder carga un indice geoespacial en memoria (varios MB) al
# construirse. Perezoso a proposito: si se instanciara a nivel de modulo,
# ese costo se pagaria al *importar* este archivo -- es decir, al arrancar
# el servidor, antes de que uvicorn llegue a bindear el puerto -- en vez de
# la primera vez que hace falta resolver una zona horaria. Se cachea en
# este global para seguir pagando el costo una sola vez por proceso.
_timezone_finder: TimezoneFinder | None = None


def _get_timezone_finder() -> TimezoneFinder:
    global _timezone_finder
    if _timezone_finder is None:
        _timezone_finder = TimezoneFinder()
    return _timezone_finder


def geocode_place(place_text: str, timeout: int = 10) -> tuple[float, float, str]:
    """Resuelve un texto de lugar a (latitud, longitud, nombre_resuelto).

    Lanza LocationNotFoundError si el geocoder no encuentra nada, y
    GeocodingTimeoutError si el servicio no responde o falla.
    """
    if not place_text or not place_text.strip():
        raise LocationNotFoundError("El lugar de nacimiento esta vacio.")

    geolocator = Nominatim(user_agent=_GEOCODER_USER_AGENT)
    try:
        location = geolocator.geocode(place_text, timeout=timeout)
    except (GeocoderTimedOut, GeocoderUnavailable) as exc:
        raise GeocodingTimeoutError(
            f"Timeout resolviendo el lugar '{place_text}': {exc}"
        ) from exc
    except GeocoderServiceError as exc:
        raise GeocodingTimeoutError(
            f"Servicio de geocoding fallo para '{place_text}': {exc}"
        ) from exc

    if location is None:
        raise LocationNotFoundError(
            f"No se encontro el lugar '{place_text}'. Proba con un formato "
            f"mas especifico (ej. 'Ciudad, Provincia, Pais') o ingresa "
            f"lat/long directo."
        )

    return location.latitude, location.longitude, location.address


def resolve_timezone(latitude: float, longitude: float) -> str:
    """Devuelve el nombre IANA de timezone (ej. 'America/Buenos_Aires')."""
    timezone_finder = _get_timezone_finder()
    tz_name = timezone_finder.timezone_at(lat=latitude, lng=longitude)
    if tz_name is None:
        # timezone_at puede devolver None en coordenadas oceanicas remotas.
        tz_name = timezone_finder.closest_timezone_at(lat=latitude, lng=longitude)
    if tz_name is None:
        raise LocationNotFoundError(
            f"No se pudo resolver timezone para lat={latitude}, lon={longitude}."
        )
    return tz_name
