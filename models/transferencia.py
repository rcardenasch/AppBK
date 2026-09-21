from sqlalchemy import (
    Column,
    Integer,
    Numeric,
    String,
    DateTime,
    ForeignKey
)

from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from database.connection import Base


class Transferencia(Base):

    __tablename__ = "transferencias"

    id = Column(Integer,primary_key=True,index=True)
    periodo_id = Column(Integer,ForeignKey("periodos.id"),nullable=False,index=True)
    socio_origen_id = Column(Integer,ForeignKey("socios.id"),nullable=False,index=True)
    socio_destino_id = Column(Integer,ForeignKey("socios.id"),nullable=False,index=True)
    monto = Column(Numeric(12, 2),nullable=False)
    estado = Column(String(20),nullable=False,default="CONFIRMADA")
    fecha_transferencia = Column(DateTime,server_default=func.now(),nullable=False)
    usuario_id = Column(Integer,ForeignKey("usuarios.id"),nullable=False)
    observacion = Column(String(500),nullable=True)

    periodo = relationship("Periodo",back_populates="transferencias")
    socio_origen = relationship("Socio",foreign_keys=[socio_origen_id])
    socio_destino = relationship("Socio",foreign_keys=[socio_destino_id])
    usuario = relationship("Usuario")