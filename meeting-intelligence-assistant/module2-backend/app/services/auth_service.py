# Responsible for:
#
# Register user
# Validate credentials
# Hash passwords
# Generate JWT
# Retrieve user
# Routes should call this service rather than implementing authentication themselves.

from sqlalchemy import select
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from app.core.security import hash_password
from app.models.user import User


def get_user_by_email(db: Session, email: str) -> User | None:
    statement = select(User).where(User.email == email)
    return db.scalar(statement)

def create_user(db: Session, email:str, password: str) -> User:
    email = email.strip().lower()

    if get_user_by_email(db,email) is not None:
        raise ValueError("Email already registered, please login")

    user = User(
        email = email,
        password_hash = hash_password(password)
    )

    db.add(user)

    try:
        db.commit()

    except IntegrityError:
        db.rollback()
        raise

    db.refresh(user)

    return user