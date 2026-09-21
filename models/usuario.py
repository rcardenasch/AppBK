# models/usuario.py

from sqlalchemy import Column
from sqlalchemy import Integer
from sqlalchemy import String
from sqlalchemy import Boolean
from sqlalchemy import DateTime
from sqlalchemy import ForeignKey

from sqlalchemy.orm import relationship

from sqlalchemy.sql import func

from database.connection import Base
from flask_login import UserMixin


class Usuario(UserMixin,Base):

    __tablename__ = "usuarios"

    id = Column(Integer,primary_key=True,index=True)
    rol_id = Column(Integer,ForeignKey("roles.id"),nullable=False)       
    socio_id = Column(Integer, ForeignKey("socios.id"), nullable=True) # NUEVO FIELD: Enlaza al usuario con su perfil de socio (permite NULL para administradores)
    nombres = Column(String(150),nullable=False)
    usuario = Column(String(50),unique=True,nullable=False)
    correo = Column(String(120))
    password_hash = Column(String(255),nullable=False)
    ultimo_acceso = Column(DateTime)
    estado = Column(Boolean,default=True)
    fecha_registro = Column(DateTime,server_default=func.now())

    debe_cambiar_password = Column(
        Boolean,
        default=True,
        nullable=False
    )

    rol = relationship("Rol",back_populates="usuarios",lazy="joined")
    asistencias = relationship("Asistencia",back_populates="usuario")        
    socio = relationship("Socio", back_populates="usuario")# NUEVO: Relación directa para acceder a los datos del socio desde el usuario logueado

    # =========================================================
    # PERMISOS
    # =========================================================

    def tiene_permiso(self,modulo,accion):
        """
        Verifica si el usuario posee un permiso mediante
        el rol que tiene asignado.
        Uso:

            current_user.tiene_permiso(
                "distribucion",
                "confirmar"
            )
        """
        if not self.estado:
            return False

        if not self.rol:
            return False
        # -----------------------------------------------------
        # ROL ADMINISTRADOR
        # -----------------------------------------------------
        if (
            self.rol.nombre
            and
            self.rol.nombre.strip().lower()
            == "administrador"
        ):
            return True
        # -----------------------------------------------------
        # PERMISOS DEL ROL
        # -----------------------------------------------------
        for rol_permiso in self.rol.permisos:

            permiso = rol_permiso.permiso

            if not permiso:
                continue

            if (permiso.modulo == modulo and permiso.accion == accion):
                return True

        return False

