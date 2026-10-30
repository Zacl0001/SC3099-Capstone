# Responsible for:
#
# Database connection
# SQLAlchemy engine
# Session creation
# Base model
# Conceptually:
#
# DATABASE_URL
#       ↓
# SQLAlchemy
#       ↓
# PostgreSQL
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.core.config import DATABASE_URL

engine = create_engine(DATABASE_URL, pool_pre_ping=True)

SessionLocal = sessionmaker(bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    with SessionLocal() as session:
        yield session
