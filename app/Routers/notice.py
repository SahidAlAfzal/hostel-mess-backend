from fastapi import APIRouter,Depends,HTTPException,status,Response,BackgroundTasks
from .. import database,schemas,oauth2
import psycopg2
from typing import List
from .. import fcm_manager

router = APIRouter(prefix='/notices',tags=['Notices'])



#----------------------------------------------------------POST NOTICE-------------------------------------------------------------#
@router.post("/",status_code=status.HTTP_201_CREATED,response_model=schemas.NoticeOut)
def create_notice(notice:schemas.NoticeCreate,background_tasks: BackgroundTasks, conn = Depends(database.get_db_connection), current_user = Depends(oauth2.require_admin_role)):
    query = """
        INSERT INTO notices (title, content, posted_by_user_id, name)
        VALUES (%(title)s, %(content)s, %(user_id)s, %(name)s)
        RETURNING id, title, content, name ,posted_by_user_id, created_at;
    """

    params = notice.model_dump()
    params['user_id'] = current_user['id']
    params['name'] = current_user['name']

    try:
        with conn.cursor() as c:
            c.execute(query,params)
            new_notice = c.fetchone()
            conn.commit()
    except Exception as e:
        conn.rollback()
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR,detail=f"Database Error: {e}")
    
    # After the notice is created, send a notification to all users.
    notification_title = f"New Notice: {new_notice['title']}"
    notification_body = new_notice['content'][:120] # Send the first 120 chars
    background_tasks.add_task(
        fcm_manager.send_notification_to_all, notification_title, notification_body
    )
    
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
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,detail="You can't delete this notice!")
    

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

    
        

