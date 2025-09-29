from fastapi import APIRouter, status, HTTPException, Depends, BackgroundTasks
from fastapi.responses import HTMLResponse
from fastapi.security import OAuth2PasswordRequestForm
from psycopg2.errors import UniqueViolation
import psycopg2
from datetime import timedelta

from .. import schemas, utils, oauth2,database
# --- THE FIX: We now import both functions explicitly from the correct file ---
from ..send_email import send_verification_email, send_password_reset_email

router = APIRouter(
    prefix="/auth",
    tags=['Authentication']
)

#----------------------------------------------REGISTRATION---------------------------------------------#
@router.post("/register",status_code=status.HTTP_201_CREATED)
def create_user(user:schemas.CreateUser,background_tasks: BackgroundTasks, conn = Depends(database.get_db_connection)):
    hashed_password = utils.hash_password(user.password)
    new_user = user.model_dump()
    new_user['hashed_password'] = hashed_password
    del new_user['password']

    try:
        with conn.cursor() as c:
            query = """
                INSERT INTO users (name, email, room_number, hashed_password)
                VALUES (%(name)s, %(email)s, %(room_number)s, %(hashed_password)s)
                RETURNING id, name, email;
            """
            c.execute(query, new_user)
            created_user = c.fetchone()
            conn.commit()
    except UniqueViolation as e:
        conn.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="An account with this email already exists.")
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Could not create user.")
    
    verification_token = oauth2.create_access_token(data={"user_id" : created_user['id']})
    # The call to the function is now unambiguous
    background_tasks.add_task(
        send_verification_email, created_user['email'], created_user['name'], verification_token
    )

    return {"message": "Registration successful! Please check your email to verify your account."}


#-------------------------------------------Email Verification-----------------------------------------#
@router.get("/verifyemail", response_class=HTMLResponse)
def verify_email(token: str, conn=Depends(database.get_db_connection)):
    """
    This endpoint is hit when a user clicks the link in their verification email.
    It verifies the token and activates the user's account.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
    )
    
    # Verify the token to get the user's ID
    token_data = oauth2.verify_access_token(token, credentials_exception)
    user_id = token_data.user_id

    # Update the user's 'is_active' status in the database
    with conn.cursor() as cur:
        try:
            query = "UPDATE users SET is_active = TRUE WHERE id = %s RETURNING id;"
            cur.execute(query, (user_id,))
            updated_user = cur.fetchone()
            
            if not updated_user:
                raise credentials_exception

            conn.commit()
        except Exception:
            conn.rollback()
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error activating account.")
    
    # Return a simple success message to the user's browser
    return """
    <html>
        <head>
            <title>Account Verified</title>
        </head>
        <body>
            <h1>Your account has been successfully verified!</h1>
            <p>You can now close this tab and log in to the application.</p>
        </body>
    </html>
    """


#----------------------------------Login---------------------------------------#
@router.post("/login",response_model=schemas.Token)
def login(user_credentials:OAuth2PasswordRequestForm = Depends(),conn = Depends(database.get_db_connection)):
    query = "SELECT * FROM users WHERE email=%s"
    with conn.cursor() as c:
        c.execute(query,(user_credentials.username,))
        user = c.fetchone()

    #check if password is correct
    if not user or not utils.verify_password(user_credentials.password,user["hashed_password"]):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,detail="Invalid Credentials")
    
    if not user['is_active']:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,detail=f"Account not active. Please verify your email first")
    
    #create access token
    access_token = oauth2.create_access_token({"user_id":user["id"]})

    return {"access_token" : access_token,"token_type": "bearer"}




#-------------------------------------About Me-----------------------------------------#
@router.get("/me",response_model=schemas.UserOut)
def get_me(current_user: dict = Depends(oauth2.get_current_user)):
    return current_user







#-------------------------------------FORGOT PASSWORD-----------------------------------#
@router.post("/forgot-password")
def forgot_password(request: schemas.PasswordResetRequest, background_tasks: BackgroundTasks, conn=Depends(database.get_db_connection)):
    """
    Handles a user's request to reset their password.
    Finds the user and sends a reset email if they exist.
    """
    with conn.cursor() as cur:
        query = "SELECT * FROM users WHERE email = %s"
        cur.execute(query, (request.email,))
        user = cur.fetchone()
    
    # IMPORTANT: For security, we always return a success message.
    # This prevents attackers from guessing which emails are registered.
    if user:
        # Create a short-lived token (15 minutes) using our flexible function
        password_reset_token = oauth2.create_access_token(
            data={"user_id": user['id']},
            expire_delta = timedelta(minutes=15)
        )
        # Send the email in the background
        background_tasks.add_task(
            send_email.send_password_reset_email, user['email'], user['name'], password_reset_token # type: ignore
        )

    return {"message": "If an account with that email exists, a password reset email has been sent."}



# ENDPOINT 2: Perform the password reset
@router.post("/reset-password")
def reset_password(request: schemas.PasswordReset, conn=Depends(database.get_db_connection)):
    """
    Handles the actual password reset using the token from the email.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="The token is invalid or has expired.",
    )
    
    token_data = oauth2.verify_access_token(request.token, credentials_exception)
    user_id = token_data.user_id

    # Hash the new password before saving it
    hashed_password = utils.hash_password(request.new_password)

    # Update the user's password in the database
    with conn.cursor() as cur:
        try:
            query = "UPDATE users SET hashed_password = %s WHERE id = %s RETURNING id;"
            cur.execute(query, (hashed_password, user_id))
            if not cur.fetchone():
                raise credentials_exception
            conn.commit()
        except Exception:
            conn.rollback()
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error resetting password.")
            
    return {"message": "Your password has been reset successfully."}
        
