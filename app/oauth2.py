from jose import JWTError,jwt
from datetime import datetime,timedelta
from fastapi import Depends,HTTPException,status
from typing import Optional
from . import schemas,database
from fastapi.security import OAuth2PasswordBearer

# This creates a dependency that will look for the token in the request's "Authorization" header
oauth2_scheme = OAuth2PasswordBearer(tokenUrl='auth/login')


SECRET_KEY = "awiu7238xbbwakjsil9al2874jhdsssaki38435jkw9aayqi2hawgdsaKaki284"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_DAYS = 10


def create_access_token(data:dict, expire_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    #expire = datetime.now() + timedelta(days=ACCESS_TOKEN_EXPIRE_DAYS)
    if expire_delta:
        expire = datetime.now() + expire_delta
    else:
        expire = datetime.now() + timedelta(days=ACCESS_TOKEN_EXPIRE_DAYS)

    to_encode.update({"exp":expire})

    encoded_jwt = jwt.encode(to_encode,SECRET_KEY,algorithm=ALGORITHM)
    return encoded_jwt


def verify_access_token(token:str,credential_exceptions):
    try:
        payload = jwt.decode(token,SECRET_KEY,algorithms=[ALGORITHM])
        user_id = payload.get("user_id")

        if user_id is None:
            raise credential_exceptions
        
        token_data = schemas.TokenData(user_id=user_id)
    except JWTError:
        raise credential_exceptions
    
    return token_data

#--------------------------------------Based on token data of user is returned-------------------------------------#
def get_current_user(token: str = Depends(oauth2_scheme), conn = Depends(database.get_db_connection)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"}
    )

    token_data = verify_access_token(token,credentials_exception)
    with conn.cursor() as c:
        c.execute("SELECT * FROM users WHERE id=%s",(str(token_data.user_id),))
        user = c.fetchone()

    if not user:
        raise credentials_exception
    
    return user



#------------------------------------Check for convenor---------------------------------------#
def require_convenor_role(current_user: dict = Depends(get_current_user)):
    """
    A dependency that checks if the current user is a convenor.
    """

    if current_user['role'] not in ['convenor']:
        raise HTTPException(status.HTTP_403_FORBIDDEN,detail="You don't have permission to perform this action.")
    
    return current_user

#------------------------------------Check for Mess Committee---------------------------------------#
def require_mess_committee_role(current_user: dict = Depends(get_current_user)):
    """
    A dependency that checks if the current user is a convenor.
    """

    if current_user['role'] not in ['mess_committee']:
        raise HTTPException(status.HTTP_403_FORBIDDEN,detail="You don't have permission to perform this action.")
    
    return current_user

#---------------------------------------Check for admin------------------------------------------#
def require_admin_role(current_user: dict = Depends(get_current_user)):
    """
    A dependency that checks if the current user is a convenor.
    """

    if current_user['role'] not in ['convenor','mess_committee']:
        raise HTTPException(status.HTTP_403_FORBIDDEN,detail="You don't have permission to perform this action.")
    
    return current_user


