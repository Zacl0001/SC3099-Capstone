# Responsible for:
#
# Register user
# Validate credentials
# Hash passwords
# Generate JWT
# Retrieve user
# Routes should call this service rather than implementing authentication themselves.

from sqlalchemy import select, delete
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from app.core.security import hash_password, verify_password, generate_session_token, hash_session_token
from app.models.user import User
from app.models.auth_session import AuthSession
from datetime import datetime, timedelta, timezone


DUMMY_PASSWORD_HASH = hash_password("password")


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

def authenticate_user(
        db: Session,
        email: str,
        password: str,
)-> User | None:
    email = email.strip().lower()
    user = get_user_by_email(db,email)

    stored_hash = ( 
        user.password_hash
        if user is not None
        else DUMMY_PASSWORD_HASH
    )

    password_matches = verify_password(password, stored_hash)

    if user is None or not password_matches:
        return None

    return user

def create_session(db:Session, user_id: int) -> tuple[str, datetime]:
    token = generate_session_token()
    expires_at = datetime.now(timezone.utc) + timedelta(hours=24) 

    auth_session = AuthSession(
        user_id= user_id,
        token_hash = hash_session_token(token),
        expires_at=expires_at,
    )

    db.add(auth_session)

    try:
        db.commit()
    except Exception:
        db.rollback()
        raise

    return token, expires_at

def get_user_by_session_token(
        db: Session,
        token: str,

)-> User | None:

    token_hash = hash_session_token(token)

    statement = select(AuthSession).where(
        AuthSession.token_hash == token_hash,
        AuthSession.expires_at > datetime.now(timezone.utc),
    )

    auth_session = db.scalar(statement)

    if auth_session is None:
        return None

    return db.get(User, auth_session.user_id)


def revoke_session(db: Session, token: str, user_id: int) -> None:
    statement = delete(AuthSession).where(
        AuthSession.token_hash == hash_session_token(token),
        AuthSession.user_id == user_id
    )

    try:
        db.execute(statement)
        db.commit()

    except Exception:
        db.rollback()
        raise