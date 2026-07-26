from fastapi import APIRouter, Depends, HTTPException, status, Response
from sqlalchemy.orm import Session
from typing import List

from .. import schemas, oauth2, database, models

router = APIRouter(prefix="/users", tags=["User Management"])

#-----------------------------------Get All Users' Info--------------------------------------#
@router.get("/", response_model=List[schemas.UserOut])
def get_all_users(db: Session = Depends(database.get_db), current_user: models.User = Depends(oauth2.require_mess_committee_role)):
    
    users = db.query(models.User).order_by(models.User.id).all()
    
    return users

#---------------------------------UPDATE ROLE-------------------------------#
@router.patch("/{user_id}", response_model=schemas.UserOut)
def update_role(user_id: int, role_update: schemas.UserRoleUpdate, db: Session = Depends(database.get_db), current_user: models.User = Depends(oauth2.require_mess_committee_role)):
    
    user_to_update = db.query(models.User).filter(models.User.id == user_id).first()

    if not user_to_update:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=f"User with id {user_id} not found")
    
    if user_to_update.role == 'mess_committee': # type: ignore
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You can't change the role of a mess committee member")

    try:
        # Assuming role_update.role is an Enum, we use .value to store the string
        user_to_update.role = role_update.role.value    # type: ignore
        db.commit()
        db.refresh(user_to_update)
    except Exception as e:
        db.rollback()
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Database Error: {e}")
        
    return user_to_update

#-----------------------------------------------------DELETE USERS----------------------------------------------------------#
@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(user_id: int, db: Session = Depends(database.get_db), current_user: models.User = Depends(oauth2.require_mess_committee_role)):

    # Security Check: Prevent an admin from deleting their own account.
    if user_id == current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Action not allowed: You cannot delete your own account.")

    user_to_delete = db.query(models.User).filter(models.User.id == user_id).first()

    if not user_to_delete:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"User with id {user_id} not found!")

    if user_to_delete.role == 'mess_committee': # type: ignore
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Action not allowed: A mess committee member cannot be deleted")

    try:
        db.delete(user_to_delete)
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Database Error: {e}")
        
    # Return a 204 No Content response on successful deletion.
    return Response(status_code=status.HTTP_204_NO_CONTENT)

#----------------------------------------------------UPDATE MESS STATUS------------------------------------------------------#
@router.patch("/{user_id}/mess-status", response_model=schemas.UserOut)
def update_mess_status(user_id: int, status_update: schemas.UserMessStatusUpdate, db: Session = Depends(database.get_db), current_user: models.User = Depends(oauth2.require_mess_committee_role)):

    user_to_update = db.query(models.User).filter(models.User.id == user_id).first()

    if not user_to_update:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"User with id {user_id} is Not Found!")

    try:
        user_to_update.is_mess_active = status_update.is_mess_active    # type: ignore
        db.commit()
        db.refresh(user_to_update)
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Database error: {e}")
    
    return user_to_update