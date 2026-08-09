"""Excepciones especificas del motor de carta natal.

Se separan por causa raiz para que el llamador (API, notebook, etc.) pueda
distinguir errores de usuario (lugar mal escrito, falta la hora) de errores
de infraestructura (timeout de geocoding, fallo del calculo efemeride).
"""


class NatalChartError(Exception):
    """Excepcion base del motor. Nunca se lanza directamente."""


class LocationNotFoundError(NatalChartError):
    """El geocoder no pudo resolver el texto de lugar a coordenadas."""


class GeocodingTimeoutError(NatalChartError):
    """El servicio de geocoding no respondio a tiempo o fallo."""


class MissingBirthTimeError(NatalChartError):
    """Falta fecha u hora exacta de nacimiento.

    En este MVP no se soporta un fallback automatico (ej. mediodia) porque
    distorsiona Ascendente/casas sin avisar. Se exige el dato explicito.
    """


class InvalidHouseSystemError(NatalChartError):
    """El sistema de casas solicitado no esta soportado."""


class InvalidDateTimeError(NatalChartError):
    """La fecha/hora de nacimiento no tiene un formato valido."""


class EphemerisCalculationError(NatalChartError):
    """Fallo interno del calculo de swisseph (posiciones, casas, etc.)."""
