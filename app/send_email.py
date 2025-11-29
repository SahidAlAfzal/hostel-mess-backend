from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail
from pydantic import EmailStr
import os

# We will need the MAIL_FROM address from our environment
MAIL_FROM = os.getenv("MAIL_FROM", "default@example.com") 
SENDGRID_API_KEY = os.getenv("SENDGRID_API_KEY")

def send_verification_email(email: EmailStr, name: str, token: str):
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
        sg.send(message)
    except Exception as e:
        print(f"Error sending email via SendGrid: {e}")
    

def send_password_reset_email(email: EmailStr, name: str, token: str):
    """
    Sends the password reset email to a user.
    """
    if not SENDGRID_API_KEY or not MAIL_FROM:
        print("WARNING: Email credentials not set. Password reset email will not be sent.")
        return

    html_content = f"""
    <html>
    <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
        <div style="max-width: 600px; margin: auto; padding: 20px; border: 1px solid #ddd; border-radius: 10px;">
            <h2 style="color: #000;">Password Reset Request</h2>
            <p>Hi {name},</p>
            <p>You recently requested to reset your password for the Hostel Mess App. Please use the token below to complete the reset process.</p>
            <p>This token is valid for <strong>15 minutes</strong>.</p>
            <p style="background-color: #f5f5f5; border: 1px dashed #ccc; padding: 10px; text-align: center; font-size: 1.2em; letter-spacing: 2px;">
                <strong>{token}</strong>
            </p>
            <p>If you did not request a password reset, you can safely ignore this email.</p>
            <p>Thanks,<br/>The Hostel Mess Team</p>
        </div>
    </body>
    </html>
    """
    message = Mail(
        from_email=MAIL_FROM,
        to_emails=email,
        subject='Hostel Mess: Password Reset Request',
        html_content=html_content
    )

    # DEBUG: Check what the key looks like (masking the middle for security)
    if SENDGRID_API_KEY:
        masked_key = f"{SENDGRID_API_KEY[:4]}...{SENDGRID_API_KEY[-4:]}"
        print(f"DEBUG: Using API Key: {masked_key}")
        print(f"DEBUG: Key Length: {len(SENDGRID_API_KEY)}")
        
    try:
        sg = SendGridAPIClient(SENDGRID_API_KEY)
        sg.send(message)
        print(f"Password reset email sent to {email}.")
    except Exception as e:
        print(f"FATAL: Error sending password reset email via SendGrid: {e}")

