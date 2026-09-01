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

    client_kwargs = {"api_key": resolved_key}

    # Las Personal API Keys de una cuenta con multiples workspaces requieren
    # este header para que Anthropic sepa contra que workspace facturar la
    # llamada -- sin el, la API devuelve 400. Opcional: si no esta seteada,
    # el cliente se comporta como antes.
    workspace_id = os.environ.get("ANTHROPIC_WORKSPACE_ID")
    if workspace_id:
        client_kwargs["default_headers"] = {"anthropic-workspace-id": workspace_id}

    return anthropic.Anthropic(**client_kwargs)
