from fastapi import APIRouter, status, HTTPException, Depends, BackgroundTasks
from sqlalchemy.orm import Session
from datetime import date

from .. import schemas, oauth2, models
from ..database import get_db
from .. import fcm_manager

router = APIRouter(
    prefix="/menus",
    tags=['Menus']
)

# ENDPOINT 1: Set/Update the menu for a specific day (Convenor only) --------->Protected Router
@router.post("/", status_code=status.HTTP_201_CREATED, response_model=schemas.DailyMenuOut)
def set_daily_menu(menu: schemas.DailyMenuCreate, background_tasks: BackgroundTasks, db: Session = Depends(get_db), current_user: models.User = Depends(oauth2.require_convenor_role)):
        
    # Check if a menu for this date already exists
    db_menu = db.query(models.Menu).filter(models.Menu.menu_date == menu.menu_date).first()

    try:
        if db_menu:
            # UPDATE existing menu
            db_menu.lunch_options = menu.lunch_options # type: ignore
            db_menu.dinner_options = menu.dinner_options # type: ignore
            db_menu.set_by_user_id = current_user.id
        else:
            # INSERT new menu
            db_menu = models.Menu(
                menu_date=menu.menu_date,
                lunch_options=menu.lunch_options,
                dinner_options=menu.dinner_options,
                set_by_user_id=current_user.id
            )
            db.add(db_menu)
            
        db.commit()
        db.refresh(db_menu)
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Database error: {e}")
    
    # Cast date to string before sending to background thread
    menu_date_str = str(db_menu.menu_date)
    
    # After setting the menu, send a notification to all users.
    notification_title = "Menu Updated !!!"
    notification_body = f"The meal menu for {menu_date_str} has been set."
    background_tasks.add_task(
        fcm_manager.send_notification_to_all, notification_title, notification_body
    )
    
    return db_menu

# ENDPOINT 2: Get the menu for a specific day (Any logged-in user)
@router.get("/{menu_date}", response_model=schemas.DailyMenuOut)
def get_daily_menu(menu_date: date, db: Session = Depends(get_db), current_user: models.User = Depends(oauth2.get_current_user)):
        
    menu = db.query(models.Menu).filter(models.Menu.menu_date == menu_date).first()

    if not menu:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"No menu has been set for {menu_date}.")
        
    return menu