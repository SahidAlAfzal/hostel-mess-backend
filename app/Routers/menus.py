from fastapi import APIRouter, status, HTTPException, Depends, BackgroundTasks
from datetime import date
import psycopg2
from psycopg2.errors import UniqueViolation

from .. import schemas, oauth2
from ..database import get_db_connection
from .. import fcm_manager

router = APIRouter(
    prefix="/menus",
    tags=['Menus']
)

# ENDPOINT 1: Set/Update the menu for a specific day (Convenor only) --------->Protected Router
@router.post("/", status_code=status.HTTP_201_CREATED, response_model=schemas.DailyMenuOut)
def set_daily_menu(menu: schemas.DailyMenuCreate, background_tasks: BackgroundTasks, conn=Depends(get_db_connection), current_user: dict = Depends(oauth2.require_convenor_role)):
        
    # This is an "UPSERT" operation. It will INSERT a new menu,
    # but if a menu for that date already exists, it will UPDATE it instead.
    query = """
        INSERT INTO daily_menus (menu_date, lunch_options, dinner_options, set_by_user_id)
        VALUES (%(menu_date)s, %(lunch_options)s, %(dinner_options)s, %(user_id)s)
        ON CONFLICT (menu_date) DO UPDATE SET
            lunch_options = EXCLUDED.lunch_options,
            dinner_options = EXCLUDED.dinner_options,
            set_by_user_id = EXCLUDED.set_by_user_id
        RETURNING menu_date, lunch_options, dinner_options, set_by_user_id;
    """
        
    params = menu.model_dump()
    params['user_id'] = current_user['id']

    with conn.cursor() as c:
        try:
            c.execute(query, params)
            new_menu = c.fetchone()
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Database error: {e}")
    
    # After setting the menu, send a notification to all users.
    notification_title = "Menu Updated !!!"
    notification_body = f"The meal menu for {new_menu['menu_date']} has been set."
    background_tasks.add_task(
        fcm_manager.send_notification_to_all, notification_title, notification_body
    )
    
    return new_menu


# ENDPOINT 2: Get the menu for a specific day (Any logged-in user)
@router.get("/{menu_date}", response_model=schemas.DailyMenuOut)
def get_daily_menu(menu_date: date, conn=Depends(get_db_connection), current_user: dict = Depends(oauth2.get_current_user)):
        
    query = "SELECT menu_date, lunch_options, dinner_options, set_by_user_id FROM daily_menus WHERE menu_date = %s"

    with conn.cursor() as cur:
        cur.execute(query, (menu_date,))
        menu = cur.fetchone()

    if not menu:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"No menu has been set for {menu_date}.")
        
    return menu
    
