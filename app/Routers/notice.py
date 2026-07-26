from fastapi import APIRouter, Depends, HTTPException, status, Response, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List

from .. import database, schemas, oauth2, models
from .. import fcm_manager

router = APIRouter(prefix='/notices', tags=['Notices'])

#----------------------------------------------------------POST NOTICE-------------------------------------------------------------#
@router.post("/", status_code=status.HTTP_201_CREATED, response_model=schemas.NoticeOut)
def create_notice(notice: schemas.NoticeCreate, background_tasks: BackgroundTasks, db: Session = Depends(database.get_db), current_user: models.User = Depends(oauth2.require_admin_role)):
    
    new_notice = models.Notice(
        title=notice.title,
        content=notice.content,
        posted_by_user_id=current_user.id,
        name=current_user.name
    )

    try:
        db.add(new_notice)
        db.commit()
        db.refresh(new_notice)
    except Exception as e:
        db.rollback()
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Database Error: {e}")
    
    # Cast to primitive strings before passing to the background thread
    notice_title = str(new_notice.title)
    notice_content = str(new_notice.content)
    
    # After the notice is created, send a notification to all users.
    notification_title = f"New Notice: {notice_title}"
    notification_body = notice_content[:120] # Send the first 120 chars
    background_tasks.add_task(
        fcm_manager.send_notification_to_all, notification_title, notification_body
    )
    
    return new_notice

#-----------------------------------------------------------GET NOTICE------------------------------------------------------------#
@router.get("/", response_model=List[schemas.NoticeOut])
def get_all_notice(db: Session = Depends(database.get_db), current_user: models.User = Depends(oauth2.get_current_user)):
    
    # SQLAlchemy equivalent of: ORDER BY created_at DESC LIMIT 10
    notices = db.query(models.Notice).order_by(models.Notice.created_at.desc()).limit(10).all()

    return notices

#-------------------------------------------------DELETE NOTICE------------------------------------------------------#
@router.delete("/{notice_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_notice(notice_id: int, db: Session = Depends(database.get_db), current_user: models.User = Depends(oauth2.require_admin_role)):
    
    notice_to_delete = db.query(models.Notice).filter(models.Notice.id == notice_id).first()

    if not notice_to_delete:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notice not found!")
    
    # Convenors can only delete their own notices. Mess Committee members can delete any.
    if current_user.role == 'convenor' and notice_to_delete.posted_by_user_id != current_user.id: # type: ignore
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You can't delete this notice!")
    
    try:
        db.delete(notice_to_delete)
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Database Error : {e}")
        
    # Return a 204 No Content response on successful deletion.
    return Response(status_code=status.HTTP_204_NO_CONTENT)