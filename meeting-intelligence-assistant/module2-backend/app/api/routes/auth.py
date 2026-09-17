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

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.db.database import get_db
from app.schemas.auth import RegisterRequest, UserResponse
from app.services.auth_service import create_user


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