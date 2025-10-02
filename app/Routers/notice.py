from fastapi import APIRouter,Depends,HTTPException,status,Response
from .. import database,schemas,oauth2
import psycopg2
from typing import List

router = APIRouter(prefix='/notices',tags=['Notices'])



#----------------------------------------------------------POST NOTICE-------------------------------------------------------------#
@router.post("/",status_code=status.HTTP_201_CREATED,response_model=schemas.NoticeOut)
def create_notice(notice:schemas.NoticeCreate,conn = Depends(database.get_db_connection),current_user = Depends(oauth2.require_admin_role)):
    query = """
        INSERT INTO notices (title, content, posted_by_user_id)
        VALUES (%(title)s, %(content)s, %(user_id)s)
        RETURNING id, title, content, posted_by_user_id, created_at;
    """

    params = notice.model_dump()
    params['user_id'] = current_user['id']

    try:
        with conn.cursor() as c:
            c.execute(query,params)
            new_notice = c.fetchone()
            conn.commit()
    except Exception as e:
        conn.rollback()
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR,detail=f"Database Error: {e}")
    
    return new_notice

#-----------------------------------------------------------GET NOTICE------------------------------------------------------------#
@router.get("/",response_model=List[schemas.NoticeOut])
def get_all_notice(conn = Depends(database.get_db_connection),current_user = Depends(oauth2.get_current_user)):
    query = "SELECT * FROM notices ORDER BY created_at DESC LIMIT 10"

    with conn.cursor() as c:
        c.execute(query)
        notices = c.fetchall()

    return notices


#-------------------------------------------------DELETE NOTICE------------------------------------------------------#
@router.delete("/{notice_id}",status_code=status.HTTP_204_NO_CONTENT)
def delete_notice(notice_id: int,conn = Depends(database.get_db_connection),current_user: dict = Depends(oauth2.require_admin_role)):
    with conn.cursor() as c:
        c.execute("SELECT posted_by_user_id FROM notices WHERE id=%s",(notice_id,))
        postman = c.fetchone()

    if not postman:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,detail="Notice not found!")
    
    postman_id = postman['posted_by_user_id']

    if current_user['role'] == 'convenor' and postman_id != current_user['id']:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)
    

    query = "DELETE FROM notices WHERE id=%s"

    with conn.cursor() as c:
        try:
            c.execute(query,(notice_id,))
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR,detail=f"Database Error : {e}")
        
        # Return a 204 No Content response on successful deletion.
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    
        

