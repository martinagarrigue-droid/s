"""Tests del armado del mensaje de entrega por mail (sin tocar smtplib)."""

import pytest

from email_engine import (
    ATTACHMENT_FILENAME,
    EMAIL_SUBJECT,
    EmailEngineError,
    build_message,
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
