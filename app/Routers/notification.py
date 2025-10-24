from fastapi import APIRouter, status, HTTPException, Depends, Response
from .. import schemas, oauth2, database

router = APIRouter(
    prefix="/notifications",
    tags=['Notifications']
)

@router.post("/token", status_code=status.HTTP_204_NO_CONTENT)
def register_push_token(
    token_data: schemas.PushTokenUpdate, 
    conn=Depends(database.get_db_connection), 
    current_user: dict = Depends(oauth2.get_current_user)
):
    """
    Receives a push token from a user's device and saves it to their record
    in the 'users' table.
    """
    query = "UPDATE users SET push_token = %s WHERE id = %s"
    with conn.cursor() as cur:
        try:
            cur.execute(query, (token_data.token, current_user['id']))
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Database error: {e}")
    
    return Response(status_code=status.HTTP_204_NO_CONTENT)

