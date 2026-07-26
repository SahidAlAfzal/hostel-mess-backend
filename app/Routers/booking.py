from fastapi import APIRouter, status, HTTPException, Depends, Response, BackgroundTasks
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from datetime import date, datetime, timedelta
from typing import List
import pytz

from .. import schemas, oauth2, models
from ..database import get_db
from .. import fcm_manager

router = APIRouter(
    prefix="/bookings",
    tags=['Bookings']
)

# --- Define Timezone and Cut-off Hours ---
IST = pytz.timezone('Asia/Kolkata')
LUNCH_CUTOFF_HOUR = 7   # 7:00 AM
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
        
#-------------------------------------CREATE OR UPDATE (UPSERT)-----------------------------------------#
@router.post("/", status_code=status.HTTP_201_CREATED, response_model=schemas.MealBookingOut)
def create_or_update_booking(
    booking: schemas.MealBookingCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(oauth2.get_current_user)
):
    # ------------------------------
    #   PART 0: Mess Active Check
    # ------------------------------
    if not current_user.is_mess_active:     # type: ignore
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your Mess is off!! Please contact mess committee"
        )

    # ------------------------------
    #   PART 1: Time Validations
    # ------------------------------
    validate_booking_time(booking.booking_date)

    now_ist = datetime.now(IST)
    today_ist = now_ist.date()

    if (
        booking.booking_date == today_ist
        and now_ist.hour >= LUNCH_CUTOFF_HOUR
        and booking.lunch_pick
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Cannot book lunch for today after {LUNCH_CUTOFF_HOUR}:00 IST."
        )

    # ------------------------------
    #   PART 2: Fetch Menu for Date
    # ------------------------------
    menu = db.query(models.Menu).filter(models.Menu.menu_date == booking.booking_date).first()

    if not menu:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"The menu for {booking.booking_date} has not been set yet. Booking is not available."
        )

    # ------------------------------
    #   PART 3: Validation Logic
    # ------------------------------
    if booking.lunch_pick:
        if not set(booking.lunch_pick).issubset(set(menu.lunch_options)):       # type: ignore
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="One or more of your lunch picks are not valid options on this day."
            )

    if booking.dinner_pick:
        if not set(booking.dinner_pick).issubset(set(menu.dinner_options)):     # type: ignore
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="One or more of your dinner picks are not valid options on this day."
            )

    # ------------------------------
    #   PART 4: UPSERT (Insert or Update)
    # ------------------------------
    db_booking = db.query(models.Booking).filter(
        models.Booking.user_id == current_user.id,
        models.Booking.booking_date == booking.booking_date
    ).first()

    try:
        if db_booking:
            db_booking.lunch_pick = booking.lunch_pick      # type: ignore
            db_booking.dinner_pick = booking.dinner_pick    # type: ignore
        else:
            db_booking = models.Booking(
                user_id=current_user.id,
                booking_date=booking.booking_date,
                lunch_pick=booking.lunch_pick,
                dinner_pick=booking.dinner_pick
            )
            db.add(db_booking)
            
        db.commit()
        db.refresh(db_booking)
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error: {e}"
        )

    return db_booking

