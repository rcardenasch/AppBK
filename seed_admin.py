import models

from models.usuario import Usuario
from models.rol import Rol

from services.auth_service import AuthService
from database.connection import SessionLocal


def inicializar_datos_sistema():

    db = SessionLocal()

    try:

        # =====================================================
        # 1. CREAR ROL ADMINISTRADOR
        # =====================================================

        rol = db.query(Rol).filter(
            Rol.nombre == "Administrador"
        ).first()

        if not rol:

            rol = Rol(
                nombre="Administrador",
                descripcion="Administrador General",
                estado=True
            )

            db.add(rol)
            db.flush()

            print("✓ Rol Administrador creado.")

        # =====================================================
        # 2. CREAR USUARIO ADMIN
        # =====================================================

        admin = db.query(Usuario).filter(
            Usuario.usuario == "admin"
        ).first()

        if not admin:

            admin = Usuario(
                nombres="Administrador",
                usuario="admin",
                correo="admin@bkfam.pe",
                password_hash=AuthService.hash_password("43737510"),
                rol_id=rol.id,
                estado=True,
                debe_cambiar_password=True
            )

            db.add(admin)

            print("✓ Usuario administrador creado.")

        else:

            print("✓ Usuario administrador ya existe.")

        db.commit()

        print("✓ Inicialización de seguridad completada.")

    except Exception:

        db.rollback()
        raise

    finally:

        db.close()