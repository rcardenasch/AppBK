from sqlalchemy import Column
from sqlalchemy import Integer
from sqlalchemy import Numeric
from sqlalchemy import String
from sqlalchemy import Date
from sqlalchemy import ForeignKey

from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from database.connection import Base


class SolicitudPrestamo(Base):

    __tablename__ = "solicitudes_prestamo"

    id = Column(Integer,primary_key=True,index=True)
    socio_id = Column(Integer,ForeignKey("socios.id"),nullable=False)
    fecha_solicitud = Column(Date,server_default=func.current_date())
    monto_solicitado = Column(Numeric(12, 2),nullable=False)
    monto_aprobado = Column(Numeric(12,2),default=0)
    prioridad = Column(Integer,default=0)
    score = Column(Numeric(10, 2),default=0)
    estado = Column(String(20),default="PENDIENTE",nullable=False)

    socio = relationship("Socio",back_populates="solicitudes")
    periodo_id = Column(Integer,ForeignKey("periodos.id"),nullable=False)
    accion_id = Column(Integer,ForeignKey("acciones.id"),nullable=False)
    accion = relationship("Accion",back_populates="solicitudes")
    periodo = relationship("Periodo",back_populates="solicitudes")