#-------------------------------------------------------CREATE A BOOKING----------------------------------------------------#
@router.post("/book", status_code=status.HTTP_201_CREATED, response_model=schemas.MealBookingOut)
def create_booking(booking: schemas.MealBookingCreate, db: Session = Depends(get_db), current_user: models.User = Depends(oauth2.get_current_user)):
    
    if not current_user.is_mess_active: # type: ignore
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Your Mess is off!! Please contact mess committee")
    
    validate_booking_time(booking.booking_date)

    now_ist = datetime.now(IST)
    today_ist = now_ist.date()

    if booking.booking_date == today_ist and now_ist.hour >= LUNCH_CUTOFF_HOUR and booking.lunch_pick:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"Cannot book lunch for today after {LUNCH_CUTOFF_HOUR}:00 IST.")

    # --- Part 1: Validation ---
    menu = db.query(models.Menu).filter(models.Menu.menu_date == booking.booking_date).first()

    if not menu:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"The menu for {booking.booking_date} has not been set yet. Booking is not available.")

    # --- VALIDATION LOGIC ---
    if booking.lunch_pick and not set(booking.lunch_pick).issubset(set(menu.lunch_options)): # type: ignore
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="One or more of your lunch picks are not valid options on this day.")

    if booking.dinner_pick and not set(booking.dinner_pick).issubset(set(menu.dinner_options)): # type: ignore
         raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="One or more of your dinner picks are not valid options on this day.")

    # --- Part 2: The "INSERT" Query ---
    new_booking = models.Booking(
        user_id=current_user.id,
        booking_date=booking.booking_date,
        lunch_pick=booking.lunch_pick,
        dinner_pick=booking.dinner_pick
    )

    try:
        db.add(new_booking)
        db.commit()
        db.refresh(new_booking)
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"A booking for {booking.booking_date} already exists. Please use the 'update' endpoints to make changes."
        )
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Database error: {e}")

    return new_booking

#-----------------------------------------------------GET MY BOOKINGS-------------------------------------------------------#
@router.get("/me", response_model=List[schemas.MyBookingHistoryItem])
def get_my_bookings(db: Session = Depends(get_db), current_user: models.User = Depends(oauth2.get_current_user)):
    
    meal_history = db.query(models.Booking).filter(
        models.Booking.user_id == current_user.id
    ).order_by(models.Booking.booking_date.desc()).all()

    if not meal_history:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="You have no bookings!")
    
    return meal_history

#-----------------------------------------------------DELETE BOOKING----------------------------------------------------------#
@router.delete("/{booking_date}", status_code=status.HTTP_204_NO_CONTENT)
def delete_booking(booking_date: date, db: Session = Depends(get_db), current_user: models.User = Depends(oauth2.get_current_user)):
    
    validate_booking_time(booking_date=booking_date)

    db_booking = db.query(models.Booking).filter(
        models.Booking.user_id == current_user.id,
        models.Booking.booking_date == booking_date
    ).first()

    if not db_booking:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"You do not have a booking for {booking_date} to cancel.")

    try:
        db.delete(db_booking)
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Database Error : {e}")
        
    return Response(status_code=status.HTTP_204_NO_CONTENT)
    
#-----------------------------------------------------UPDATE LUNCH BOOKINGS------------------------------------------------------#
@router.patch("/update-lunch", status_code=status.HTTP_200_OK, response_model=schemas.MealBookingOut)
def update_Lunch(booking: schemas.LunchUpdate, db: Session = Depends(get_db), current_user: models.User = Depends(oauth2.get_current_user)):
    
    validate_booking_time(booking.booking_date)

    now_ist = datetime.now(IST)
    today_ist = now_ist.date()

    if booking.booking_date == today_ist and now_ist.hour >= LUNCH_CUTOFF_HOUR:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"Cannot book lunch for today after {LUNCH_CUTOFF_HOUR}:00 IST.")
    
    #----------Menu Validation-----------
    menu = db.query(models.Menu).filter(models.Menu.menu_date == booking.booking_date).first()

    if not menu:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"The menu for {booking.booking_date} has not been set yet.")

    if booking.lunch_pick and not set(booking.lunch_pick).issubset(set(menu.lunch_options)):        # type: ignore
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="One or more of your lunch picks are not valid options on this day.")
    
    db_booking = db.query(models.Booking).filter(
        models.Booking.user_id == current_user.id,
        models.Booking.booking_date == booking.booking_date
    ).first()

    if not db_booking:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No booking found for user {current_user.id} on {booking.booking_date}"
        )

    try:
        db_booking.lunch_pick = booking.lunch_pick      # type: ignore
        db.commit()
        db.refresh(db_booking)
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Database error: {e}")
        
    return db_booking
    
