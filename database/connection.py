# database/connection.py
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.orm import declarative_base

DATABASE_URL = (
<<<<<<< HEAD
    "postgresql+psycopg2://postgres:1234@localhost:5432/BK_FAM"
=======
    "postgresql+psycopg2://postgres:123456@localhost:5433/BK_FAM"
>>>>>>> 9735a76f2390c160db2f78f98c7a1d0957fb9f46
)

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_size=20,
    max_overflow=30
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

Base = declarative_base()