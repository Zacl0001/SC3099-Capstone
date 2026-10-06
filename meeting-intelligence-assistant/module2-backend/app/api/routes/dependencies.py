from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models.user import User
from app.services.auth_service import get_user_by_session_token

bearer_scheme = HTTPBearer(auto_error=False)

def get_current_user(
        credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
        db: Session = Depends(get_db),
) -> User:

    unauthorized = HTTPException(
        status_code=401,
        detail="Invalid or expired session",
        headers={"WWW-Authenticate" : "Bearer"},
    )

    if credentials is None:
        raise unauthorized

    user = get_user_by_session_token(db, credentials.credentials) #cred.cred gets token string

    if user is None:
        raise unauthorized

    return user
