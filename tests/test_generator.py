"""Tests del orquestador de la Etapa 2, con un cliente de Anthropic mockeado.

Ningun test de este archivo llama a la API real -- se inyecta un cliente
falso via el parametro `client=` de generate_report / _generate_section_text.
"""

from types import SimpleNamespace

import anthropic
import httpx
import pytest

from natal_engine.chart import generate_natal_chart
from report_engine.config import SECTIONS
from report_engine.exceptions import LLMGenerationError, LLMRefusalError, MissingAPIKeyError
from report_engine.generator import _generate_section_text, generate_report

TEST_KWARGS = dict(
    name="Persona de Prueba",
    date_str="1990-05-14",
    time_str="14:32",
    latitude=-34.6037,
    longitude=-58.3816,
)


@pytest.fixture(scope="module")
def chart():
    return generate_natal_chart(**TEST_KWARGS)


@pytest.fixture(autouse=True)
def no_real_sleep(monkeypatch):
    """Los tests de reintentos no deben esperar el backoff exponencial de verdad."""
    monkeypatch.setattr("report_engine.generator.time.sleep", lambda _seconds: None)


# --- helpers para simular respuestas del SDK sin red -----------------------

_DUMMY_REQUEST = httpx.Request("POST", "https://api.anthropic.com/v1/messages")


def make_response(text="Texto generado.", stop_reason="end_turn", category=None,
                   input_tokens=100, output_tokens=50, cache_read=20, cache_creation=0):
    block = SimpleNamespace(type="text", text=text)
    usage = SimpleNamespace(
        input_tokens=input_tokens, output_tokens=output_tokens,
        cache_read_input_tokens=cache_read, cache_creation_input_tokens=cache_creation,
    )
    stop_details = SimpleNamespace(category=category) if category else None
    return SimpleNamespace(stop_reason=stop_reason, content=[block], usage=usage, stop_details=stop_details)


def rate_limit_error():
    response = httpx.Response(status_code=429, request=_DUMMY_REQUEST)
    return anthropic.RateLimitError("rate limited", response=response, body=None)


def server_error():
    response = httpx.Response(status_code=500, request=_DUMMY_REQUEST)
    return anthropic.APIStatusError("server error", response=response, body=None)


def bad_request_error():
    response = httpx.Response(status_code=400, request=_DUMMY_REQUEST)
    return anthropic.APIStatusError("bad request", response=response, body=None)


class FakeStream:
    def __init__(self, response):
        self._response = response

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return False

    def get_final_message(self):
        return self._response


class FakeMessages:
    """factory(call_index, kwargs) -> response objeto, o una excepcion para lanzar."""

    def __init__(self, factory):
        self.calls = []
        self._factory = factory

    def stream(self, **kwargs):
        index = len(self.calls)
        self.calls.append(kwargs)
        result = self._factory(index, kwargs)
        if isinstance(result, BaseException):
            raise result
        return FakeStream(result)


class FakeClient:
    def __init__(self, factory):
        self.messages = FakeMessages(factory)


# --- _generate_section_text -------------------------------------------------

def test_generate_section_success_returns_text_and_usage():
    client = FakeClient(lambda i, kw: make_response(text="Analisis del Sol."))
    text, usage = _generate_section_text(client, [], "directiva", "claude-opus-4-8", "high", 8000, "test_section")
    assert text == "Analisis del Sol."
    assert usage["input_tokens"] == 100
    assert usage["cache_read_input_tokens"] == 20
    assert len(client.messages.calls) == 1


def test_generate_section_retries_on_rate_limit_then_succeeds():
    responses = [rate_limit_error(), rate_limit_error(), make_response(text="OK tras reintentos.")]
    client = FakeClient(lambda i, kw: responses[i])
    text, _usage = _generate_section_text(client, [], "d", "claude-opus-4-8", "high", 8000, "s")
    assert text == "OK tras reintentos."
    assert len(client.messages.calls) == 3


def test_generate_section_retries_on_server_error_then_succeeds():
    responses = [server_error(), make_response(text="OK tras 500.")]
    client = FakeClient(lambda i, kw: responses[i])
    text, _usage = _generate_section_text(client, [], "d", "claude-opus-4-8", "high", 8000, "s")
    assert text == "OK tras 500."
    assert len(client.messages.calls) == 2


