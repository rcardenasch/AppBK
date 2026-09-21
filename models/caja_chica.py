from datetime import datetime

from sqlalchemy import NUMERIC, Column, DateTime, ForeignKey, Text
from sqlalchemy import Integer
from sqlalchemy import Numeric
from sqlalchemy import String
from sqlalchemy import Boolean 

from database.connection import Base


class CajaChica(Base):

    __tablename__ = "caja_chica"

    id = Column(Integer, primary_key=True)
    nombre = Column(String(100),default="Caja chica")
    saldo_inicial = Column(Numeric(12, 2),default=0)
    saldo_actual = Column(Numeric(12, 2),default=0)
    activo = Column(Boolean,default=True)

class MovimientoCajaChica(Base):

    __tablename__ = "movimientos_caja_chica"

    id = Column(Integer, primary_key=True)
    caja_id = Column(Integer,ForeignKey("caja_chica.id"),nullable=False)
    periodo_id = Column(Integer,ForeignKey("periodos.id"),nullable=False)
    tipo = Column(String(20),nullable=False)
    # INGRESO
    # EGRESO
    # AJUSTE
    concepto = Column(String(200))
    monto = Column(Numeric(12, 2),nullable=False)
    fecha = Column(DateTime,default=datetime.now)
    observacion = Column(Text)