import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from app.config import EMAIL_FROM, SMTP_HOST, SMTP_PASS, SMTP_PORT, SMTP_USER


def enviar_email(destinatario: str, assunto: str, corpo_html: str) -> None:
    """Envia e-mail via SMTP com TLS. Lança exceção se SMTP não estiver configurado."""
    if not SMTP_HOST or not SMTP_USER:
        raise RuntimeError("SMTP não configurado. Defina SMTP_HOST e SMTP_USER no .env")

    msg = MIMEMultipart("alternative")
    msg["Subject"] = assunto
    msg["From"] = EMAIL_FROM
    msg["To"] = destinatario
    msg.attach(MIMEText(corpo_html, "html", "utf-8"))

    ctx = ssl.create_default_context()
    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as smtp:
        smtp.ehlo()
        smtp.starttls(context=ctx)
        smtp.login(SMTP_USER, SMTP_PASS)
        smtp.sendmail(SMTP_USER, destinatario, msg.as_string())
