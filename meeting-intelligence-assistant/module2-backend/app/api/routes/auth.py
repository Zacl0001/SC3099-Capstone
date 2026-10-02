# api/routes/auth.py
# Endpoints:
#
# POST /auth/register
# POST /auth/login
# GET /auth/me
# Responsibilities:
#
# Validate input
# Call auth service
# Return JWT/user information
# Don't put password hashing/business logic directly here.\

from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from app.db.database import get_db
from app.schemas.auth import RegisterRequest, UserResponse, LoginRequest, TokenResponse
from app.services.auth_service import create_user, authenticate_user, create_session, revoke_session
from app.api.routes.dependencies import get_current_user, bearer_scheme
from app.models.user import User


router = APIRouter(
    prefix="/api/auth",
    tags=["Authentication"],
)

@router.post("/register",
             response_model=UserResponse,
             status_code=201,
             )

def register(
    request:RegisterRequest,
  
    db: Session = Depends(get_db),
):

    try:
        return create_user(db, request.email, request.password)
    except ValueError as exc:
        raise HTTPException(
        status_code = 409,
       detail=str(exc),
    ) from exc

    except IntegrityError as exc:
        if(
            getattr(exc.orig, "sqlstate", None) == "23505"
            and exc.orig.diag.constraint_name == "users_email_key"
        ):
            raise HTTPException(
                status_code = 409,
                detail="Email already registered",
            )from exc

        raise

@router.post("/login", response_model=TokenResponse)
def login(
        request: LoginRequest,
        db: Session = Depends(get_db),
):

    user = authenticate_user(db, request.email, request.password)

    if user is None:
        raise HTTPException(
            status_code=401,
            detail="Invalid email or password",
        )

    token, expires_at = create_session(db, user.id)

    return TokenResponse(
        access_token = token,
        expires_at = expires_at,
    )

@router.get("/me", response_model=UserResponse)
def get_me(
    current_user: User = Depends(get_current_user),
):

    return current_user

@router.post("/logout", status_code=204)
def logout(
    current_user: User = Depends(get_current_user),
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
):

    if credentials is None:
        raise HTTPException(
            status_code=401,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    revoke_session(db, credentials.credentials, current_user.id)

    return Response(status_code=204)
