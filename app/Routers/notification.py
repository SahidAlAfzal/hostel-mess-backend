from fastapi import APIRouter, status, HTTPException, Depends, Response
from sqlalchemy.orm import Session

from .. import schemas, oauth2, database, models

router = APIRouter(
    prefix="/notifications",
    tags=['Notifications']
)

@router.post("/token", status_code=status.HTTP_204_NO_CONTENT)
def register_push_token(
    token_data: schemas.PushTokenUpdate, 
    db: Session = Depends(database.get_db), 
    current_user: models.User = Depends(oauth2.get_current_user)
):
    """
    Receives a push token from a user's device and saves it to their record
    in the 'users' table.
    """
    user = db.query(models.User).filter(models.User.id == current_user.id).first()
    
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    
    try:
        user.push_token = token_data.token # type: ignore
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Database error: {e}")
    
    return Response(status_code=status.HTTP_204_NO_CONTENT)