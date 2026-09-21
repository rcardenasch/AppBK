from sqlalchemy import NUMERIC, Column
from sqlalchemy import Integer
from sqlalchemy import Numeric
from sqlalchemy import String
from sqlalchemy import Boolean 

from database.connection import Base


class Configuracion(Base):

    __tablename__ = "configuracion"

    id = Column(Integer,primary_key=True,index=True)
    aporte_minimo = Column(Numeric(12, 2),nullable=False)    
    sobre_por_accion = Column(Numeric(12, 2),nullable=False)
    interes_mensual = Column(Numeric(5, 2),nullable=False)
    metodo_distribucion = Column(String(20),nullable=False)
    multa_tardanza = Column( NUMERIC(12, 2),nullable=False)
    multa_falta = Column(NUMERIC(12, 2),nullable=False)
    estado=Column(Boolean,default=True)