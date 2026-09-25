# models/distribucion_utilidades.py

from sqlalchemy import Column
from sqlalchemy import Integer
from sqlalchemy import Numeric
from sqlalchemy import String
from sqlalchemy import DateTime
from sqlalchemy import ForeignKey

from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from database.connection import Base

# para la Distribución ANUAL de utilidades 
class DistribucionUtilidades(Base):

    __tablename__ = "distribucion_utilidades"

    id = Column(
        Integer,
        primary_key=True,
        index=True
    )

    anio = Column(
        Integer,
        nullable=False
    )

    socio_id = Column(
        Integer,
        ForeignKey("socios.id"),
        nullable=False
    )

    utilidad = Column(
        Numeric(12, 2),
        nullable=False
    )

    porcentaje = Column(
        Numeric(8, 4),
        nullable=False
    )

    metodo = Column(
        String(30),
        nullable=False
    )

    fecha_registro = Column(
        DateTime,
        server_default=func.now()
    )

    socio = relationship(
        "Socio",
        back_populates="utilidades"
    )