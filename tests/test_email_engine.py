"""Tests del armado del mensaje de entrega por mail (sin tocar smtplib)."""

import pytest

from email_engine import (
    ATTACHMENT_FILENAME,
    EMAIL_SUBJECT,
    EmailEngineError,
    build_admin_alert_message,
    build_message,
    send_admin_alert_email,
    send_report_email,
)


@pytest.fixture()
def fake_pdf(tmp_path):
    pdf_path = tmp_path / "informe.pdf"
    pdf_path.write_bytes(b"%PDF-1.4 contenido de prueba")
    return str(pdf_path)


def test_build_message_has_subject_and_recipients(fake_pdf):
    message = build_message("sender@siderea.com", "comprador@example.com", fake_pdf)
    assert message["Subject"] == EMAIL_SUBJECT
    assert message["From"] == "sender@siderea.com"
    assert message["To"] == "comprador@example.com"


def test_build_message_includes_plain_and_html_bodies(fake_pdf):
    message = build_message("sender@siderea.com", "comprador@example.com", fake_pdf)

    plain_parts = [p for p in message.walk() if p.get_content_type() == "text/plain"]
    html_parts = [p for p in message.walk() if p.get_content_type() == "text/html"]

    assert len(plain_parts) == 1
    assert len(html_parts) == 1
    assert "La luz que te precede" in plain_parts[0].get_payload(decode=True).decode("utf-8")
    assert "Gracias por confiar en Sidérea" in html_parts[0].get_payload(decode=True).decode("utf-8")


def test_build_message_attaches_pdf_with_expected_filename(fake_pdf):
    message = build_message("sender@siderea.com", "comprador@example.com", fake_pdf)

    attachments = [p for p in message.walk() if p.get_content_type() == "application/pdf"]
    assert len(attachments) == 1
    assert attachments[0].get_filename() == ATTACHMENT_FILENAME
    assert attachments[0].get_payload(decode=True) == b"%PDF-1.4 contenido de prueba"


def test_send_report_email_raises_without_credentials(fake_pdf, monkeypatch):
    monkeypatch.delenv("SMTP_EMAIL", raising=False)
    monkeypatch.delenv("SMTP_PASSWORD", raising=False)

    with pytest.raises(EmailEngineError):
        send_report_email("comprador@example.com", fake_pdf)


def test_send_report_email_wraps_missing_pdf_as_email_engine_error(tmp_path, monkeypatch):
    # build_message() debe vivir dentro del try/except de send_report_email:
    # si el PDF no existe en disco, el llamador solo debería ver
    # EmailEngineError, nunca un FileNotFoundError/OSError crudo.
    monkeypatch.setenv("SMTP_EMAIL", "sender@siderea.com")
    monkeypatch.setenv("SMTP_PASSWORD", "fake-password")

    missing_pdf = str(tmp_path / "no-existe.pdf")

    with pytest.raises(EmailEngineError):
        send_report_email("comprador@example.com", missing_pdf)


def test_build_admin_alert_message_goes_to_the_admin_itself():
    message = build_admin_alert_message(
        "admin@siderea.com", "pay-123", "comprador@example.com", "pdf_engine_weasyprint",
        RuntimeError("boom"),
    )
    assert message["From"] == "admin@siderea.com"
    assert message["To"] == "admin@siderea.com"
    assert "pay-123" in message["Subject"]


def test_build_admin_alert_message_includes_diagnostic_details():
    message = build_admin_alert_message(
        "admin@siderea.com", "pay-123", "comprador@example.com", "pdf_engine_weasyprint",
        RuntimeError("boom"),
    )
    body = message.get_payload(decode=True).decode("utf-8")
    assert "pay-123" in body
    assert "comprador@example.com" in body
    assert "pdf_engine_weasyprint" in body
    assert "RuntimeError" in body
    assert "boom" in body


def test_send_admin_alert_email_raises_without_credentials(monkeypatch):
    monkeypatch.delenv("SMTP_EMAIL", raising=False)
    monkeypatch.delenv("SMTP_PASSWORD", raising=False)

    with pytest.raises(EmailEngineError):
        send_admin_alert_email("pay-123", "comprador@example.com", "natal_engine", RuntimeError("boom"))
