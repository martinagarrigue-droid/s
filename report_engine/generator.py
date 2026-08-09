"""Orquestador de la Etapa 2: genera el informe completo, seccion por seccion.

Cada seccion es una llamada independiente a Claude. Esto evita el truncamiento
que aparece al pedir un informe de 10-15 paginas en una sola respuesta, y
permite reintentar una sola seccion sin regenerar el informe entero.

El bloque de datos natales (grande, identico en las N llamadas de un mismo
informe) va en el system prompt con cache_control -- se paga una vez por
informe, no una vez por seccion.
"""

import time

import anthropic

from report_engine.client import build_client
from report_engine.config import (
    DEFAULT_EFFORT,
    DEFAULT_MAX_TOKENS_PER_SECTION,
    DEFAULT_MODEL,
    SECTIONS,
    SYSTEM_TONE_INSTRUCTIONS,
)
from report_engine.exceptions import LLMGenerationError, LLMRefusalError
from report_engine.prompt_builder import build_section_user_message, format_natal_summary

MAX_RETRIES_PER_SECTION = 3
_BASE_BACKOFF_SECONDS = 2


def _sleep_backoff(attempt: int) -> None:
    time.sleep(min(_BASE_BACKOFF_SECONDS ** attempt, 30))


def _empty_usage() -> dict:
    return {
        "input_tokens": 0,
        "output_tokens": 0,
        "cache_read_input_tokens": 0,
        "cache_creation_input_tokens": 0,
    }


def _generate_section_text(
    client: anthropic.Anthropic,
    system_blocks: list,
    user_message: str,
    model: str,
    effort: str,
    max_tokens: int,
    section_key: str,
    max_retries: int = MAX_RETRIES_PER_SECTION,
) -> tuple[str, dict]:
    """Llama a la API para una seccion, con reintentos en errores retryables."""
    last_exception: Exception | None = None

    for attempt in range(1, max_retries + 1):
        try:
            with client.messages.stream(
                model=model,
                max_tokens=max_tokens,
                system=system_blocks,
                thinking={"type": "adaptive"},
                output_config={"effort": effort},
                messages=[{"role": "user", "content": user_message}],
            ) as stream:
                response = stream.get_final_message()
        except anthropic.RateLimitError as exc:
            last_exception = exc
            _sleep_backoff(attempt)
            continue
        except anthropic.APIConnectionError as exc:
            last_exception = exc
            _sleep_backoff(attempt)
            continue
        except anthropic.APIStatusError as exc:
            if exc.status_code >= 500:
                last_exception = exc
                _sleep_backoff(attempt)
                continue
            raise LLMGenerationError(
                f"Error de la API generando la seccion '{section_key}': {exc}"
            ) from exc

        if response.stop_reason == "refusal":
            category = getattr(response.stop_details, "category", None)
            raise LLMRefusalError(
                f"El modelo rechazo generar la seccion '{section_key}' "
                f"(categoria: {category})."
            )

        text = "".join(block.text for block in response.content if block.type == "text").strip()
        if not text:
            last_exception = LLMGenerationError(
                f"Respuesta vacia para la seccion '{section_key}' (stop_reason={response.stop_reason})."
            )
            continue

        usage = {
            "input_tokens": response.usage.input_tokens,
            "output_tokens": response.usage.output_tokens,
            "cache_read_input_tokens": getattr(response.usage, "cache_read_input_tokens", 0) or 0,
            "cache_creation_input_tokens": getattr(response.usage, "cache_creation_input_tokens", 0) or 0,
        }
        return text, usage

    raise LLMGenerationError(
        f"No se pudo generar la seccion '{section_key}' despues de "
        f"{max_retries} intentos. Ultimo error: {last_exception}"
    ) from last_exception


def generate_report(
    chart: dict,
    api_key: str | None = None,
    model: str = DEFAULT_MODEL,
    effort: str = DEFAULT_EFFORT,
    max_tokens_per_section: int = DEFAULT_MAX_TOKENS_PER_SECTION,
    max_retries_per_section: int = MAX_RETRIES_PER_SECTION,
    client: anthropic.Anthropic | None = None,
) -> dict:
    """Genera el informe completo a partir del JSON de la Etapa 1.

    Args:
        chart: dict devuelto por natal_engine.generate_natal_chart().
        api_key: opcional, ver report_engine.client.build_client.
        model: id de modelo de Claude (default: claude-opus-4-8).
        effort: nivel de esfuerzo/razonamiento ('low'..'max').
        max_tokens_per_section: limite de output por seccion.
        max_retries_per_section: reintentos ante errores retryables (429/5xx).
        client: cliente de anthropic.Anthropic ya construido (para tests /
            para reusar un cliente entre varios informes).

    Returns:
        dict con 'sections' (lista ordenada {key, title, text}), 'full_text'
        (informe completo concatenado, listo para la Etapa 3), 'model' y
        'usage' (tokens totales, agregado de todas las secciones).
    """
    active_client = client or build_client(api_key)
    natal_summary = format_natal_summary(chart)

    system_blocks = [
        {
            "type": "text",
            "text": SYSTEM_TONE_INSTRUCTIONS,
            "cache_control": {"type": "ephemeral"},
        },
        {
            "type": "text",
            "text": natal_summary,
            "cache_control": {"type": "ephemeral"},
        },
    ]

    sections_out = []
    total_usage = _empty_usage()

    for section in SECTIONS:
        user_message = build_section_user_message(section, chart)
        text, usage = _generate_section_text(
            active_client,
            system_blocks,
            user_message,
            model,
            effort,
            max_tokens_per_section,
            section["key"],
            max_retries=max_retries_per_section,
        )
        sections_out.append({"key": section["key"], "title": section["title"], "text": text})
        for field in total_usage:
            total_usage[field] += usage[field]

    full_text = "\n\n".join(
        f"## {s['title']}\n\n{s['text']}" for s in sections_out
    )

    return {
        "subject_name": chart["subject"]["name"],
        "model": model,
        "sections": sections_out,
        "full_text": full_text,
        "usage": total_usage,
    }
