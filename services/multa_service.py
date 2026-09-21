from decimal import Decimal

from models.movimiento import Movimiento
from models.periodo import Periodo


class MultaService:

    @staticmethod
    def decimal(valor):
        if valor is None:
            return Decimal("0.00")

        return Decimal(str(valor)).quantize(
            Decimal("0.01")
        )

    # ==========================================================
    # OBTENER PERÍODO VIGENTE
    # ==========================================================

    @staticmethod
    def obtener_periodo_vigente(db):

        periodo = (
            db.query(Periodo)
            .filter(
                Periodo.cerrado == False
            )
            .order_by(
                Periodo.anio.desc(),
                Periodo.mes.desc()
            )
            .first()
        )

        return periodo

    # ==========================================================
    # ACTUALIZAR MULTA
    # ==========================================================

    @staticmethod
    def actualizar_multa(
        db,
        movimiento_id,
        multa,
        observacion
    ):

        movimiento = (
            db.query(Movimiento)
            .filter(
                Movimiento.id == movimiento_id
            )
            .first()
        )

        if not movimiento:
            raise Exception(
                "No se encontró el movimiento."
            )

        periodo = (
            db.query(Periodo)
            .filter(
                Periodo.id == movimiento.periodo_id
            )
            .first()
        )

        if not periodo:
            raise Exception(
                "No se encontró el período del movimiento."
            )

        # ------------------------------------------------------
        # SOLO SE PUEDE MODIFICAR EL PERÍODO ABIERTO
        # ------------------------------------------------------

        if periodo.cerrado:
            raise Exception(
                "No se puede modificar una multa "
                "de un período cerrado."
            )

        periodo_vigente = (
            MultaService
            .obtener_periodo_vigente(db)
        )

        if not periodo_vigente:
            raise Exception(
                "No existe un período vigente abierto."
            )

        if periodo.id != periodo_vigente.id:
            raise Exception(
                "Solo se pueden registrar multas "
                "en el período vigente."
            )

        multa = MultaService.decimal(multa)

        if multa < Decimal("0.00"):
            raise Exception(
                "La multa no puede ser negativa."
            )

        observacion = (
            observacion.strip()
            if observacion
            else None
        )

        # ------------------------------------------------------
        # IMPORTANTE
        #
        # SOLO modificamos:
        #
        #   multa
        #   observacion
        #
        # No tocamos ningún otro campo financiero.
        # ------------------------------------------------------

        movimiento.multa = multa
        movimiento.observacion = observacion

        db.flush()

        return movimiento