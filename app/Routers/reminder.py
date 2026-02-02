from fastapi import APIRouter,Depends,BackgroundTasks
from app import fcm_manager
from .. import database,oauth2
from .. import fcm_manager


router = APIRouter(prefix='/reminders',tags=['Reminders'])

@router.get("/remind")
def send_reminder(background_tasks: BackgroundTasks, conn = Depends(database.get_db_connection),current_user = Depends(oauth2.require_admin_role)):
    notification_title = "Reminder!"
    notification_body = "Please book your meal for tomorrow before going to bed."
    background_tasks.add_task(
        fcm_manager.send_notification_to_all, notification_title, notification_body
    )
    

    return {"message": "Reminder notifications are being sent in the background."}