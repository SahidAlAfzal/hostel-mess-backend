from fastapi_mail import FastMail, MessageSchema, ConnectionConfig
from pydantic import EmailStr
from typing import List
from config import settings # Import our settings

# Setup the connection configuration using our settings
conf = ConnectionConfig(
    MAIL_USERNAME=settings.MAIL_USERNAME,
    MAIL_PASSWORD=settings.MAIL_PASSWORD, # type: ignore
    MAIL_FROM=settings.MAIL_FROM,
    MAIL_PORT=settings.MAIL_PORT,
    MAIL_SERVER=settings.MAIL_SERVER,
    MAIL_FROM_NAME=settings.MAIL_FROM_NAME,
    MAIL_STARTTLS=True,
    MAIL_SSL_TLS=False,
    USE_CREDENTIALS=True,
    VALIDATE_CERTS=True
)

async def send_verification_email(email: EmailStr, name: str, token: str):
    """
    Sends the account verification email to a new user.
    """
    # This is a simple HTML template for the email body.
    # In a real app, you would use a more robust templating engine like Jinja2.
    html = f"""
    <html>
    <body>
        <p>Hi {name},</p>
        <p>Thanks for registering for the Hostel Mess App! Please click the link below to verify your email address and activate your account:</p>
        <a href="http://127.0.0.1:8000/auth/verifyemail?token={token}">Verify Your Email</a>
        <p>Thanks,</p>
        <p>The Hostel Mess Team</p>
    </body>
    </html>
    """

    message = MessageSchema(
        subject="Hostel Mess: Verify Your Email",
        recipients=[email],
        body=html,
        subtype="html" # type: ignore
    )

    fm = FastMail(conf)
    await fm.send_message(message)
    

async def send_password_reset_email(email: EmailStr, name: str, token: str):
    """
    Sends the password reset email to a user.
    """
    # NOTE: In a real frontend app, the link here would point to a page in your app,
    # for now, we just provide the token directly in the email for simplicity.
    html = f"""
    <html><body>
        <p>Hi {name},</p>
        <p>You recently requested to reset your password for the Hostel Mess App. Please use the token below to complete the reset process.</p>
        <p>This token is valid for <strong>15 minutes</strong>.</p>
        <p>Your password reset token is: <strong>{token}</strong></p>
        <p>If you did not request a password reset, please ignore this email or contact support if you have concerns.</p>
        <p>Thanks,</p><p>The Hostel Mess Team</p>
    </body></html>
    """
    message = MessageSchema(
        subject="Hostel Mess: Password Reset Request",
        recipients=[email],
        body=html,
        subtype="html" # type: ignore
    )
    fm = FastMail(conf)
    await fm.send_message(message)