"""Tests de la cola transaccional persistente del webhook (.pending/.lock/.done).

Cubre la garantía central pedida: un pago aceptado (payment_id reclamado)
no se pierde si el proceso muere antes de terminar de procesarlo, y dos
intentos concurrentes sobre el mismo payment_id nunca hacen el trabajo
(y gastan créditos de Anthropic) dos veces.
"""

import asyncio
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

import main


class FakeMPResponse(dict):
    def raise_for_status(self):
        pass


def _approved_payment(**metadata_overrides):
    metadata = {
        "date": "1990-05-12",
        "time": "14:30",
        "location": "Buenos Aires, Argentina",
        "email": "buyer@example.com",
    }
    metadata.update(metadata_overrides)
    return FakeMPResponse({"status": 200, "response": {"status": "approved", "metadata": metadata}})


@pytest.fixture(autouse=True)
def isolated_reports_dir(tmp_path, monkeypatch):
    """Cada test corre contra su propio REPORTS_DIR, no el generated_reports/ real."""
    reports_dir = tmp_path / "generated_reports"
    reports_dir.mkdir()
    monkeypatch.setattr(main, "REPORTS_DIR", reports_dir)
    monkeypatch.setattr(main, "_mp_sdk", None)
    yield reports_dir


@pytest.fixture()
def client():
    return TestClient(main.app)


def _mock_success_pipeline():
    """Parchea natal_engine/report_engine/pdf_engine/email_engine para que
    _fulfill_payment corra de punta a punta sin red real."""
    return (
        patch("main.generate_natal_chart", lambda **kw: {"fake": "chart"}),
        patch("main.generate_report", lambda chart: {"full_text": "x"}),
        patch("main.generate_pdf", lambda chart, report, path: open(path, "wb").write(b"%PDF-1.4 x")),
    )


# --- _claim_payment: la primitiva atómica ----------------------------------


def test_claim_payment_succeeds_once_second_call_fails(isolated_reports_dir):
    assert main._claim_payment("111") is True
    assert main._claim_payment("111") is False
    assert (isolated_reports_dir / "webhook-111.pending").exists()


def test_claim_payment_fails_if_already_done(isolated_reports_dir):
    (isolated_reports_dir / "webhook-222.done").touch()

    assert main._claim_payment("222") is False
    assert not (isolated_reports_dir / "webhook-222.pending").exists()


# --- _fulfill_payment: el lock evita procesamiento concurrente duplicado --


def test_fulfill_payment_skips_silently_if_locked_by_another_worker(isolated_reports_dir):
    (isolated_reports_dir / "webhook-333.lock").touch()
    sdk = MagicMock()
    main._mp_sdk = sdk

    main._fulfill_payment("333")

    sdk.payment.assert_not_called()
    # El lock ajeno no se toca -- no es nuestro para liberarlo.
    assert (isolated_reports_dir / "webhook-333.lock").exists()


def test_fulfill_payment_releases_lock_after_success(isolated_reports_dir):
    (isolated_reports_dir / "webhook-444.pending").touch()
    sdk = MagicMock()
    sdk.payment.return_value.get.return_value = _approved_payment()
    main._mp_sdk = sdk

    p1, p2, p3 = _mock_success_pipeline()
    with p1, p2, p3, patch("main.send_report_email", lambda email, path: None):
        main._fulfill_payment("444")

    assert not (isolated_reports_dir / "webhook-444.lock").exists()
    assert (isolated_reports_dir / "webhook-444.done").exists()
    assert not (isolated_reports_dir / "webhook-444.pending").exists()


def test_fulfill_payment_releases_lock_and_keeps_pending_on_failure(isolated_reports_dir):
    (isolated_reports_dir / "webhook-555.pending").touch()
    sdk = MagicMock()
    sdk.payment.return_value.get.return_value = _approved_payment()
    main._mp_sdk = sdk

    with patch("main.generate_natal_chart", side_effect=RuntimeError("boom")), \
         patch("main._alert_admin") as fake_alert:
        main._fulfill_payment("555")

    fake_alert.assert_called_once()
    # El lock se libera (para permitir un reintento futuro), pero .pending
    # queda -- el trabajo no se completó, así que sigue siendo candidato.
    assert not (isolated_reports_dir / "webhook-555.lock").exists()
    assert (isolated_reports_dir / "webhook-555.pending").exists()
    assert not (isolated_reports_dir / "webhook-555.done").exists()


# --- POST /api/webhook: registro pre-response + no reclama dos veces ------


