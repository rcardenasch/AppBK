# models/rol_permiso.py

from sqlalchemy import Column
from sqlalchemy import Integer
from sqlalchemy import ForeignKey

from sqlalchemy.orm import relationship

from database.connection import Base


class RolPermiso(Base):

    __tablename__ = "roles_permisos"

    rol_id = Column(Integer,ForeignKey("roles.id"),primary_key=True)
    permiso_id = Column(Integer,ForeignKey("permisos.id"),primary_key=True)

    rol = relationship("Rol",back_populates="permisos")
    permiso = relationship("Permiso",back_populates="roles")