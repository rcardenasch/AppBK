from flask_sqlalchemy import SQLAlchemy
from datetime import date
from sqlalchemy import Column, Date, DateTime,Integer,Numeric,String, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from database.connection import Base

class Asistencia(Base):

    __tablename__ = "asistencias"

    __table_args__ = (

        UniqueConstraint(
            "periodo_id",
            "socio_id",
            name="uq_asistencia_periodo_socio"
        ),

    )

    id = Column(Integer, primary_key=True, autoincrement=True)

    periodo_id = Column(Integer,ForeignKey("periodos.id"),nullable=False)
    socio_id = Column(Integer,ForeignKey("socios.id"),nullable=False)
    usuario_id = Column(Integer,ForeignKey("usuarios.id"),nullable=False)
    estado = Column(String(20),nullable=False)
    acciones = Column(Integer,nullable=False)
    multa = Column(Numeric(12,2),default=0,nullable=False)
    observacion = Column(String(100))
    fecha_registro = Column(DateTime,server_default=func.now())

    periodo = relationship("Periodo",back_populates="asistencias")
    socio = relationship("Socio",back_populates="asistencias")
    usuario = relationship("Usuario",back_populates="asistencias")
    movimiento = relationship("Movimiento",back_populates="asistencia",uselist=False)