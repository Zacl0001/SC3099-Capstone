# Endpoints:
#
# GET /meetings
# POST /meetings
# GET /meetings/{id}
# DELETE /meetings/{id}
# Responsible for meeting CRUD.

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.api.routes.dependencies import get_current_user
from app.db.database import get_db
from app.models.user import User
from app.schemas.meeting import MeetingResponse
from app.services.meeting_service import upload_meeting, list_meetings

router = APIRouter(prefix="/api/meetings", tags=["Meetings"])

@router.post("/upload", response_model=MeetingResponse, status_code=201)
def upload_meeting_endpoint(
    title: str = Form(..., min_length=1, max_length=255), file: UploadFile = File(...), current_user: User = Depends(get_current_user), db: Session = Depends(get_db), 
): # ... -> required
    title = title.strip()

    if not title:
        raise HTTPException(status_code=422 , detail="title cannot be blank")


    try:
        return upload_meeting(db, current_user.id, title, file)

    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    finally:                                                                                                                                                                                   
        file.file.close()

@router.get("", response_model=list[MeetingResponse])
def list_meetings_endpoint(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):

    return list_meetings(db,current_user.id)