#-----------------------------------------------------UPDATE DINNER BOOKINGS------------------------------------------------------#
@router.patch("/update-dinner", status_code=status.HTTP_200_OK, response_model=schemas.MealBookingOut)
def update_Dinner(booking: schemas.DinnerUpdate, db: Session = Depends(get_db), current_user: models.User = Depends(oauth2.get_current_user)):
    
    validate_booking_time(booking.booking_date)
    
    now_ist = datetime.now(IST)
    today_ist = now_ist.date()

    #----------Menu Validation-----------
    menu = db.query(models.Menu).filter(models.Menu.menu_date == booking.booking_date).first()

    if not menu:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"The menu for {booking.booking_date} has not been set yet.")

    if booking.dinner_pick and not set(booking.dinner_pick).issubset(set(menu.dinner_options)):     # type: ignore
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="One or more of your dinner picks are not valid options on this day.")
    
    if booking.booking_date == today_ist and now_ist.hour >= TODAY_CUTOFF_HOUR:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"Cannot book dinner for today after {TODAY_CUTOFF_HOUR}:00 IST.")
    
    db_booking = db.query(models.Booking).filter(
        models.Booking.user_id == current_user.id,
        models.Booking.booking_date == booking.booking_date
    ).first()

    if not db_booking:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No booking found for user {current_user.id} on {booking.booking_date}"
        )

    try:
        db_booking.dinner_pick = booking.dinner_pick        # type: ignore
        db.commit()
        db.refresh(db_booking)
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Database error: {e}")
        
    return db_booking

#----------------------------------------------------Wake Up Convenor------------------------------------------------------#
@router.post("/wake-convenor", status_code=status.HTTP_200_OK)
def wake_up_convenor(
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(oauth2.get_current_user)
):
    now_ist = datetime.now(IST)
    today_ist = now_ist.date()

    try:
        # ---------------- Cursor 1: Cooldown check (lock row) ----------------
        cooldown = db.query(models.Cooldown).filter(
            models.Cooldown.task_name == 'wake_convenor'
        ).with_for_update().first()

        if cooldown and cooldown.last_triggered_at:     # type: ignore
            if now_ist - cooldown.last_triggered_at < timedelta(minutes=1):     # type: ignore
                db.rollback()
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Convenors recently notified. Please wait a moment."
                )

        # ---------------- Cursor 2: Menu check ----------------
        target_date = today_ist + timedelta(days=1) if now_ist.hour >= 21 else today_ist

        menu_exists = db.query(models.Menu).filter(models.Menu.menu_date == target_date).first()
        
        if menu_exists:
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Menu is already set for the date."
            )

        # ---------------- Cursor 3: Update cooldown ----------------
        if cooldown:
            cooldown.last_triggered_at = now_ist        # type: ignore
        else:
            new_cooldown = models.Cooldown(task_name='wake_convenor', last_triggered_at=now_ist)
            db.add(new_cooldown)

        # ---------------- Cursor 4: Fetch convenors ----------------
        convenors = db.query(models.User).filter(models.User.role == 'convenor').all()

        # Commit only after ALL DB steps succeed
        db.commit()

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error: {str(e)}"
        )

    # ---------------- Background Tasks (outside DB transaction) ----------------
    if not convenors:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No convenors found."
        )

    # Convert to standard strings to avoid DetachedInstanceError in background thread
    tokens = [str(c.push_token) for c in convenors if c.push_token]     # type: ignore
    caller_name = str(current_user.name)
    convenor_names = [str(c.name) for c in convenors]

    if tokens:
        background_tasks.add_task(
            fcm_manager.send_notification,
            tokens,
            "Urgent: Menu Call",
            f"{caller_name} is asking for the menu!"
        )
        
    return {
        "message": "Notifications sent",
        "convenors": convenor_names
    }