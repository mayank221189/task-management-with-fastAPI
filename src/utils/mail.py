from html import escape
from urllib.parse import quote

from fastapi_mail import (
    ConnectionConfig,
    FastMail,
    MessageSchema,
    MessageType,
)
from pydantic import NameEmail, SecretStr
from starlette.responses import JSONResponse

from src.utils.settings import settings

conf = ConnectionConfig(
    MAIL_USERNAME=settings.MAIL_USERNAME,
    MAIL_PASSWORD=SecretStr(settings.MAIL_PASSWORD),
    MAIL_FROM=settings.MAIL_FROM,
    MAIL_PORT=settings.MAIL_PORT,
    MAIL_SERVER=settings.MAIL_SERVER,
    MAIL_STARTTLS=False,
    MAIL_SSL_TLS=True,
    USE_CREDENTIALS=True,
    VALIDATE_CERTS=True,
)


async def send_email(emails: list[str], first_name: str | None = None) -> JSONResponse:
    greeting_name = escape(first_name) if first_name else "there"
    support_email = escape(quote(settings.MAIL_FROM, safe="@.+-_"), quote=True)
    html = f"""\
    <!doctype html>
    <html lang="en">
      <body style="margin:0;padding:24px;background-color:#f3f6fb;font-family:Arial,sans-serif;color:#172033;">
        <main style="max-width:600px;margin:0 auto;background:#ffffff;border-radius:12px;overflow:hidden;">
          <header style="padding:32px;background:#2447a8;color:#ffffff;">
            <p style="margin:0 0 8px;font-size:13px;letter-spacing:1px;text-transform:uppercase;">Task Management</p>
            <h1 style="margin:0;font-size:28px;">Welcome aboard, {greeting_name}!</h1>
          </header>
          <section style="padding:28px 32px;">
            <p style="margin-top:0;font-size:16px;line-height:1.6;">
              Your registration is complete. You can now organize your work and keep track of what needs to get done.
            </p>
            <h2 style="font-size:18px;">Get started</h2>
            <ol style="padding-left:22px;line-height:1.8;">
              <li>Sign in to your Task Management account.</li>
              <li>Create a task for something you want to accomplish.</li>
              <li>Update its status as you make progress.</li>
            </ol>
            <p style="margin:24px 0 0;padding:16px;background:#eef3ff;border-radius:8px;line-height:1.6;">
              <strong>Need a hand?</strong> Our team is happy to help.
              <a href="mailto:{support_email}" style="color:#2447a8;font-weight:bold;">Reply to our team</a>.
            </p>
          </section>
          <footer style="padding:18px 32px;background:#f8f9fc;color:#68738a;font-size:12px;">
            Thanks for joining us. We look forward to helping you stay organized.
          </footer>
        </main>
      </body>
    </html>
    """
    message = MessageSchema(
        subject="Welcome to Task Management",
        recipients=[NameEmail(email, email) for email in emails],
        body=html,
        subtype=MessageType.html,
    )
    await FastMail(conf).send_message(message)
    return JSONResponse(status_code=200, content={"message": "email has been sent"})