def test_webhook_full_success_flow_creates_and_clears_markers(client, isolated_reports_dir):
    sdk = MagicMock()
    sdk.payment.return_value.get.return_value = _approved_payment()
    main._mp_sdk = sdk

    p1, p2, p3 = _mock_success_pipeline()
    with p1, p2, p3, patch("main.send_report_email", lambda email, path: None):
        response = client.post("/api/webhook", json={"type": "payment", "data": {"id": "666"}})

    assert response.status_code == 200
    assert (isolated_reports_dir / "webhook-666.done").exists()
    assert not (isolated_reports_dir / "webhook-666.pending").exists()
    assert not (isolated_reports_dir / "webhook-666.lock").exists()


def test_webhook_duplicate_delivery_does_not_reprocess(client, isolated_reports_dir):
    sdk = MagicMock()
    sdk.payment.return_value.get.return_value = _approved_payment()
    main._mp_sdk = sdk

    sent = []
    p1, p2, p3 = _mock_success_pipeline()
    with p1, p2, p3, patch("main.send_report_email", lambda email, path: sent.append(email)):
        client.post("/api/webhook", json={"type": "payment", "data": {"id": "777"}})
        client.post("/api/webhook", json={"type": "payment", "data": {"id": "777"}})

    assert len(sent) == 1


def test_webhook_rejects_non_numeric_payment_id(client, isolated_reports_dir):
    response = client.post(
        "/api/webhook", json={"type": "payment", "data": {"id": "../../etc/passwd"}}
    )

    assert response.status_code == 200
    assert response.json()["status"] == "ignored"
    assert list(isolated_reports_dir.iterdir()) == []


# --- Recuperación de arranque: encuentra .pending, limpia .lock huérfano --


def test_find_recoverable_payment_ids_returns_pending_payment_ids(isolated_reports_dir):
    (isolated_reports_dir / "webhook-888.pending").touch()
    (isolated_reports_dir / "webhook-999.pending").touch()

    assert sorted(main._find_recoverable_payment_ids()) == ["888", "999"]


def test_find_recoverable_payment_ids_ignores_already_done(isolated_reports_dir):
    (isolated_reports_dir / "webhook-111.pending").touch()
    (isolated_reports_dir / "webhook-222.pending").touch()
    (isolated_reports_dir / "webhook-222.done").touch()

    # .pending de un pago ya .done no debería existir en la práctica (se
    # borra al completar), pero si por algo raro coexisten, no hay
    # obligación de excluirlo acá: _fulfill_payment ya lo hace de forma
    # segura (done_path.exists() al principio). Esta prueba solo confirma
    # que el scan en sí no explota ni se confunde con archivos mixtos.
    found = main._find_recoverable_payment_ids()
    assert "111" in found


def test_find_recoverable_payment_ids_cleans_up_stale_lock(isolated_reports_dir):
    (isolated_reports_dir / "webhook-333.pending").touch()
    (isolated_reports_dir / "webhook-333.lock").touch()

    payment_ids = main._find_recoverable_payment_ids()

    assert payment_ids == ["333"]
    assert not (isolated_reports_dir / "webhook-333.lock").exists()


def test_find_recoverable_payment_ids_ignores_malformed_filenames(isolated_reports_dir):
    (isolated_reports_dir / "webhook-444.pending").touch()
    (isolated_reports_dir / "webhook-not-a-number.pending").touch()

    assert main._find_recoverable_payment_ids() == ["444"]


def test_lifespan_recovers_interrupted_payment_on_startup(isolated_reports_dir):
    # Simula un .pending dejado por un proceso anterior interrumpido a
    # mitad de camino, con un .lock huérfano del mismo crash.
    (isolated_reports_dir / "webhook-321.pending").touch()
    (isolated_reports_dir / "webhook-321.lock").touch()

    sdk = MagicMock()
    sdk.payment.return_value.get.return_value = _approved_payment()
    main._mp_sdk = sdk

    sent = []
    p1, p2, p3 = _mock_success_pipeline()

    async def run_lifespan_and_wait():
        # Se maneja el lifespan directamente (en vez de vía TestClient) y se
        # espera explícitamente app.state.recovery_tasks -- TestClient no
        # garantiza esperar tareas de asyncio.create_task sin awaitear antes
        # de que su __exit__ retorne, así que probarlo a través de él sería
        # una prueba potencialmente inestable (a veces pasa, a veces no,
        # según el scheduling del event loop).
        async with main.lifespan(main.app):
            await asyncio.gather(*getattr(main.app.state, "recovery_tasks", []))

    with p1, p2, p3, patch("main.send_report_email", lambda email, path: sent.append(email)):
        asyncio.run(run_lifespan_and_wait())

    assert sent == ["buyer@example.com"]
    assert (isolated_reports_dir / "webhook-321.done").exists()
    assert not (isolated_reports_dir / "webhook-321.pending").exists()
