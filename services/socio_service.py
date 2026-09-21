from decimal import Decimal

class SocioService:

    @staticmethod
    def resumen_financiero(
        socio
    ):
        total_acciones = len(
            socio.acciones
        )

        valor_acciones = Decimal("0.00")
        deuda_total = Decimal("0.00")
        detalle=[]

        for accion in socio.acciones:
            
            valor_acciones += accion.valor
            deuda_accion = Decimal("0.00")
            for prestamo in accion.prestamos:

                if prestamo.estado=="ACTIVO":

                    deuda_accion += prestamo.saldo_actual

            deuda_total += deuda_accion

            detalle.append({

                "accion": accion.numero_accion,
                "valor": accion.valor,
                "deuda": deuda_accion

            })

        return {
            "acciones":total_acciones,
            "valor_acciones":valor_acciones,
            "deuda_total":deuda_total,
            "detalle":detalle

        }