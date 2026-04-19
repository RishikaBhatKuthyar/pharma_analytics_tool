# database.py
# Handles PostgreSQL connection and user table.
# SQLAlchemy creates the users table automatically on first run.

import os
from sqlalchemy import create_engine, Column, String, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime

# Use external URL locally, internal URL on Render
# External URL works from anywhere, internal only works within Render's network
DATABASE_URL = os.getenv("DATABASE_URL_EXTERNAL") or os.getenv("DATABASE_URL")

# Create SQLAlchemy engine
engine = create_engine(DATABASE_URL)

# Session factory — used to create DB sessions in auth.py
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class for all models
Base = declarative_base()

# ── Users table ────────────────────────────────────────────────────────────
class UserModel(Base):
    __tablename__ = "users"

    user_id      = Column(String, primary_key=True)
    email        = Column(String, unique=True, nullable=False, index=True)
    name         = Column(String, nullable=False)
    hashed_password = Column(String, nullable=False)
    created_at   = Column(DateTime, default=datetime.utcnow)

def init_db():
    """
    Creates all tables if they don't exist yet.
    Called once when the FastAPI app starts.
    Safe to call multiple times — won't overwrite existing data.
    """
    Base.metadata.create_all(bind=engine)
    print("✅ Database tables ready")

def get_db():
    """
    Dependency that provides a DB session.
    Automatically closes the session when done.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()