def test_generate_section_client_error_fails_immediately_no_retry():
    client = FakeClient(lambda i, kw: bad_request_error())
    with pytest.raises(LLMGenerationError):
        _generate_section_text(client, [], "d", "claude-opus-4-8", "high", 8000, "s")
    assert len(client.messages.calls) == 1


def test_generate_section_raises_after_exhausting_retries():
    client = FakeClient(lambda i, kw: rate_limit_error())
    with pytest.raises(LLMGenerationError):
        _generate_section_text(client, [], "d", "claude-opus-4-8", "high", 8000, "s", max_retries=2)
    assert len(client.messages.calls) == 2


def test_generate_section_raises_llm_refusal_error():
    client = FakeClient(lambda i, kw: make_response(stop_reason="refusal", category="cyber"))
    with pytest.raises(LLMRefusalError, match="cyber"):
        _generate_section_text(client, [], "d", "claude-opus-4-8", "high", 8000, "s")
    assert len(client.messages.calls) == 1


def test_generate_section_retries_on_empty_text_response():
    responses = [make_response(text="   "), make_response(text="Contenido real.")]
    client = FakeClient(lambda i, kw: responses[i])
    text, _usage = _generate_section_text(client, [], "d", "claude-opus-4-8", "high", 8000, "s")
    assert text == "Contenido real."
    assert len(client.messages.calls) == 2


# --- generate_report ---------------------------------------------------------

def test_generate_report_calls_one_request_per_section(chart):
    client = FakeClient(lambda i, kw: make_response(text=f"Seccion {i}"))
    report = generate_report(chart, client=client)
    assert len(client.messages.calls) == len(SECTIONS)
    assert len(report["sections"]) == len(SECTIONS)
    assert [s["key"] for s in report["sections"]] == [s["key"] for s in SECTIONS]


def test_generate_report_full_text_includes_all_titles_as_headers(chart):
    client = FakeClient(lambda i, kw: make_response(text="contenido"))
    report = generate_report(chart, client=client)
    for section in SECTIONS:
        assert f"## {section['title']}" in report["full_text"]


def test_generate_report_aggregates_usage_across_sections(chart):
    client = FakeClient(lambda i, kw: make_response(input_tokens=100, output_tokens=50, cache_read=20))
    report = generate_report(chart, client=client)
    n = len(SECTIONS)
    assert report["usage"]["input_tokens"] == 100 * n
    assert report["usage"]["output_tokens"] == 50 * n
    assert report["usage"]["cache_read_input_tokens"] == 20 * n


def test_generate_report_reuses_same_cached_system_blocks_every_call(chart):
    client = FakeClient(lambda i, kw: make_response())
    generate_report(chart, client=client)
    system_blocks_per_call = [kw["system"] for kw in client.messages.calls]
    first = system_blocks_per_call[0]
    assert all(blocks == first for blocks in system_blocks_per_call)
    assert len(first) == 2
    assert first[0]["cache_control"] == {"type": "ephemeral"}
    assert first[1]["cache_control"] == {"type": "ephemeral"}
    assert "Persona de Prueba" in first[1]["text"]


def test_generate_report_passes_model_and_effort_through(chart):
    client = FakeClient(lambda i, kw: make_response())
    generate_report(chart, client=client, model="claude-sonnet-5", effort="medium")
    for kw in client.messages.calls:
        assert kw["model"] == "claude-sonnet-5"
        assert kw["output_config"] == {"effort": "medium"}
        assert kw["thinking"] == {"type": "adaptive"}


def test_generate_report_without_client_or_key_raises_missing_api_key(chart, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with pytest.raises(MissingAPIKeyError):
        generate_report(chart)


def test_generate_report_propagates_refusal_from_any_section(chart):
    def factory(i, kw):
        if i == 2:
            return make_response(stop_reason="refusal", category="bio")
        return make_response()

    client = FakeClient(factory)
    with pytest.raises(LLMRefusalError):
        generate_report(chart, client=client)
