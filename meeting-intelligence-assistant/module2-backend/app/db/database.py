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
import os 
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

load_dotenv(Path(__file__).resolve().parents[2] /".env")

engine = create_engine(os.environ["DATABASE_URL"],
                       pool_pre_ping=True,
                       )

SessionLocal = sessionmaker(bind=engine)

class Base(DeclarativeBase):
    pass

def get_db():
    with SessionLocal() as session:
        yield session