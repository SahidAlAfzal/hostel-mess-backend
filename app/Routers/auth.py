from fastapi import APIRouter, status, HTTPException, Depends, BackgroundTasks
from fastapi.responses import HTMLResponse
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from datetime import timedelta

from .. import models, schemas, utils, oauth2, database
from ..send_email import send_verification_email, send_password_reset_email

router = APIRouter(
    prefix="/auth",
    tags=['Authentication']
)

#----------------------------------------------REGISTRATION---------------------------------------------#
@router.post("/register", status_code=status.HTTP_201_CREATED)
def create_user(user: schemas.CreateUser, background_tasks: BackgroundTasks, db: Session = Depends(database.get_db)):
    hashed_password = utils.hash_password(user.password)
    
    new_user = models.User(
        name=user.name,
        email=user.email,
        hashed_password=hashed_password,
        room_number=user.room_number
    )

    try:
        db.add(new_user)
        db.commit()
        db.refresh(new_user)
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Username or Email already exists")
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Database error: {e}")
      
    verification_token = oauth2.create_access_token(data={"user_id": new_user.id})
    background_tasks.add_task(
        send_verification_email, user.email, user.name, verification_token
    )
    
    return {"message": "Registration successful! Please check your email to verify your account."}

#-------------------------------------------Email Verification-----------------------------------------#
@router.get("/verifyemail", response_class=HTMLResponse)
def verify_email(token: str, db: Session = Depends(database.get_db)):
    """
    This endpoint is hit when a user clicks the link in their verification email.
    It verifies the token and activates the user's account.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
    )
    
    token_data = oauth2.verify_access_token(token, credentials_exception)
    user = db.query(models.User).filter(models.User.id == token_data.user_id).first()
    
    if not user:
        raise credentials_exception

    try:
        user.is_active = True # type: ignore
        db.commit()
    except Exception:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error activating account.")
    
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
@router.post("/login", response_model=schemas.Token)
def login(user_credentials: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(database.get_db)):
    user = db.query(models.User).filter(models.User.email == user_credentials.username).first()

    if not user or not utils.verify_password(user_credentials.password, user.hashed_password): # type: ignore
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid Credentials")
    
    if not user.is_active: # type: ignore
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account not active. Please verify your email first")
    
    access_token = oauth2.create_access_token({"user_id": user.id})

    return {"access_token": access_token, "token_type": "bearer"}

#-------------------------------------About Me-----------------------------------------#
@router.get("/me", response_model=schemas.UserOut)
def get_me(current_user: models.User = Depends(oauth2.get_current_user)):
    return current_user

#-------------------------------------FORGOT PASSWORD-----------------------------------#
@router.post("/forgot-password")
def forgot_password(request: schemas.PasswordResetRequest, background_tasks: BackgroundTasks, db: Session = Depends(database.get_db)):
    """
    Handles a user's request to reset their password.
    Finds the user and sends a reset email if they exist.
    """
    user = db.query(models.User).filter(models.User.email == request.email).first()
    
    # IMPORTANT: For security, we always return a success message.
    # This prevents attackers from guessing which emails are registered.
    if user:
        password_reset_token = oauth2.create_access_token(
            data={"user_id": user.id},
            expire_delta=timedelta(minutes=15)
        )
        background_tasks.add_task(
            send_password_reset_email, user.email, user.name, password_reset_token # type: ignore
        )

    return {"message": "If an account with that email exists, a password reset email has been sent."}

#-------------------------------------RESET PASSWORD------------------------------------#
@router.post("/reset-password")
def reset_password(request: schemas.PasswordReset, db: Session = Depends(database.get_db)):
    """
    Handles the actual password reset using the token from the email.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="The token is invalid or has expired.",
    )
    
    token_data = oauth2.verify_access_token(request.token, credentials_exception)
    user = db.query(models.User).filter(models.User.id == token_data.user_id).first()

    if not user:
        raise credentials_exception

    try:
        user.hashed_password = utils.hash_password(request.new_password)
        db.commit()
    except Exception:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error resetting password.")
            
    return {"message": "Your password has been reset successfully."}

#---------------------------------UPDATE PROFILE---------------------------------#
@router.patch("/me", response_model=schemas.UpdatedUserOut)
def update_user(updated_user: schemas.UpdatedUserIn, db: Session = Depends(database.get_db), current_user: models.User = Depends(oauth2.get_current_user)):
    user = db.query(models.User).filter(models.User.id == current_user.id).first()
    
    if not user:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=f"User with id {current_user.id} not found")

    try:
        user.name = updated_user.name # type: ignore
        user.room_number = updated_user.room_number # type: ignore
        db.commit()
        db.refresh(user)
    except Exception as e:
        db.rollback()
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Database Error: {e}")
        
    return user