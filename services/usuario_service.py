# services/usuario_service.py

from sqlalchemy.exc import SQLAlchemyError

from database.connection import SessionLocal

from models.usuario import Usuario
from models.rol import Rol

from services.auth_service import AuthService


class UsuarioService:

    @staticmethod
    def listar():

        db = SessionLocal()

        try:

            return (
                db.query(Usuario)
                .join(Rol)
                .order_by(
                    Usuario.nombres
                )
                .all()
            )

        finally:

            db.close()

    ###################################################

    @staticmethod
    def obtener(id):

        db = SessionLocal()

        try:

            return db.get(
                Usuario,
                id
            )

        finally:

            db.close()

    ###################################################

    @staticmethod
    def listar_roles():

        db = SessionLocal()

        try:

            return (
                db.query(Rol)
                .filter(
                    Rol.estado == True
                )
                .order_by(
                    Rol.nombre
                )
                .all()
            )

        finally:

            db.close()

    ###################################################

    @staticmethod
    def crear(datos):

        db = SessionLocal()

        try:

            existe = db.query(
                Usuario
            ).filter(
                Usuario.usuario == datos["usuario"]
            ).first()

            if existe:

                return False, "El usuario ya existe."

            nuevo = Usuario(

                nombres=datos["nombres"],

                usuario=datos["usuario"],

                correo=datos["correo"],

                rol_id=int(
                    datos["rol_id"]
                ),

                password_hash=AuthService.hash_password(
                    datos["password"]
                ),

                estado=True

            )

            db.add(
                nuevo
            )

            db.commit()

            return True, "Usuario creado correctamente."

        except SQLAlchemyError as e:

            db.rollback()

            return False, str(e)

        finally:

            db.close()

    ###################################################

    @staticmethod
    def actualizar(id, datos):

        db = SessionLocal()

        try:

            usuario = db.get(
                Usuario,
                id
            )

            if not usuario:

                return False, "Usuario no encontrado."

            existe = (

                db.query(
                    Usuario
                )

                .filter(
                    Usuario.usuario == datos["usuario"],
                    Usuario.id != id
                )

                .first()

            )

            if existe:

                return False, "El nombre de usuario ya existe."

            usuario.nombres = datos["nombres"]

            usuario.usuario = datos["usuario"]

            usuario.correo = datos["correo"]

            usuario.rol_id = int(
                datos["rol_id"]
            )

            usuario.estado = (

                True

                if datos.get("estado")

                else False

            )

            db.commit()

            return True, "Usuario actualizado."

        except SQLAlchemyError as e:

            db.rollback()

            return False, str(e)

        finally:

            db.close()

    ###################################################

    @staticmethod
    def reset_password(id, password):

        db = SessionLocal()

        try:

            usuario = db.get(
                Usuario,
                id
            )

            if not usuario:

                return False, "Usuario no encontrado."

            usuario.password_hash = (

                AuthService.hash_password(
                    password
                )

            )

            db.commit()

            return True, "Contraseña actualizada."

        except SQLAlchemyError as e:

            db.rollback()

            return False, str(e)

        finally:

            db.close()

    ###################################################

    @staticmethod
    def activar(id):

        db = SessionLocal()

        try:

            usuario = db.get(
                Usuario,
                id
            )

            usuario.estado = True

            db.commit()

            return True, "Usuario activado."

        except SQLAlchemyError as e:

            db.rollback()

            return False, str(e)

        finally:

            db.close()

    ###################################################

    @staticmethod
    def desactivar(id):

        db = SessionLocal()

        try:

            usuario = db.get(
                Usuario,
                id
            )

            usuario.estado = False

            db.commit()

            return True, "Usuario desactivado."

        except SQLAlchemyError as e:

            db.rollback()

            return False, str(e)

        finally:

            db.close()

    ###################################################

    @staticmethod
    def estadisticas():

        db = SessionLocal()

        try:

            total = db.query(
                Usuario
            ).count()

            activos = (

                db.query(
                    Usuario
                )

                .filter(
                    Usuario.estado == True
                )

                .count()

            )

            inactivos = (

                db.query(
                    Usuario
                )

                .filter(
                    Usuario.estado == False
                )

                .count()

            )

            administradores = (

                db.query(
                    Usuario
                )

                .join(Rol)

                .filter(
                    Rol.nombre == "Administrador"
                )

                .count()

            )

            return {

                "total": total,

                "activos": activos,

                "inactivos": inactivos,

                "administradores": administradores

            }

        finally:

            db.close()