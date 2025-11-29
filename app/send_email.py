import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os

# Load config
SMTP_SERVER = os.getenv("MAIL_SERVER", "smtp-relay.brevo.com")
SMTP_PORT = int(os.getenv("MAIL_PORT", 587))
SENDER_EMAIL = os.getenv("MAIL_FROM")      # The email you verified in Brevo
SMTP_LOGIN = os.getenv("MAIL_USERNAME")    # Your Brevo login email
SMTP_PASSWORD = os.getenv("MAIL_PASSWORD") # The XS... key you generated

def send_email_smtp(to_email: str, subject: str, html_content: str):
    if not SMTP_PASSWORD or not SENDER_EMAIL:
        print("FATAL: Email credentials not set in .env")
        return

    # Create the email object
    msg = MIMEMultipart()
    msg['From'] = SENDER_EMAIL
    msg['To'] = to_email
    msg['Subject'] = subject
    msg.attach(MIMEText(html_content, 'html'))

    try:
        # Connect to Brevo's SMTP server
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls() # Secure the connection
        server.login(SMTP_LOGIN, SMTP_PASSWORD) # type: ignore
        server.send_message(msg)
        server.quit()
        print(f"✅ Email sent successfully to {to_email}")
    except Exception as e:
        print(f"❌ Failed to send email: {e}")

# --- Wrappers to match your auth.py calls ---

def send_verification_email(email: str, name: str, token: str):
    # Update this URL to match your frontend/backend URL
    verify_url = f"https://hostel-mess-backend.onrender.com/auth/verifyemail?token={token}"
    
    html = f"""
    <html>
        <body style="font-family: Arial, sans-serif; padding: 20px;">
            <h2>Welcome to MessBook, {name}!</h2>
            <p>Please verify your email address to activate your account.</p>
            <a href="{verify_url}" style="background-color: #4CAF50; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">Verify Email</a>
            <p>Or paste this link: {verify_url}</p>
        </body>
    </html>
    """
    send_email_smtp(email, "MessBook: Verify Your Account", html)

def send_password_reset_email(email: str, name: str, token: str):
    html = f"""
    <html>
        <body style="font-family: Arial, sans-serif; padding: 20px;">
            <h2>Password Reset</h2>
            <p>Hi {name}, use the token below to reset your password:</p>
            <h3 style="background: #eee; padding: 10px; display: inline-block;">{token}</h3>
            <p>This token expires in 15 minutes.</p>
        </body>
    </html>
    """
    send_email_smtp(email, "MessBook: Password Reset", html)