from fastapi import FastAPI,Depends,status,HTTPException,APIRouter
from psycopg2.errors import UniqueViolation # type: ignore
import psycopg2 # type: ignore
from . import schemas
from .database import get_db_connection
from fastapi.security import OAuth2PasswordRequestForm
from . import oauth2, utils
from .Routers import auth,menus,booking,notice,users

# Create an instance of the FastAPI application
app = FastAPI()

app.include_router(auth.router)
app.include_router(menus.router)
app.include_router(booking.router)
app.include_router(notice.router)
app.include_router(users.router)