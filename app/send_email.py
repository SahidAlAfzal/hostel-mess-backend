from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail
from pydantic import EmailStr
import os

# We will need the MAIL_FROM address from our environment
MAIL_FROM = os.getenv("MAIL_FROM", "default@example.com") 
SENDGRID_API_KEY = os.getenv("SENDGRID_API_KEY")

async def send_verification_email(email: EmailStr, name: str, token: str):
    """
    Sends the account verification email to a new user using SendGrid.
    """
    if not SENDGRID_API_KEY:
        print("WARNING: SENDGRID_API_KEY not set. Email will not be sent.")
        return

    html_content = f"""
    <html><body>
        <p>Hi {name},</p>
        <p>Please click the link below to verify your email and activate your account:</p>
        <a href="https://hostel-mess-backend.onrender.com/auth/verifyemail?token={token}">Verify Your Email</a>
    </body></html>
    """
    message = Mail(
        from_email=MAIL_FROM,
        to_emails=email,
        subject='Hostel Mess: Verify Your Email',
        html_content=html_content
    )
    try:
        sg = SendGridAPIClient(SENDGRID_API_KEY)
        await sg.send(message)
    except Exception as e:
        print(f"Error sending email via SendGrid: {e}")
    

