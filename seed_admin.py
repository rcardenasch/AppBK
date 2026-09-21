import models

# MODELOS
from models.socio import Socio
from models.accion import Accion
from models.prestamo import Prestamo
from models.movimiento import Movimiento
from models.periodo import Periodo
from models.fondo_utilidades import FondoUtilidades
from models.distribucion_utilidades import DistribucionUtilidades
from models.solicitud_prestamo import SolicitudPrestamo
from models.configuracion import Configuracion

# Seguridad
from models.usuario import Usuario
from models.rol import Rol
from models.permiso import Permiso
from models.rol_permiso import RolPermiso

from services.auth_service import AuthService
from database.connection import SessionLocal

db = SessionLocal()

try:

    rol = db.query(Rol).filter(
        Rol.nombre == "Administrador"
    ).first()

    if not rol:

        rol = Rol(

            nombre="Administrador",

            descripcion="Administrador General"

        )

        db.add(rol)

        db.commit()

        db.refresh(rol)

    existe = db.query(Usuario).filter(

        Usuario.usuario == "admin"

    ).first()

    if not existe:

        admin = Usuario(

            nombres="Administrador",
            usuario="admin",
            correo="admin@bkfam.pe",
            password_hash=AuthService.hash_password("43737510"),
            rol_id=rol.id

        )

        db.add(admin)
        db.commit()
        print("Administrador creado.")

    else:

        print("Ya existe.")

finally:

    db.close()