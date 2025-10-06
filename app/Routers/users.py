from fastapi import APIRouter,Depends,HTTPException,status,Response
from typing import List
from ..database import get_db_connection
from .. import schemas,oauth2


router = APIRouter(prefix="/users",tags=["User Management"])

#-----------------------------------Get All Users' Info--------------------------------------#
@router.get("/",response_model=List[schemas.UserOut])
def get_all_users(conn = Depends(get_db_connection), current_user: dict = Depends(oauth2.require_mess_committee_role)):
    query = "SELECT id, name, email, room_number, role, is_active, is_mess_active, created_at FROM users ORDER BY id;"

    with conn.cursor() as c:
        c.execute(query)
        users = c.fetchall()
    
    return users


#---------------------------------UPDATE CONVENOR-------------------------------#
@router.patch("/{user_id}",response_model=schemas.UserOut)
def update_convenor(user_id: int, role_update: schemas.UserRoleUpdate, conn = Depends(get_db_connection), current_user: dict = Depends(oauth2.require_mess_committee_role)):
    with conn.cursor() as cur:
        cur.execute("SELECT role FROM users WHERE id=%s",(user_id,))
        check_user = cur.fetchone()

    if not check_user:
        raise HTTPException(status.HTTP_404_NOT_FOUND,detail=f"User with id {user_id} not found")
    
    if check_user['role'] == 'mess_committee':
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,detail=f"You can't change the role of mess committee member")



    query = """UPDATE users SET role=%s
            WHERE id=%s
            RETURNING id, name, email, room_number, role, is_active, is_mess_active, created_at;"""
    with conn.cursor() as c:
        try:
            c.execute(query,(role_update.role.value,user_id))
            updated_user = c.fetchone()
        
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR,detail=f"Database Error : {e}")
        
    return updated_user




#-----------------------------------------------------DELETE USERS----------------------------------------------------------#
@router.delete("/{user_id}",status_code=status.HTTP_204_NO_CONTENT)
def delete_user(user_id : int, conn = Depends(get_db_connection),current_user: dict = Depends(oauth2.require_mess_committee_role)):

    # Security Check: Prevent an admin from deleting their own account.
    if user_id == current_user['id']:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Action not allowed: You cannot delete your own account.")


    with conn.cursor() as c:
        c.execute("SELECT role FROM users WHERE id=%s",(user_id,))
        user_to_delete = c.fetchone()


    if not user_to_delete:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,detail=f"User with id {user_id} not found!")


    if user_to_delete['role'] == 'mess_committee':
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,detail=f"Action not allowed: A mess committee member cannot be deleted")

    query = "DELETE FROM users WHERE id=%s;"


    with conn.cursor() as c:
        try:
            c.execute(query,(user_id,))
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR,detail=f"Database Error : {e}")
        
        # Return a 204 No Content response on successful deletion.
        return Response(status_code=status.HTTP_204_NO_CONTENT)



#----------------------------------------------------UPDATE MESS STATUS------------------------------------------------------#
@router.patch("/{user_id}/mess-status",response_model=schemas.UserOut)
def update_mess_status(user_id: int, status_update: schemas.UserMessStatusUpdate, conn = Depends(get_db_connection), current_user: dict = Depends(oauth2.require_mess_committee_role)):

    query = """UPDATE users SET is_mess_active=%s WHERE id=%s
    returning id, name, email, room_number, role, is_mess_active, created_at;
    """

    try:
        with conn.cursor() as cur:
            cur.execute(query,(status_update.is_mess_active,user_id))
            updated_user = cur.fetchone()

            if not updated_user:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,detail=f"User with id {user_id} is Not Found!")
            conn.commit()
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,detail=f"Database error : {e}")
    
    return updated_user

