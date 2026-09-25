# models/permiso.py

from sqlalchemy import Column
from sqlalchemy import Integer
from sqlalchemy import String

from sqlalchemy.orm import relationship

from database.connection import Base


class Permiso(Base):

    __tablename__ = "permisos"

    id = Column(Integer,primary_key=True,index=True)
    modulo = Column(String(50),nullable=False)
    accion = Column(String(50),nullable=False)
    descripcion = Column(String(150))

    roles = relationship("RolPermiso",back_populates="permiso")