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
LUNCH_CUTOFF_HOUR = 7 # 7:00 AM
TODAY_CUTOFF_HOUR = 18  # 6:00 PM


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



#-------------------------------------------------------CREATE A BOOKING----------------------------------------------------#
@router.post("/", status_code=status.HTTP_201_CREATED, response_model=schemas.MealBookingOut)
def create_booking(booking: schemas.MealBookingCreate, conn=Depends(get_db_connection), current_user: dict = Depends(oauth2.get_current_user)):
    #Check mess is off or not
    if not current_user['is_mess_active']:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,detail="Your Mess is off!! Please contact mess committee")
    

    #CHECK FOR time logic
    validate_booking_time(booking.booking_date)

    # RULE: CAN'T BOOK FOR LUNCH AFTER 7 AM
    now_ist = datetime.now(IST)
    today_ist = now_ist.date()

    if booking.booking_date == today_ist and now_ist.hour >= LUNCH_CUTOFF_HOUR and booking.lunch_pick:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail=f"Cannot book lunch for today after {LUNCH_CUTOFF_HOUR}:00 IST.")


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
    if booking.lunch_pick and not set(booking.lunch_pick).issubset(set(menu['lunch_options'])):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail=f"One or more of your lunch picks are not valid options on this day.")


    # Check if every item in the user's dinner pick list is a valid menu option.
    if booking.dinner_pick and not set(booking.dinner_pick).issubset(set(menu['dinner_options'])):
         raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail=f"One or more of your dinner picks are not valid options on this day.")


    # --- Part 2: The "INSERT" Query ---
    # This query is now a simple INSERT, not an UPSERT.
    # It will fail with a unique_violation error if a booking already exists.
    query = """
        INSERT INTO meal_bookings (user_id, booking_date, lunch_pick, dinner_pick)
        VALUES (%(user_id)s, %(booking_date)s, %(lunch_pick)s, %(dinner_pick)s)
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
            # Check if the error is a 'unique_violation' (pgcode 23505)
            if hasattr(e, 'pgcode') and e.pgcode == '23505': # type: ignore
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"A booking for {booking.booking_date} already exists. Please use the 'update' endpoints to make changes."
                )
            # For any other database error
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Database error: {e}")

    return new_booking

#-----------------------------------------------------GET MY BOOKINGS-------------------------------------------------------#
@router.get("/me",response_model=List[schemas.MyBookingHistoryItem])
def get_my_bookings(conn = Depends(get_db_connection),current_user: dict = Depends(oauth2.get_current_user)):
    user_id = current_user['id']
    query = "SELECT booking_date,lunch_pick, dinner_pick,created_at FROM meal_bookings WHERE user_id = %s ORDER BY booking_date DESC;"
    
    with conn.cursor() as c:
        c.execute(query,(user_id,))
        meal_history = c.fetchall()

    if not meal_history:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,detail="You have no bookings!")
    
    return meal_history




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
    

#-----------------------------------------------------UPDATE LUNCH BOOKINGS------------------------------------------------------#
@router.patch("/update-lunch",status_code=status.HTTP_200_OK,response_model=schemas.MealBookingOut)
def update_Lunch(booking:schemas.LunchUpdate, conn = Depends(get_db_connection),current_user: dict = Depends(oauth2.get_current_user)):
    # This validates Rules 1, 2, and 3 (past dates, 6 PM cutoff, 9 PM window)
    validate_booking_time(booking.booking_date)

    # RULE: CAN'T BOOK FOR LUNCH AFTER 7 AM
    now_ist = datetime.now(IST)
    today_ist = now_ist.date()

    if booking.booking_date == today_ist and now_ist.hour >= LUNCH_CUTOFF_HOUR:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail=f"Cannot book lunch for today after {LUNCH_CUTOFF_HOUR}:00 IST.")
    

    #----------Menu Validation-----------
    with conn.cursor() as cur:
        cur.execute("SELECT * FROM daily_menus WHERE menu_date = %s", (booking.booking_date,))
        menu = cur.fetchone()

    if not menu:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail=f"The menu for {booking.booking_date} has not been set yet.")

    # Check if the new lunch pick is valid
    if booking.lunch_pick and not set(booking.lunch_pick).issubset(set(menu['lunch_options'])):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail=f"One or more of your lunch picks are not valid options on this day.")
    

    user_id = current_user['id']

    query = """UPDATE meal_bookings SET lunch_pick = %s WHERE user_id = %s AND booking_date = %s
            RETURNING id, user_id, booking_date, lunch_pick, dinner_pick, created_at;
            """
    
    with conn.cursor() as cur:
        try:
            cur.execute(query,(booking.lunch_pick,user_id,booking.booking_date))
            updated_booking = cur.fetchone()

            if not updated_booking:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"No booking found for user {user_id} on {booking.booking_date}"
                )
            conn.commit()

        except Exception as e:
            conn.rollback()
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Database error: {e}")
        
    return updated_booking
    

#-----------------------------------------------------UPDATE DINNER BOOKINGS------------------------------------------------------#
@router.patch("/update-dinner",status_code=status.HTTP_200_OK,response_model=schemas.MealBookingOut)
def update_Dinner(booking:schemas.DinnerUpdate, conn = Depends(get_db_connection),current_user: dict = Depends(oauth2.get_current_user)):
    #CHECK FOR time logic
    validate_booking_time(booking.booking_date)
    
    # RULE: CAN'T BOOK FOR Dinner AFTER 6 PM
    now_ist = datetime.now(IST)
    today_ist = now_ist.date()

    #----------Menu Validation-----------
    with conn.cursor() as cur:
        cur.execute("SELECT * FROM daily_menus WHERE menu_date = %s", (booking.booking_date,))
        menu = cur.fetchone()

    if not menu:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail=f"The menu for {booking.booking_date} has not been set yet.")

    # Check if the new lunch pick is valid
    if booking.dinner_pick and not set(booking.dinner_pick).issubset(set(menu['dinner_options'])):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail=f"One or more of your dinner picks are not valid options on this day.")
    
    if booking.booking_date == today_ist and now_ist.hour >= TODAY_CUTOFF_HOUR:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail=f"Cannot book dinner for today after {TODAY_CUTOFF_HOUR}:00 IST.")
    

    user_id = current_user['id']

    query = """UPDATE meal_bookings SET dinner_pick = %s WHERE user_id = %s AND booking_date = %s
            RETURNING id, user_id, booking_date, lunch_pick, dinner_pick, created_at;
            """
    
    with conn.cursor() as cur:
        try:
            cur.execute(query,(booking.dinner_pick,user_id,booking.booking_date))
            updated_booking = cur.fetchone()

            if not updated_booking:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"No booking found for user {user_id} on {booking.booking_date}"
                )
            
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Database error: {e}")
        
        return updated_booking


