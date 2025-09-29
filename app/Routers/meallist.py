from fastapi import APIRouter, status, HTTPException, Depends
from fastapi.responses import StreamingResponse
from datetime import date
from typing import List
from collections import Counter # Used for efficiently counting items
import io  # Used for creating an in-memory file
import csv # Python's built-in CSV library

from .. import schemas, oauth2
from ..database import get_db_connection

router = APIRouter(
    prefix="/meallist",
    tags=['Meal List']
)

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

    # Process results to get counts and item lists
    for row in results:
        if row['lunch_pick']:
            lunch_bookings_count += 1
            all_lunch_items.extend(row['lunch_pick'])
        if row['dinner_pick']:
            dinner_bookings_count += 1
            all_dinner_items.extend(row['dinner_pick'])

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
        "bookings": results
    }




# ENDPOINT 1: Get the meal list for TODAY (admin based Endpoint)
@router.get("/today", response_model=schemas.MealListOut)
def get_todays_meal_list(conn=Depends(get_db_connection), current_user: dict = Depends(oauth2.require_admin_role)):
    
    today_date = date.today()
    query = """
        SELECT u.name as user_name, u.room_number, mb.lunch_pick, mb.dinner_pick
        FROM meal_bookings AS mb JOIN users AS u ON mb.user_id = u.id
        WHERE mb.booking_date = %s;
    """
    with conn.cursor() as cur:
        cur.execute(query, (today_date,))
        results = cur.fetchall()
    
    return process_meal_list_results(results, today_date)




# ENDPOINT 2: Get the meal list for a SPECIFIC date
@router.get("/{booking_date}", response_model=schemas.MealListOut)
def get_meal_list_for_date(booking_date: date, conn=Depends(get_db_connection), current_user: dict = Depends(oauth2.require_admin_role)):
    """
    Retrieves the detailed meal list and summary for a specific chosen date.
    """
    query = """
        SELECT u.name as user_name, u.room_number, mb.lunch_pick, mb.dinner_pick
        FROM meal_bookings AS mb JOIN users AS u ON mb.user_id = u.id
        WHERE mb.booking_date = %s;
    """
    with conn.cursor() as cur:
        cur.execute(query, (booking_date,))
        results = cur.fetchall()
    
    return process_meal_list_results(results, booking_date)





# ENDPOINT 1: Get the meal list for TODAY (user based Endpoint)
@router.get("/me/today", response_model=schemas.MealListItem)
def my_meal(conn = Depends(get_db_connection),current_user: dict = Depends(oauth2.get_current_user)):
    query = """
        SELECT u.name as user_name, u.room_number, mb.lunch_pick, mb.dinner_pick
        FROM meal_bookings AS mb JOIN users AS u ON mb.user_id = u.id
        WHERE mb.booking_date = %s AND u.id=%s;
    """
    with conn.cursor() as cur:
        cur.execute(query, (date.today(),current_user['id']))
        results = cur.fetchone()
    
    if results is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND,detail="You have not booked a meal for today yet!")
    
    return results




#----------------------------------------------------------DOWNLOAD MEAL LIST--------------------------------------------------------#
@router.get("/{booking_date}/download")
def download_meal_list_for_date(booking_date: date, conn=Depends(get_db_connection), current_user: dict = Depends(oauth2.require_convenor_role)):
    """
    Generates and returns a CSV file of all meal bookings for a specific date,
    including a summary of total counts.
    """
    # 1. Fetch the data
    query = """
        SELECT u.name as user_name, u.room_number, mb.lunch_pick, mb.dinner_pick
        FROM meal_bookings AS mb JOIN users AS u ON mb.user_id = u.id
        WHERE mb.booking_date = %s ORDER BY u.name;
    """
    with conn.cursor() as cur:
        cur.execute(query, (booking_date,))
        results = cur.fetchall()

    if not results:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail=f"No bookings found for {booking_date} to download.")

    # 2. Calculate the total counts
    total_lunch = sum(1 for row in results if row['lunch_pick'])
    total_dinner = sum(1 for row in results if row['dinner_pick'])

    # 3. Create a CSV file in memory
    output = io.StringIO()
    writer = csv.writer(output)
    
    # --- NEW: Write the summary rows at the top ---
    writer.writerow([f"Meal List Summary for: {booking_date}"])
    writer.writerow([]) # Blank row for spacing
    writer.writerow(["Total Lunch Bookings:", total_lunch])
    writer.writerow(["Total Dinner Bookings:", total_dinner])
    writer.writerow([]) # Blank row for spacing
    
    # Write the main header row
    writer.writerow(["Student Name", "Room Number", "Lunch Selection", "Dinner Selection"])
    
    # Write the data rows
    for row in results:
        lunch_picks = ', '.join(row['lunch_pick'] or [])
        dinner_picks = ', '.join(row['dinner_pick'] or [])
        writer.writerow([row['user_name'], row['room_number'], lunch_picks, dinner_picks])
    
    # 4. Prepare and return the response
    output.seek(0)
    headers = {"Content-Disposition": f"attachment; filename=meal_list_{booking_date}.csv"}
    return StreamingResponse(output, headers=headers, media_type="text/csv")

