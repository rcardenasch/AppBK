from sqlalchemy import Column
from sqlalchemy import Integer
from sqlalchemy import Numeric
from sqlalchemy import DateTime
from sqlalchemy import ForeignKey
from sqlalchemy import Text
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from database.connection import Base

class Movimiento(Base):

    __tablename__ = "movimientos"

    id = Column(Integer,primary_key=True,index=True)
    socio_id = Column(Integer,ForeignKey("socios.id"),nullable=False)
    periodo_id = Column(Integer,ForeignKey("periodos.id"),nullable=False)
    aporte = Column(Numeric(12,2),default=0)
    cuota_pagada = Column(Numeric(12,2),default=0)
    interes = Column(Numeric(12,2),default=0)
    amortizacion = Column(Numeric(12,2),default=0)
    saldo_prestamo = Column(Numeric(12,2),default=0)
    multa = Column(Numeric(12,2),default=0)
    sobre = Column(Numeric(12,2),default=0)
    observacion = Column(Text)
    fecha_registro = Column(DateTime,server_default=func.now())
    prestamo_id = Column(Integer,ForeignKey("prestamos.id"),nullable=True)
    accion_id = Column(Integer,ForeignKey("acciones.id"))
    asistencia_id = Column(Integer,ForeignKey("asistencias.id"))

    socio = relationship("Socio",back_populates="movimientos")
    periodo = relationship("Periodo",back_populates="movimientos")
    prestamo = relationship("Prestamo",back_populates="movimientos")     
    accion = relationship("Accion",back_populates="movimientos")
    asistencia = relationship("Asistencia",back_populates="movimiento")  