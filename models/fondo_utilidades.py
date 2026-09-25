# models/fondo_utilidades.py

from sqlalchemy import Column
from sqlalchemy import Integer
from sqlalchemy import Numeric
from sqlalchemy import DateTime
from sqlalchemy import ForeignKey
from sqlalchemy.orm import relationship

from sqlalchemy.sql import func

from database.connection import Base


class FondoUtilidades(Base):

    __tablename__ = "fondo_utilidades"

    id = Column(
        Integer,
        primary_key=True,
        index=True
    )

    periodo_id = Column(
        Integer,
        ForeignKey("periodos.id"),
        nullable=False
    )

    intereses = Column(
        Numeric(12, 2),
        default=0
    )

    multas = Column(
        Numeric(12, 2),
        default=0
    )

    sobres = Column(
        Numeric(12, 2),
        default=0
    )

    total = Column(
        Numeric(12, 2),
        default=0
    )

    fecha_registro = Column(
        DateTime,
        server_default=func.now()
    )

    periodo = relationship(
    "Periodo",
    back_populates="fondo_utilidad"
    )