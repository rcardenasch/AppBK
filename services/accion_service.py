from decimal import Decimal

class AccionService:

    @staticmethod
    def resumen_accion(
        accion
    ):
        prestamos = accion.prestamos
        deuda = Decimal("0.00")
        cuotas = Decimal("0.00")

        for p in prestamos:
            if p.estado=="ACTIVO":
                deuda += p.saldo_actual

        return {

            "accion_id": accion.id,
            "numero_accion": accion.numero_accion,
            "valor": accion.valor,
            "deuda": deuda,
            "prestamos": prestamos

        }