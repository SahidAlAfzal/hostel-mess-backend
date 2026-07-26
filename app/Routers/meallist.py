from fastapi import APIRouter, status, HTTPException, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from datetime import date, datetime
from typing import List
import pytz
from collections import Counter # Used for efficiently counting items
import io  # Used for creating an in-memory file
import csv # Python's built-in CSV library

from .. import schemas, oauth2, models
from ..database import get_db

router = APIRouter(
    prefix="/meallist",
    tags=['Meal List']
)

IST = pytz.timezone('Asia/Kolkata')

# HELPER FUNCTION to avoid repeating code for processing database results
def process_meal_list_results(results: list, booking_date: date):
    """Takes raw DB results and processes them into the final response structure."""
    if not results:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail=f"No bookings found for {booking_date}.")

    lunch_bookings_count = 0
    dinner_bookings_count = 0
    all_lunch_items = []
    all_dinner_items = []
    formatted_bookings = []

    # Process results to get counts and item lists using ORM attribute access
    for row in results:
        formatted_bookings.append({
            "user_name": row.user_name,
            "room_number": row.room_number,
            "lunch_pick": row.lunch_pick,
            "dinner_pick": row.dinner_pick
        })
        
        if row.lunch_pick:
            lunch_bookings_count += 1
            all_lunch_items.extend(row.lunch_pick)
        if row.dinner_pick:
            dinner_bookings_count += 1
            all_dinner_items.extend(row.dinner_pick)

    # Use Counter to get the counts of each unique item
    lunch_item_counts = Counter(all_lunch_items)
    dinner_item_counts = Counter(all_dinner_items)

    # Structure the final response to match the Pydantic schema
    return {
        "booking_date": booking_date,
        "total_lunch_bookings": lunch_bookings_count,
        "total_dinner_bookings": dinner_bookings_count,
        "lunch_item_counts": dict(lunch_item_counts),
        "dinner_item_counts": dict(dinner_item_counts),
        "bookings": formatted_bookings
    }

# ENDPOINT 1: Get the meal list for TODAY (admin based Endpoint)
@router.get("/today", response_model=schemas.MealListOut)
def get_todays_meal_list(db: Session = Depends(get_db), current_user: models.User = Depends(oauth2.get_current_user)):
    
    now_ist = datetime.now(IST)
    today_ist = now_ist.date()

    results = db.query(
        models.User.name.label("user_name"),
        models.User.room_number,
        models.Booking.lunch_pick,
        models.Booking.dinner_pick
    ).join(
        models.User, models.Booking.user_id == models.User.id
    ).filter(
        models.Booking.booking_date == today_ist
    ).all()
    
    return process_meal_list_results(results, today_ist)

# ENDPOINT 2: Get the meal list for a SPECIFIC date
@router.get("/{booking_date}", response_model=schemas.MealListOut)
def get_meal_list_for_date(booking_date: date, db: Session = Depends(get_db), current_user: models.User = Depends(oauth2.get_current_user)):
    """
    Retrieves the detailed meal list and summary for a specific chosen date.
    """
    results = db.query(
        models.User.name.label("user_name"),
        models.User.room_number,
        models.Booking.lunch_pick,
        models.Booking.dinner_pick
    ).join(
        models.User, models.Booking.user_id == models.User.id
    ).filter(
        models.Booking.booking_date == booking_date
    ).all()
    
    return process_meal_list_results(results, booking_date)

# ENDPOINT 3: Get the meal list for TODAY (user based Endpoint)
@router.get("/me/today", response_model=schemas.MealListItem)
def my_meal(db: Session = Depends(get_db), current_user: models.User = Depends(oauth2.get_current_user)):

    now_ist = datetime.now(IST)
    today_ist = now_ist.date()

    result = db.query(
        models.User.name.label("user_name"),
        models.User.room_number,
        models.Booking.lunch_pick,
        models.Booking.dinner_pick
    ).join(
        models.User, models.Booking.user_id == models.User.id
    ).filter(
        models.Booking.booking_date == today_ist,
        models.User.id == current_user.id
    ).first()
    
    if result is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="You have not booked a meal for today yet!")
    
    return {
        "user_name": result.user_name,
        "room_number": result.room_number,
        "lunch_pick": result.lunch_pick,
        "dinner_pick": result.dinner_pick
    }

#----------------------------------------------------------DOWNLOAD MEAL LIST--------------------------------------------------------#
@router.get("/{booking_date}/download")
def download_meal_list_for_date(booking_date: date, db: Session = Depends(get_db), current_user: models.User = Depends(oauth2.get_current_user)):
    """
    Generates and returns a CSV file of all meal bookings for a specific date,
    including a summary of total counts.
    """
    # 1. Fetch the data with an ORM JOIN and order by student name
    results = db.query(
        models.User.name.label("user_name"),
        models.User.room_number,
        models.Booking.lunch_pick,
        models.Booking.dinner_pick
    ).join(
        models.User, models.Booking.user_id == models.User.id
    ).filter(
        models.Booking.booking_date == booking_date
    ).order_by(
        models.User.name
    ).all()

    if not results:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail=f"No bookings found for {booking_date} to download.")

    # 2. Calculate the total counts using the ORM results
    total_lunch = sum(1 for row in results if row.lunch_pick)
    total_dinner = sum(1 for row in results if row.dinner_pick)

    # 3. Create a CSV file in memory
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Write the summary rows at the top
    writer.writerow([f"Meal List Summary for: {booking_date}"])
    writer.writerow([]) # Blank row for spacing
    writer.writerow(["Total Lunch Bookings:", total_lunch])
    writer.writerow(["Total Dinner Bookings:", total_dinner])
    writer.writerow([]) # Blank row for spacing
    
    # Write the main header row
    writer.writerow(["Student Name", "Room Number", "Lunch Selection", "Dinner Selection"])
    
    # Write the data rows
    for row in results:
        lunch_picks = ', '.join(row.lunch_pick or [])
        dinner_picks = ', '.join(row.dinner_pick or [])
        writer.writerow([row.user_name, row.room_number, lunch_picks, dinner_picks])
    
    # 4. Prepare and return the response
    output.seek(0)
    headers = {"Content-Disposition": f"attachment; filename=meal_list_{booking_date}.csv"}
    return StreamingResponse(output, headers=headers, media_type="text/csv")