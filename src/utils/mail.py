from fastapi_mail import (
    ConnectionConfig,
    FastMail,
    MessageSchema,
    MessageType,
)
from pydantic import SecretStr
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


async def send_email(emails: list[str]) -> JSONResponse:
    html = """<p>Hi, Thanks for Registration. Our team will contact you soon.</p>"""
    message = MessageSchema(
        subject="Registeration Confirmation",
        recipients=emails,
        body=html,
        subtype=MessageType.html,
    )
    await FastMail(conf).send_message(message)
    return JSONResponse(status_code=200, content={"message": "email has been sent"})
