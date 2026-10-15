# database/connection.py
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.exc import OperationalError

# Configuración de URLs
DATABASE_URL_LOCAL = "postgresql+psycopg2://postgres:123456@localhost:5433/BK_FAM" # PC-02-trabajo 
# "postgresql+psycopg2://postgres:1234@localhost:5432/BK_FAM" # PC-01-Casa
DATABASE_URL_NEON = os.getenv("DATABASE_URL")

# Configuración base para ambos engines
engine_kwargs = {
    "pool_pre_ping": True,
    "pool_size": 5,
    "max_overflow": 5,
    "pool_recycle": 1800
}

# 1. Intentar configurar la base de datos local primero
try:
    print("Intentando conectar a la base de datos local...")
    # Usamos un timeout corto para que no se quede colgado si la BD local está apagada
    local_engine = create_engine(
        DATABASE_URL_LOCAL, 
        connect_args={"connect_timeout": 3}, 
        **engine_kwargs
    )
    # Verificación real de la conexión
    with local_engine.connect() as conn:
        pass
    engine = local_engine
    print("¡Conectado exitosamente a la base de datos LOCAL!")

# 2. Si falla la local, pasamos a la de Neon (Web)
except OperationalError:
    print("No se pudo conectar a la BD local. Conectando a NEON (Web)...")
    if not DATABASE_URL_NEON:
        raise RuntimeError("DATABASE_URL de Neon no está configurada en las variables de entorno.")
    
    engine = create_engine(DATABASE_URL_NEON, **engine_kwargs)
    print("¡Conectado exitosamente a NEON!")

# Configuración de la sesión y Base de SQLAlchemy
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

Base = declarative_base()

