"""Motor de envío del informe completo por correo electrónico.

Separa el armado del mensaje (`build_message`, puro, testeable sin red)
del envío real (`send_report_email`, hace I/O vía smtplib) -- mismo
principio que el resto del proyecto (ver pdf_engine.html_builder vs.
pdf_engine.exporter).
"""

import os
import smtplib
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

SMTP_HOST = os.environ.get("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))

EMAIL_SUBJECT = "Sidérea · Tu Lectura Óptica Integral"
ATTACHMENT_FILENAME = "Siderea_Lectura_Optica.pdf"

PLAIN_BODY = (
    "La luz que te precede.\n\n"
    "Adjuntamos tu documento confidencial con la arquitectura de tu carta natal.\n\n"
    "Gracias por confiar en Sidérea."
)

HTML_BODY = """\
<div style="background:#F1EDE4;padding:48px 24px;font-family:'IBM Plex Mono',ui-monospace,monospace;color:#2A2622;">
  <div style="max-width:480px;margin:0 auto;text-align:center;">
    <p style="font-family:'Bodoni Moda',Didot,'Bodoni MT',serif;font-size:26px;color:#211D1A;margin:0 0 24px;">
      La luz que te precede.
    </p>
    <p style="font-size:13px;line-height:1.75;color:#5D5548;margin:0 0 8px;">
      Adjuntamos tu documento confidencial con la arquitectura de tu carta natal.
    </p>
    <p style="font-size:13px;line-height:1.75;color:#5D5548;margin:0;">
      Gracias por confiar en Sidérea.
    </p>
  </div>
</div>
"""


class EmailEngineError(Exception):
    """Fallo armando o enviando el correo con el informe."""


def build_message(sender: str, to_email: str, pdf_path: str) -> MIMEMultipart:
    """Arma el mensaje MIME completo (cuerpo + adjunto), sin tocar la red."""
    message = MIMEMultipart("mixed")
    message["Subject"] = EMAIL_SUBJECT
    message["From"] = sender
    message["To"] = to_email

    body = MIMEMultipart("alternative")
    body.attach(MIMEText(PLAIN_BODY, "plain", "utf-8"))
    body.attach(MIMEText(HTML_BODY, "html", "utf-8"))
    message.attach(body)

    pdf_bytes = Path(pdf_path).read_bytes()
    attachment = MIMEApplication(pdf_bytes, _subtype="pdf")
    attachment.add_header(
        "Content-Disposition", "attachment", filename=ATTACHMENT_FILENAME
    )
    message.attach(attachment)

    return message


def send_report_email(to_email: str, pdf_path: str) -> None:
    """Envía el informe adjunto por correo, vía SMTP con STARTTLS.

    Args:
        to_email: dirección del comprador.
        pdf_path: ruta local al PDF ya generado.

    Raises:
        EmailEngineError: si faltan credenciales o falla el envío.
    """
    sender = os.environ.get("SMTP_EMAIL")
    password = os.environ.get("SMTP_PASSWORD")
    if not sender or not password:
        raise EmailEngineError(
            "Faltan SMTP_EMAIL y/o SMTP_PASSWORD en el entorno -- no se puede "
            "enviar el informe por correo."
        )

    message = build_message(sender, to_email, pdf_path)

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=30) as server:
            server.starttls()
            server.login(sender, password)
            server.sendmail(sender, [to_email], message.as_string())
    except (smtplib.SMTPException, OSError) as exc:
        raise EmailEngineError(f"No se pudo enviar el correo a {to_email}: {exc}") from exc
