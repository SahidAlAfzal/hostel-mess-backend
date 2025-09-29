from fastapi import APIRouter, status, HTTPException, Depends,Response
from datetime import date,datetime,timedelta
import psycopg2
from typing import List
import pytz
from .. import schemas, oauth2
from ..database import get_db_connection

router = APIRouter(
    prefix="/bookings",
    tags=['Bookings']
)


# --- Define Timezone and Cut-off Hours ---
IST = pytz.timezone('Asia/Kolkata')
TODAY_CUTOFF_HOUR = 18  # 6:00 PM
NEXT_DAY_WINDOW_HOUR = 21 # 9:00 PM


def validate_booking_time(booking_date: date):
    """
    Checks if a booking or cancellation is allowed based on the current time and hostel rules.
    All times are checked against India Standard Time (IST).
    """
    # Get current date and time in IST
    now_ist = datetime.now(IST)
    today_ist = now_ist.date()

    # Rule 1: Prevent any action on past dates
    if booking_date < today_ist:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot perform actions on a past date.")

    # Rule 2: Check for today's booking cutoff (6 PM)
    if booking_date == today_ist:
        if now_ist.hour >= TODAY_CUTOFF_HOUR:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"Booking for today is closed after {TODAY_CUTOFF_HOUR}:00 IST.")

    # Rule 3: Check for the next-day-only window (after 9 PM)
    if now_ist.hour >= NEXT_DAY_WINDOW_HOUR:
        tomorrow_ist = today_ist + timedelta(days=1)
        if booking_date != tomorrow_ist:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"After {NEXT_DAY_WINDOW_HOUR}:00 IST, you can only book or modify meals for the next day.")




@router.post("/", status_code=status.HTTP_201_CREATED, response_model=schemas.MealBookingOut)
def create_or_update_booking(booking: schemas.MealBookingCreate, conn=Depends(get_db_connection), current_user: dict = Depends(oauth2.get_current_user)):
    #CHECK FOR time logic
    validate_booking_time(booking.booking_date)



    # --- Part 1: Validation ---
    # Get the official menu for the requested date to validate against.
    with conn.cursor() as cur:
        cur.execute("SELECT * FROM daily_menus WHERE menu_date = %s", (booking.booking_date,))
        menu = cur.fetchone()

    if not menu:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail=f"The menu for {booking.booking_date} has not been set yet. Booking is not available.")

    # --- VALIDATION LOGIC ---
    # Check if every item in the user's lunch pick list is a valid menu option.
    # We use set().issubset() for an efficient check.
    if booking.lunch_pick and not set(booking.lunch_pick).issubset(set(menu['lunch_options'])):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail=f"One or more of your lunch picks are not valid options on this day.")


    # Check if every item in the user's dinner pick list is a valid menu option.
    if booking.dinner_pick and not set(booking.dinner_pick).issubset(set(menu['dinner_options'])):
         raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail=f"One or more of your dinner picks are not valid options on this day.")


    # --- Part 2: The "UPSERT" Query ---
    # This query remains the same, as psycopg2 can handle passing a Python list
    # directly to a PostgreSQL TEXT[] array column.
    query = """
        INSERT INTO meal_bookings (user_id, booking_date, lunch_pick, dinner_pick)
        VALUES (%(user_id)s, %(booking_date)s, %(lunch_pick)s, %(dinner_pick)s)
        ON CONFLICT (user_id, booking_date) DO UPDATE SET
            lunch_pick = EXCLUDED.lunch_pick,
            dinner_pick = EXCLUDED.dinner_pick
        RETURNING id, user_id, booking_date, lunch_pick, dinner_pick, created_at;
    """
    
    params = booking.model_dump()
    params['user_id'] = current_user['id']

    with conn.cursor() as cur:
        try:
            cur.execute(query, params)
            new_booking = cur.fetchone()
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Database error: {e}")

    return new_booking



#-----------------------------------------------------DELETE BOOKING----------------------------------------------------------#
@router.delete("/{booking_date}",status_code=status.HTTP_204_NO_CONTENT)
def delete_booking(booking_date: date, conn = Depends(get_db_connection),current_user: dict = Depends(oauth2.get_current_user)):
    #check the time logic
    validate_booking_time(booking_date=booking_date)


    query = "DELETE FROM meal_bookings WHERE user_id=%s AND booking_date = %s"

    with conn.cursor() as c:
        try:
            c.execute(query,(current_user['id'],booking_date))
            # Check if a row was actually deleted.
            # If rowcount is 0, it means no booking existed for that user and date.
            if c.rowcount == 0:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,detail=f"You do not have a booking for {booking_date} to cancel.")
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR,detail=f"Database Error : {e}")
        
        # Return a 204 No Content response on successful deletion.
        return Response(status_code=status.HTTP_204_NO_CONTENT)




