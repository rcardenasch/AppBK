from sqlalchemy import Column, func
from sqlalchemy import Integer
from sqlalchemy import Numeric
from sqlalchemy import String
from sqlalchemy import Date
from sqlalchemy import ForeignKey
from sqlalchemy.orm import relationship

from database.connection import Base

class Prestamo(Base):

    __tablename__ = "prestamos"

    id = Column(Integer,primary_key=True,index=True)
    socio_id = Column(Integer,ForeignKey("socios.id"),nullable=False)
    fecha_prestamo = Column(Date,server_default=func.now())
    cuota_minima = Column(Numeric(12,2),nullable=False)
    monto = Column(Numeric(12,2),nullable=False)
    saldo_interes = Column(Numeric(12,2),default=0)
    saldo_actual = Column(Numeric(12,2),default=0)
    tasa_interes = Column(Numeric(5,2),nullable=False)
    accion_id = Column(Integer,ForeignKey("acciones.id"),nullable=False)
    estado = Column(String(20),default="ACTIVO")

    socio = relationship("Socio",back_populates="prestamos" )
    accion = relationship("Accion",back_populates="prestamos")
    movimientos = relationship("Movimiento", back_populates="prestamo")
    periodo = relationship("Periodo",back_populates="prestamos")


    periodo_id = Column(Integer,ForeignKey("periodos.id"), nullable=False)

    @property
    def porcentaje_pagado(self):
        if self.monto == 0:
            return 0

        return round(
            (self.monto - self.saldo_actual) * 100 / self.monto,
            2
        )