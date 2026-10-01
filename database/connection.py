# database/connection.py


#DATABASE_URL = (
    #"postgresql+psycopg2://postgres:1234@localhost:5432/BK_FAM" # PC-01-Casa
    #"postgresql+psycopg2://postgres:123456@localhost:5433/BK_FAM" # PC-02-trabajo
#)

import os

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base


DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL no está configurada")


engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=5,
    pool_recycle=1800
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

Base = declarative_base()