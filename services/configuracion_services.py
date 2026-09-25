# services/usuario_service.py

from sqlalchemy.exc import SQLAlchemyError

from database.connection import SessionLocal

from models.configuracion import Configuracion
from models.rol import Rol

from services.auth_service import AuthService


class UsuarioService:

    @staticmethod
    def listar():

        db = SessionLocal()

        try:

            return (
                db.query(Configuracion)
                .join(Rol)
                .order_by(
                    Configuracion.id
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
                Configuracion,
                id
            )

        finally:

            db.close()

    @staticmethod
    def crear(datos):

        db = SessionLocal()

        try:

            nuevo = Configuracion(
            
                aporte_minimo=datos["aporte_minimo"],
                sobre_por_accion=datos["sobre_por_accion"],
                interes_mensual=datos["interes_mensual"],
                metodo_distribucion=datos["metodo_distribucion"],
                multa_tardanza=datos["multa_tardanza"],
                multa_falta=datos["multa_falta"],

            )

            db.add(
                nuevo
            )

            db.commit()

            return True, "Configuración creado correctamente."

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

            configuracion = db.get(
                Configuracion,
                id
            )

            if not configuracion:

                return False, "Configuracion no encontrado."

            existe = (

                db.query(
                    Configuracion
                )

                .first()

            )

            if existe:

                return False, "La configuracion ya existe."

            configuracion.aporte_minimo = datos["aporte_minimo"]
            configuracion.sobre_por_accion = datos["sobre_por_accion"]
            configuracion.interes_mensual = datos["interes_mensual"]
            configuracion.metodo_distribucion = datos["metodo_distribucion"]
            configuracion.multa_falta = datos["multa_falta"]
            configuracion.multa_tardanza = datos["multa_tardanza"]

            db.commit()

            return True, "Configuración actualizada."

        except SQLAlchemyError as e:

            db.rollback()

            return False, str(e)

        finally:

            db.close()


    @staticmethod
    def activar(id):

        db = SessionLocal()

        try:

            configuracion = db.get(
                Configuracion,
                id
            )

            configuracion.estado = True

            db.commit()

            return True, "Configuracion activado."

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

            configuracion = db.get(
                Configuracion,
                id
            )

            configuracion.estado = False

            db.commit()

            return True, "Configuración desactivada."

        except SQLAlchemyError as e:

            db.rollback()

            return False, str(e)

        finally:

            db.close()