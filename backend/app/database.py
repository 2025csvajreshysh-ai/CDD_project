import os
from pathlib import Path
from sqlmodel import SQLModel, create_engine, Session
from app.config import settings

# Normalize database URL (e.g. Supabase postgres:// -> postgresql:// for SQLAlchemy)
db_url = settings.DATABASE_URL
if db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)

# Ensure database directory exists if using sqlite
if "sqlite" in db_url:
    db_path = db_url.replace("sqlite:///", "").replace("sqlite://", "")
    db_dir = Path(db_path).parent
    if db_dir and not db_dir.exists():
        db_dir.mkdir(parents=True, exist_ok=True)
    connect_args = {"check_same_thread": False}
    engine = create_engine(db_url, echo=False, connect_args=connect_args)
else:
    # MySQL / PostgreSQL connection
    engine = create_engine(
        db_url,
        echo=False,
        pool_pre_ping=True,
        pool_recycle=3600
    )

def create_db_and_tables():
    SQLModel.metadata.create_all(engine)

def get_session():
    with Session(engine) as session:
        yield session
