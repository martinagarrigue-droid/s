"""Resolucion de credenciales y construccion del cliente de Anthropic.

La API key se lee EXCLUSIVAMENTE de la variable de entorno ANTHROPIC_API_KEY
(o del parametro explicito api_key, para tests). Nunca se hardcodea ni se
pide por input().
"""

import os

import anthropic

from report_engine.exceptions import MissingAPIKeyError


def build_client(api_key: str | None = None) -> anthropic.Anthropic:
    """Crea el cliente de Anthropic.

    Args:
        api_key: si se pasa explicito, se usa ese valor (util para tests).
            Si no, se lee de la variable de entorno ANTHROPIC_API_KEY.

    Raises:
        MissingAPIKeyError: si no hay key disponible por ninguna via.
    """
    resolved_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
    if not resolved_key:
        raise MissingAPIKeyError(
            "No se encontro ANTHROPIC_API_KEY en el entorno. En Colab: "
            "import os; os.environ['ANTHROPIC_API_KEY'] = getpass('API key: ') "
            "-- nunca hardcodees la key en el notebook."
        )
    return anthropic.Anthropic(api_key=resolved_key)
