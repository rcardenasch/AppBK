# models/socio.py

from sqlalchemy import Column
from sqlalchemy import Integer
from sqlalchemy import String
from sqlalchemy import Boolean
from sqlalchemy import Date

from sqlalchemy.orm import relationship

from database.connection import Base

from sqlalchemy.sql import func


class Socio(Base):

    __tablename__="socios"

    id = Column(Integer,primary_key=True,index=True)
    nombres = Column(String(200),nullable=False)
    documento = Column(String(20))
    telefono = Column(String(20))
    fecha_ingreso = Column(Date,server_default=func.current_date())
    estado = Column(Boolean,default=True)

    acciones = relationship("Accion",back_populates="socio")
    prestamos = relationship("Prestamo",back_populates="socio")
    movimientos = relationship("Movimiento",back_populates="socio")
    solicitudes = relationship("SolicitudPrestamo",back_populates="socio")
    utilidades = relationship("DistribucionUtilidades",back_populates="socio")
    asistencias = relationship("Asistencia",back_populates="socio")
    usuario = relationship("Usuario", back_populates="socio", uselist=False)# NUEVO: Relación inversa hacia Usuario (Un socio puede tener un usuario en el sistema)

    @property
    def total_acciones(self):
        """Devuelve la cantidad total de acciones que posee el socio"""
        return len(self.acciones) if self.acciones else 0

    @property
    def valor_total_acciones(self):
        """Opcional: Devuelve la suma del valor monetario de todas sus acciones"""
        return sum(a.valor for a in self.acciones if a.valor) if self.acciones else 0
