from sqlalchemy import Column
from sqlalchemy import Integer
from sqlalchemy import Numeric
from sqlalchemy import Date
from sqlalchemy import Boolean

from sqlalchemy.orm import relationship

from database.connection import Base


class Periodo(Base):

    __tablename__ = "periodos"

    id = Column(Integer,primary_key=True,index=True)
    anio = Column(Integer,nullable=False)
    mes = Column(Integer,nullable=False)
    fecha_inicio = Column(Date,nullable=False)
    fecha_fin = Column(Date,nullable=False)
    saldo_caja = Column(Numeric(12,2),default=0)
    cerrado = Column(Boolean,default=False,nullable=False)

    movimientos = relationship("Movimiento",back_populates="periodo")
    prestamos = relationship("Prestamo",back_populates="periodo")
    fondo_utilidad = relationship("FondoUtilidades",back_populates="periodo",uselist=False)
    solicitudes = relationship("SolicitudPrestamo",back_populates="periodo")
    asistencias = relationship("Asistencia",back_populates="periodo",cascade="all, delete-orphan")
    transferencias = relationship("Transferencia",back_populates="periodo",cascade="all, delete-orphan")
