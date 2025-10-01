from fastapi import FastAPI,Depends,status,HTTPException,APIRouter
from psycopg2.errors import UniqueViolation # type: ignore
import psycopg2 # type: ignore
from . import schemas
from .database import get_db_connection
from fastapi.security import OAuth2PasswordRequestForm
from . import oauth2, utils
from .Routers import auth,menus,booking,notice,users,meallist
from fastapi.middleware.cors import CORSMiddleware

# Create an instance of the FastAPI application
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Accept requests from any domain/IP
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(auth.router)
app.include_router(menus.router)
app.include_router(booking.router)
app.include_router(notice.router)
app.include_router(users.router)
app.include_router(meallist.router)



# A simple root endpoint
@app.get("/")
def root():
    return {"message": "Welcome to the Hostel Management API. The service is running."}


#------------------------------------NEW HEALTH CHECK ENDPOINT-------------------------------------#
@app.get("/health", status_code=status.HTTP_200_OK)
def health_check(conn=Depends(get_db_connection)):
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT 1")
            cur.fetchone()
        return {"status": "ok", "database": "connected"}
    
    except Exception as e:
        # If the database connection fails, this will raise a server error,
        # which will correctly signal to UptimeRobot that the service is down.
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Database connection error: {e}"
        )