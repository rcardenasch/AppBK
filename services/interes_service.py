# services/interes_service.py

from decimal import Decimal
from math import ceil

from models.configuracion import Configuracion

class InteresService:

    @staticmethod
    def calcular_interes(db, saldo):

        saldo = Decimal(str(saldo or 0))

        if saldo <= 0:
            return Decimal("0.00")
        
        config = (
            db.query(Configuracion)
            .filter(Configuracion.estado == True)
            .first()
        )

        interes_porcentaje = (
            Decimal(
                str(config.interes_mensual)
            )
            if config
            else Decimal("0.01")
        )

        # ---------------------------------------------
        # INTERÉS
        # ---------------------------------------------

        interes_base = (
            saldo * interes_porcentaje
        )

        # ---------------------------------------------
        # REDONDEO A MÚLTIPLOS DE 0.50
        # ---------------------------------------------

        interes_final = (
            Decimal(
                ceil(
                    interes_base * Decimal("2")
                )
            )
            / Decimal("2")
        )

        return interes_final.quantize(
            Decimal("0.01")
        )
