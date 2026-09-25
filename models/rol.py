# models/rol.py

from sqlalchemy import Column
from sqlalchemy import Integer
from sqlalchemy import String
from sqlalchemy import Boolean

from sqlalchemy.orm import relationship

from database.connection import Base


class Rol(Base):

    __tablename__ = "roles"

    id = Column(Integer,primary_key=True,index=True)
    nombre = Column(String(50),unique=True,nullable=False)
    descripcion = Column(String(200))
    estado = Column(Boolean,default=True)

    usuarios = relationship("Usuario",back_populates="rol")
    permisos = relationship("RolPermiso",back_populates="rol")