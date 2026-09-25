from decimal import Decimal

from database.connection import SessionLocal

from models.socio import Socio
from models.accion import Accion
from models.fondo_utilidades import FondoUtilidades
from models.distribucion_utilidades import DistribucionUtilidades


class UtilidadesService:

    @staticmethod
    def obtener_fondo_anual(anio):

        db = SessionLocal()

        try:

            fondos = db.query(
                FondoUtilidades
            ).join(
                FondoUtilidades.periodo
            ).filter(
                FondoUtilidades.periodo.has(
                    anio=anio
                )
            ).all()

            total = sum(
                Decimal(f.total or 0)
                for f in fondos
            )

            return total

        finally:

            db.close()

    @staticmethod
    def simular_igualitario(anio):

        db = SessionLocal()

        try:

            total_fondo = UtilidadesService.obtener_fondo_anual(
                anio
            )

            socios = db.query(
                Socio
            ).filter(
                Socio.estado == True
            ).all()

            if not socios:
                return []

            monto = (
                total_fondo /
                len(socios)
            )

            resultado = []

            for socio in socios:

                resultado.append({

                    "socio_id": socio.id,
                    "socio": socio.nombres,

                    "utilidad": round(
                        float(monto), 2
                    )
                })

            return resultado

        finally:

            db.close()

    @staticmethod
    def simular_participacion(anio):

        db = SessionLocal()

        try:

            total_fondo = UtilidadesService.obtener_fondo_anual(
                anio
            )

            acciones = db.query(
                Accion
            ).all()

            total_acciones = sum(
                a.cantidad
                for a in acciones
            )

            if total_acciones == 0:
                return []

            resultado = []

            for accion in acciones:

                porcentaje = (
                    accion.cantidad /
                    total_acciones
                )

                utilidad = (
                    total_fondo *
                    Decimal(str(porcentaje))
                )

                resultado.append({

                    "socio_id":  accion.socio_id,
                    "acciones":  accion.cantidad,
                    "porcentaje": round(porcentaje * 100,2),
                    "utilidad":   round(float(utilidad),2)

                })

            return resultado

        finally:

            db.close()

    @staticmethod
    def distribuir_utilidades(
        anio,
        metodo
    ):

        db = SessionLocal()

        try:

            if metodo == "IGUALITARIO":

                distribucion = (
                    UtilidadesService
                    .simular_igualitario(
                        anio
                    )
                )

            else:

                distribucion = (
                    UtilidadesService
                    .simular_participacion(
                        anio
                    )
                )

            for item in distribucion:

                registro = (
                    DistribucionUtilidades(

                        anio=anio,
                        socio_id=item["socio_id"],

                        utilidad=item["utilidad"],
                        porcentaje=item.get("porcentaje",0),
                        metodo=metodo
                    )
                )

                db.add(
                    registro
                )

            db.commit()

            return {

                "success": True,

                "metodo": metodo,

                "registros":
                    len(distribucion)
            }

        except Exception as e:

            db.rollback()

            return {

                "success": False,

                "error": str(e)
            }

        finally:

            db.close()