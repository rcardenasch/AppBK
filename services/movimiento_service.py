from decimal import Decimal
from models.accion import Accion
from models.movimiento import Movimiento
from models.periodo import Periodo
from models.prestamo import Prestamo
from services.interes_service import InteresService


from decimal import Decimal
from sqlalchemy import and_, or_

class MovimientoService:

    @staticmethod
    def registrar_movimiento(
        db,
        socio_id,
        accion_id,
        periodo_id,
        prestamo=None,
        aporte=0,
        cuota_pagada=0,
        multa=0,
        sobre=0,
        observacion=""
    ):
        from services.prestamo_service import PrestamoService

        aporte = Decimal(
            str(aporte or 0)
        ).quantize(
            Decimal("0.01")
        )

        cuota_pagada = Decimal(
            str(cuota_pagada or 0)
        ).quantize(
            Decimal("0.01")
        )

        multa = Decimal(
            str(multa or 0)
        ).quantize(
            Decimal("0.01")
        )

        sobre = Decimal(
            str(sobre or 0)
        ).quantize(
            Decimal("0.01")
        )

        datos = {
            "socio_id": socio_id,
            "accion_id": accion_id,
            "periodo_id": periodo_id,
            "aporte": aporte,
            "cuota_pagada": cuota_pagada,
            "multa": multa,
            "sobre": sobre,
            "observacion": observacion
        }

        # ==================================================
        # VERIFICAR PRÉSTAMOS DE LA ACCIÓN
        # ==================================================

        prestamos = (
            PrestamoService.obtener_prestamos_activos_accion(
                db,
                accion_id
            )
        )

        # ==================================================
        # SIN PRÉSTAMO
        # ==================================================

        if not prestamos:

            datos.update({
                "prestamo_id": None,
                "interes": Decimal("0.00"),
                "amortizacion": Decimal("0.00"),
                "saldo_prestamo": Decimal("0.00")
            })

            return datos

        # ==================================================
        # REFERENCIA AL PRÉSTAMO PRINCIPAL
        #
        # NO se utiliza para calcular interés.
        # ==================================================

        prestamo_referencia = (
            prestamo
            if prestamo
            else prestamos[0]
        )

        datos["prestamo_id"] = (
            prestamo_referencia.id
        )

        # ==================================================
        # CÁLCULO ÚNICO POR ACCIÓN
        # ==================================================

        resultado = (
            MovimientoService.calcular_movimiento_accion(
                db=db,
                accion_id=accion_id,
                periodo_id=periodo_id,
                aporte=aporte,
                cuota_pagada=cuota_pagada
            )
        )

        datos.update({
            "interes": resultado["interes"],
            "amortizacion": resultado["amortizacion"],
            "saldo_prestamo": resultado["saldo_prestamo"]
        })

        return datos

    @staticmethod
    def calcular_movimiento_accion(
        db,
        accion_id,
        periodo_id,
        aporte,
        cuota_pagada,
        multa_periodo_anterior_override=None,
        saldo_apertura_override=None
    ):
        """
        MOTOR FINANCIERO ÚNICO.
        REGLAS:
        1. saldo_apertura:
        - Normal: se obtiene de PrestamoService.
        - Edición: si se proporciona saldo_apertura_override,
            corresponde SOLO al saldo de préstamos restaurado.
        2. multa_periodo_anterior:
        - Normal: se obtiene automáticamente del movimiento
            del período cronológicamente anterior.
        - Si se proporciona override, se utiliza ese valor.
        3. La multa del período actual NO participa.
        4. Base de interés: saldo_apertura + multa_periodo_anterior
        5. Deuda: saldo_apertura + multa_periodo_anterior + préstamos_nuevos
        6. Amortización:
            cuota
            - aporte
            - interés
        7. Saldo final:  deuda - amortización
        """

        from services.prestamo_service import PrestamoService

        CENTAVOS = Decimal("0.01")

        # =========================================================
        # NORMALIZAR
        # =========================================================

        aporte = Decimal(
            str(aporte or 0)
        ).quantize(CENTAVOS)

        cuota_pagada = Decimal(
            str(cuota_pagada or 0)
        ).quantize(CENTAVOS)

        # =========================================================
        # VALIDAR PERÍODO
        # =========================================================

        periodo = (
            db.query(Periodo)
            .filter(
                Periodo.id == periodo_id
            )
            .first()
        )

        if not periodo:
            raise Exception(
                "Período no encontrado."
            )

        if periodo.cerrado:
            raise Exception(
                "El período está cerrado."
            )
        # =========================================================
        # VALIDAR ACCIÓN
        # =========================================================
        accion = (
            db.query(Accion)
            .filter(
                Accion.id == accion_id
            )
            .first()
        )

        if not accion:
            raise Exception(
                "Acción no encontrada."
            )
        # =========================================================
        # 1. SALDO APERTURA
        # =========================================================
        if saldo_apertura_override is not None:

            # IMPORTANTE:
            # Este saldo corresponde SOLO a préstamos.
            saldo_apertura = Decimal(
                str(
                    saldo_apertura_override or 0
                )
            ).quantize(CENTAVOS)

        else:

            saldo_apertura = (
                PrestamoService
                .obtener_saldo_apertura_accion(
                    db=db,
                    accion_id=accion_id,
                    periodo_id=periodo_id
                )
            )

            saldo_apertura = Decimal(
                str(
                    saldo_apertura or 0
                )
            ).quantize(CENTAVOS)

        # =========================================================
        # 2. MULTA DEL PERÍODO ANTERIOR
        # =========================================================

        if multa_periodo_anterior_override is not None:

            multa_periodo_anterior = Decimal(
                str(
                    multa_periodo_anterior_override or 0
                )
            ).quantize(CENTAVOS)

        else:

            # ESTA ES LA REGLA NORMAL.
            #
            # La función busca automáticamente la multa
            # del período cronológicamente anterior.

            multa_periodo_anterior = (
                MovimientoService
                .obtener_multa_periodo_anterior_accion(
                    db=db,
                    accion_id=accion_id,
                    periodo_id=periodo_id
                )
            )

            multa_periodo_anterior = Decimal(
                str(
                    multa_periodo_anterior or 0
                )
            ).quantize(CENTAVOS)

        # Nunca permitir multa negativa.

        if multa_periodo_anterior < Decimal("0.00"):
            multa_periodo_anterior = Decimal("0.00")

        # =========================================================
        # 3. BASE PARA INTERÉS
        # =========================================================

        saldo_base_interes = (
            saldo_apertura
            + multa_periodo_anterior
        ).quantize(CENTAVOS)

        # =========================================================
        # 4. PRÉSTAMOS DEL PERÍODO ACTUAL
        # =========================================================

        prestamos = (
            db.query(Prestamo)
            .filter(
                Prestamo.accion_id == accion_id
            )
            .order_by(
                Prestamo.fecha_prestamo.asc(),
                Prestamo.id.asc()
            )
            .all()
        )

        saldo_nuevos = Decimal("0.00")
        prestamos_nuevos = []

        for prestamo in prestamos:

            if prestamo.periodo_id != periodo_id:
                continue

            monto = Decimal(
                str(
                    prestamo.monto or 0
                )
            ).quantize(CENTAVOS)

            if monto <= Decimal("0.00"):
                continue

            saldo_nuevos += monto

            prestamos_nuevos.append(
                prestamo
            )

        saldo_nuevos = saldo_nuevos.quantize(CENTAVOS)

        # =========================================================
        # 5. INTERÉS
        # =========================================================

        if saldo_base_interes > Decimal("0.00"):

            interes = (
                InteresService.calcular_interes(
                    db,
                    saldo_base_interes
                )
            )

            interes = Decimal(
                str(
                    interes or 0
                )
            ).quantize(CENTAVOS)

        else:

            interes = Decimal("0.00")

        # =========================================================
        # 6. AMORTIZACIÓN
        # =========================================================

        amortizacion_calculada = (
            cuota_pagada
            - aporte
            - interes
        ).quantize(CENTAVOS)

        if amortizacion_calculada < Decimal("0.00"):
            amortizacion_calculada = Decimal("0.00")

        # =========================================================
        # 7. DEUDA TOTAL DEL PERÍODO
        # =========================================================

        saldo_deuda = (
            saldo_apertura
            + multa_periodo_anterior
            + saldo_nuevos
        ).quantize(CENTAVOS)

        # =========================================================
        # 8. LIMITAR AMORTIZACIÓN
        # =========================================================

        amortizacion = min(
            amortizacion_calculada,
            saldo_deuda
        ).quantize(CENTAVOS)

        # =========================================================
        # 9. SALDO FINAL
        # =========================================================

        saldo_final = (
            saldo_deuda
            - amortizacion
        ).quantize(CENTAVOS)

        if saldo_final < Decimal("0.00"):
            saldo_final = Decimal("0.00")

        # =========================================================
        # DEBUG
        # =========================================================

        print("\n==============================================")
        print("CALCULAR MOVIMIENTO ACCIÓN")
        print("==============================================")
        print(f"Acción                  : {accion_id}")
        print(f"Período                 : {periodo_id}")
        print(f"Saldo apertura préstamo : {saldo_apertura}")
        print(f"Multa período anterior  : {multa_periodo_anterior}")
        print(f"Base interés            : {saldo_base_interes}")
        print(f"Préstamos nuevos        : {saldo_nuevos}")
        print(f"Deuda total             : {saldo_deuda}")
        print(f"Aporte                  : {aporte}")
        print(f"Interés                 : {interes}")
        print(f"Cuota                   : {cuota_pagada}")
        print(f"Amortización            : {amortizacion}")
        print(f"Saldo final             : {saldo_final}")
        print("==============================================\n")

        # =========================================================
        # RESULTADO
        # =========================================================

        return {

            "accion_id": accion_id,
            "periodo_id": periodo_id,
            "saldo_apertura": saldo_apertura,
            "multa_periodo_anterior": multa_periodo_anterior,
            "saldo_base_interes": saldo_base_interes,
            "saldo_prestamos_nuevos": saldo_nuevos,
            "saldo_deuda": saldo_deuda,
            "saldo_prestamo": saldo_final,
            "aporte": aporte,
            "cuota_pagada": cuota_pagada,
            "interes": interes,
            "amortizacion": amortizacion,
            "prestamos_nuevos": prestamos_nuevos
        }
    
    # ====================================================
    # Obtener multa del periodo anterior para la accion
    # ====================================================
    @staticmethod
    def obtener_multa_periodo_anterior_accion(
        db,
        accion_id,
        periodo_id
    ):
        """
        Obtiene la multa registrada en el movimiento de la acción
        correspondiente al período inmediatamente anterior.

        Regla:
        - La multa se genera en el período actual.
        - NO afecta el saldo del mismo período.
        - Se incorpora como deuda al período siguiente.

        Por ejemplo:

            Enero:
                saldo = 7,228.50
                multa = 10.00

            Febrero:
                saldo apertura = 7,228.50
                multa anterior = 10.00
                deuda inicial = 7,238.50

        IMPORTANTE:
        Se busca por el período cronológicamente anterior,
        NO usando simplemente periodo_id - 1, porque los IDs
        no necesariamente representan continuidad mensual.
        """

        periodo_actual = (
            db.query(Periodo)
            .filter(
                Periodo.id == periodo_id
            )
            .first()
        )

        if not periodo_actual:
            raise Exception(
                f"No se encontró el período {periodo_id}."
            )

        # ======================================================
        # BUSCAR EL PERÍODO CRONOLÓGICAMENTE ANTERIOR
        # ======================================================

        periodo_anterior = (
            db.query(Periodo)
            .filter(
                or_(
                    Periodo.anio < periodo_actual.anio,
                    and_(
                        Periodo.anio == periodo_actual.anio,
                        Periodo.mes < periodo_actual.mes
                    )
                )
            )
            .order_by(
                Periodo.anio.desc(),
                Periodo.mes.desc()
            )
            .first()
        )

        if not periodo_anterior:
            return Decimal("0.00")

        # ======================================================
        # BUSCAR EL MOVIMIENTO DE ESA ACCIÓN
        # ======================================================

        movimiento_anterior = (
            db.query(Movimiento)
            .filter(
                Movimiento.accion_id == accion_id,
                Movimiento.periodo_id == periodo_anterior.id
            )
            .order_by(
                Movimiento.id.desc()
            )
            .first()
        )

        if not movimiento_anterior:
            return Decimal("0.00")

        # ======================================================
        # MULTA DEL PERÍODO ANTERIOR
        # ======================================================

        multa = Decimal(
            str(movimiento_anterior.multa or 0)
        ).quantize(Decimal("0.01"))

        if multa < Decimal("0.00"):
            multa = Decimal("0.00")

        # ======================================================
        # DEBUG
        # ======================================================

        print("\n==============================================")
        print("MULTA PERÍODO ANTERIOR")
        print("==============================================")
        print(f"Acción                  : {accion_id}")
        print(f"Período actual          : {periodo_actual.id}")
        print(
            f"Período anterior       : "
            f"{periodo_anterior.id} "
            f"({periodo_anterior.anio}-{periodo_anterior.mes:02d})"
        )
        print(f"Movimiento anterior     : {movimiento_anterior.id}")
        print(f"Multa anterior          : {multa}")
        print("==============================================\n")

        return multa
