# models/accion.py

from sqlalchemy import Column
from sqlalchemy import Integer
from sqlalchemy import String
from sqlalchemy import Numeric
from sqlalchemy import Date
from sqlalchemy import ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from database.connection import Base


class Accion(Base):

    __tablename__="acciones"

    id = Column(Integer,primary_key=True)
    socio_id = Column(Integer,ForeignKey("socios.id"),nullable=False)
    numero_accion = Column(String(20),nullable=False)
    valor = Column(Numeric(12,2),nullable=False)
    estado = Column(String(20),default="ACTIVO")
    fecha_registro = Column(Date,server_default=func.current_date())

    socio = relationship("Socio",back_populates="acciones")
    prestamos = relationship("Prestamo",back_populates="accion")
    movimientos = relationship("Movimiento",back_populates="accion")
    solicitudes = relationship("SolicitudPrestamo",back_populates="accion")