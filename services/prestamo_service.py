# services/prestamo_service.py

# services/prestamo_service.py
from datetime import date
from decimal import Decimal

from sqlalchemy import func, or_, and_

from models.movimiento import Movimiento
from models.periodo import Periodo
from models.prestamo import Prestamo
from models.accion import Accion

from database.connection import SessionLocal
from services.interes_service import InteresService
from services.movimiento_service import MovimientoService


def calcular_amortizacion(cuota_pagada, aporte, interes):
    """
    La cuota pagada incluye:
        aporte + interés + amortización
    """
    amortizacion = Decimal(str(cuota_pagada)) \
                 - Decimal(str(aporte)) \
                 - Decimal(str(interes))

    if amortizacion < 0:
        amortizacion = Decimal("0.00")

    return amortizacion


def calcular_nuevo_saldo(saldo_actual, amortizacion):

    saldo = Decimal(str(saldo_actual)) - Decimal(str(amortizacion))

    if saldo < 0:
        saldo = Decimal("0.00")

    return saldo

class PrestamoService:

    @staticmethod
    def obtener_saldo_apertura_accion(
        db,
        accion_id,
        periodo_id
    ):
        """
        Obtiene el saldo de capital de APERTURA de una acción.

        REGLAS:

        1. Una acción puede tener múltiples préstamos.
        2. La apertura es la SUMA de los saldos actuales
        de todos los préstamos pertenecientes a períodos
        anteriores al período actual.
        3. Los préstamos creados en el período actual
        NO participan en la apertura ni en el interés.
        4. No utiliza Movimiento.saldo_prestamo para determinar
        la apertura.
        5. No utiliza Prestamo.saldo_interes.
        6. La multa del período anterior se obtiene aparte y
        se agrega solamente a la base de interés.
        """

        # =====================================================
        # PERÍODO ACTUAL
        # =====================================================

        periodo_actual = (
            db.query(Periodo)
            .filter(
                Periodo.id == periodo_id
            )
            .first()
        )

        if not periodo_actual:
            raise Exception(
                "Período no encontrado."
            )

        # =====================================================
        # OBTENER TODOS LOS PRÉSTAMOS DE LA ACCIÓN
        #
        # IMPORTANTE:
        # Se relaciona con Periodo para comparar
        # AÑO + MES, no simplemente el ID.
        # =====================================================

        prestamos = (
            db.query(Prestamo)
            .join(
                Periodo,
                Prestamo.periodo_id == Periodo.id
            )
            .filter(
                Prestamo.accion_id == accion_id,
                or_(
                    Periodo.anio < periodo_actual.anio,
                    and_(
                        Periodo.anio == periodo_actual.anio,
                        Periodo.mes < periodo_actual.mes
                    )
                )
            )
            .order_by(
                Prestamo.fecha_prestamo.asc(),
                Prestamo.id.asc()
            )
            .all()
        )

        # =====================================================
        # SUMAR SALDOS DE TODOS LOS PRÉSTAMOS ANTERIORES
        # =====================================================

        saldo_apertura = Decimal("0.00")

        for prestamo in prestamos:

            saldo = Decimal(
                str(
                    prestamo.saldo_actual or 0
                )
            ).quantize(
                Decimal("0.01")
            )

            if saldo > 0:
                saldo_apertura += saldo

        saldo_apertura = saldo_apertura.quantize(
            Decimal("0.01")
        )

        # =====================================================
        # DEBUG
        # =====================================================

        print("\n==============================================")
        print("SALDO APERTURA ACCIÓN")
        print("==============================================")
        print(f"Acción              : {accion_id}")
        print(f"Período             : {periodo_id}")
        print(
            f"Saldo apertura     : "
            f"{saldo_apertura}"
        )

        for prestamo in prestamos:

            print(
                f"  Préstamo {prestamo.id} "
                f"| período={prestamo.periodo_id} "
                f"| saldo={prestamo.saldo_actual}"
            )

        print("==============================================\n")

        return saldo_apertura

  
    #
    # método para obtener todos los préstamos de una acción
    #
    @staticmethod
    def obtener_prestamos_activos_accion(
        db,
        accion_id
    ):
        """
        Obtiene todos los préstamos activos con saldo
        mayor a cero pertenecientes a una acción.
        """

        prestamos = (
            db.query(Prestamo)
            .filter(
                Prestamo.accion_id == accion_id,
                Prestamo.estado == "ACTIVO",
                Prestamo.saldo_actual > 0
            )
            .order_by(
                Prestamo.id.asc()
            )
            .all()
        )

        return prestamos


    # -----------------------------------------------------
    # RESTAURAR AMORTIZACIÓN DE UN MOVIMIENTO
    # -----------------------------------------------------
    @staticmethod
    def restaurar_amortizacion_movimiento(db, movimiento):
        """
        Revierte la amortización que tenía el movimiento antes de editarlo.

        REGLAS:

        1. Prestamo.saldo_actual = SOLO CAPITAL.
        2. La multa anterior NO forma parte del capital.
        3. La restauración debe ser IDÉNTICA aunque el movimiento
        sea editado varias veces.
        4. Si los datos vienen de la lógica anterior y la multa
        quedó contaminando Prestamo.saldo_actual, se corrige
        UNA SOLA VEZ.
        5. Después de la primera edición ya no se vuelve a descontar
        la multa.
        6. La amortización anterior se restaura FIFO.
        """

        CENTAVOS = Decimal("0.01")

        # =====================================================
        # 1. AMORTIZACIÓN ANTERIOR
        # =====================================================

        amortizacion_anterior = Decimal(
            str(
                movimiento.amortizacion or 0
            )
        ).quantize(CENTAVOS)

        if amortizacion_anterior < Decimal("0.00"):
            amortizacion_anterior = Decimal("0.00")

        # =====================================================
        # 2. OBTENER PERÍODO
        # =====================================================

        periodo = (
            db.query(Periodo)
            .filter(
                Periodo.id == movimiento.periodo_id
            )
            .first()
        )

        if not periodo:
            raise Exception(
                "Período no encontrado."
            )

        if periodo.cerrado:
            raise Exception(
                "No se puede restaurar un movimiento "
                "de un período cerrado."
            )

        # =====================================================
        # 3. MULTA DEL PERÍODO ANTERIOR
        # =====================================================

        multa_anterior = (
            MovimientoService
            .obtener_multa_periodo_anterior_accion(
                db=db,
                accion_id=movimiento.accion_id,
                periodo_id=movimiento.periodo_id
            )
        )

        multa_anterior = Decimal(
            str(
                multa_anterior or 0
            )
        ).quantize(CENTAVOS)

        if multa_anterior < Decimal("0.00"):
            multa_anterior = Decimal("0.00")

        # =====================================================
        # 4. OBTENER PRÉSTAMOS ANTERIORES
        #
        # SOLO préstamos anteriores al período editado.
        # =====================================================

        prestamos = (
            db.query(Prestamo)
            .join(
                Periodo,
                Prestamo.periodo_id == Periodo.id
            )
            .filter(
                Prestamo.accion_id == movimiento.accion_id,
                or_(
                    Periodo.anio < periodo.anio,
                    and_(
                        Periodo.anio == periodo.anio,
                        Periodo.mes < periodo.mes
                    )
                )
            )
            .order_by(
                Prestamo.fecha_prestamo.asc(),
                Prestamo.id.asc()
            )
            .all()
        )

        # =====================================================
        # 5. CASO SIN PRÉSTAMOS ANTERIORES
        # =====================================================

        if not prestamos:

            deuda_multa_restaurada = min(
                amortizacion_anterior,
                multa_anterior
            ).quantize(CENTAVOS)

            db.flush()

            print("\n==============================================")
            print("RESTAURAR AMORTIZACIÓN - SOLO MULTA")
            print("==============================================")
            print(
                f"Movimiento             : "
                f"{movimiento.id}"
            )
            print(
                f"Acción                 : "
                f"{movimiento.accion_id}"
            )
            print(
                f"Período                : "
                f"{movimiento.periodo_id}"
            )
            print(
                f"Amortización anterior  : "
                f"{amortizacion_anterior}"
            )
            print(
                f"Multa anterior         : "
                f"{multa_anterior}"
            )
            print(
                f"Multa restaurada       : "
                f"{deuda_multa_restaurada}"
            )
            print("==============================================\n")

            return {
                "ok": True,
                "accion_id": movimiento.accion_id,
                "periodo_id": movimiento.periodo_id,
                "amortizacion_restaurada": Decimal("0.00"),
                "prestamos_restaurados": 0,
                "saldo_total_restaurado": Decimal("0.00"),
                "saldo_multa_restaurado": deuda_multa_restaurada,
                "solo_multa": True
            }

        # =====================================================
        # 6. SALDO ACTUAL DE CAPITAL
        #
        # IMPORTANTE:
        # aquí obtenemos solamente los préstamos anteriores.
        # =====================================================

        saldo_capital_actual = Decimal("0.00")

        for prestamo in prestamos:

            saldo = Decimal(
                str(
                    prestamo.saldo_actual or 0
                )
            ).quantize(CENTAVOS)

            if saldo > Decimal("0.00"):
                saldo_capital_actual += saldo

        saldo_capital_actual = (
            saldo_capital_actual
        ).quantize(CENTAVOS)

        # =====================================================
        # 7. PRÉSTAMOS NUEVOS DEL PERÍODO ACTUAL
        #
        # El saldo_prestamo del movimiento puede incluirlos,
        # pero esos préstamos NO se restauran aquí.
        # =====================================================

        prestamos_nuevos = (
            db.query(Prestamo)
            .filter(
                Prestamo.accion_id == movimiento.accion_id,
                Prestamo.periodo_id == movimiento.periodo_id
            )
            .all()
        )

        saldo_nuevos = Decimal("0.00")

        for prestamo in prestamos_nuevos:

            monto = Decimal(
                str(
                    prestamo.monto or 0
                )
            ).quantize(CENTAVOS)

            if monto > Decimal("0.00"):
                saldo_nuevos += monto

        saldo_nuevos = saldo_nuevos.quantize(
            CENTAVOS
        )
        # =====================================================
        # 8. DETERMINAR CÓMO SE APLICÓ LA AMORTIZACIÓN ANTERIOR
        # =====================================================
        #
        # La amortización anterior pudo haber sido aplicada:
        #
        #   a) completamente al capital
        #   b) parcialmente a la multa y el resto al capital
        #   c) completamente a la multa
        #
        # Además, existen movimientos antiguos donde la multa
        # pudo haber quedado incorporada al saldo del préstamo.
        #
        # Por eso NO asumimos cómo se hizo.
        #
        # Lo reconstruimos comparando:
        #
        #   saldo total del movimiento anterior
        #   contra
        #   capital actualmente almacenado.
        #
        # Esto permite que la edición sea idempotente.
        # =====================================================

        saldo_movimiento_anterior = Decimal(
            str(
                movimiento.saldo_prestamo or 0
            )
        ).quantize(CENTAVOS)

        # -----------------------------------------------------
        # PRÉSTAMOS NUEVOS DEL MISMO PERÍODO
        #
        # No forman parte del capital de apertura que estamos
        # restaurando, pero sí pueden estar incluidos en
        # movimiento.saldo_prestamo.
        # -----------------------------------------------------

        prestamos_nuevos = (
            db.query(Prestamo)
            .filter(
                Prestamo.accion_id == movimiento.accion_id,
                Prestamo.periodo_id == movimiento.periodo_id
            )
            .all()
        )

        saldo_nuevos = Decimal("0.00")

        for prestamo in prestamos_nuevos:

            monto = Decimal(
                str(
                    prestamo.monto or 0
                )
            ).quantize(CENTAVOS)

            if monto > Decimal("0.00"):
                saldo_nuevos += monto

        saldo_nuevos = saldo_nuevos.quantize(CENTAVOS)

        # -----------------------------------------------------
        # SALDO TOTAL DEL MOVIMIENTO CORRESPONDIENTE A LA
        # APERTURA + MULTA.
        #
        # Quitamos únicamente los préstamos nuevos.
        # -----------------------------------------------------

        saldo_total_anterior = (
            saldo_movimiento_anterior
            - saldo_nuevos
        ).quantize(CENTAVOS)

        if saldo_total_anterior < Decimal("0.00"):
            saldo_total_anterior = Decimal("0.00")


        # =====================================================
        # 9. DETERMINAR MULTA QUE QUEDÓ PENDIENTE
        # =====================================================
        #
        # Si:
        #
        #   saldo_total_anterior - capital_actual = multa pendiente
        #
        # entonces podemos saber cuánto de la multa fue pagado
        # con la amortización anterior.
        #
        # Esto funciona para los tres casos:
        #
        #   A) No se pagó multa
        #   B) Se pagó parte de la multa
        #   C) Se pagó toda la multa
        # =====================================================

        multa_pendiente_inferida = (
            saldo_total_anterior
            - saldo_capital_actual
        ).quantize(CENTAVOS)

        if multa_pendiente_inferida < Decimal("0.00"):
            multa_pendiente_inferida = Decimal("0.00")

        if multa_pendiente_inferida > multa_anterior:
            multa_pendiente_inferida = multa_anterior


        # =====================================================
        # 10. DETERMINAR MULTA PAGADA
        # =====================================================

        multa_pagada_anterior = (
            multa_anterior
            - multa_pendiente_inferida
        ).quantize(CENTAVOS)

        if multa_pagada_anterior < Decimal("0.00"):
            multa_pagada_anterior = Decimal("0.00")


        # =====================================================
        # 11. DETERMINAR AMORTIZACIÓN QUE REALMENTE AFECTÓ
        #     AL CAPITAL
        # =====================================================

        amortizacion_capital_anterior = (
            amortizacion_anterior
            - multa_pagada_anterior
        ).quantize(CENTAVOS)

        if amortizacion_capital_anterior < Decimal("0.00"):
            amortizacion_capital_anterior = Decimal("0.00")


        print("\n==============================================")
        print("RESTAURACIÓN DE AMORTIZACIÓN")
        print("==============================================")
        print(
            f"Movimiento              : "
            f"{movimiento.id}"
        )
        print(
            f"Amortización anterior   : "
            f"{amortizacion_anterior}"
        )
        print(
            f"Multa anterior          : "
            f"{multa_anterior}"
        )
        print(
            f"Saldo movimiento       : "
            f"{saldo_movimiento_anterior}"
        )
        print(
            f"Préstamos nuevos       : "
            f"{saldo_nuevos}"
        )
        print(
            f"Saldo total anterior   : "
            f"{saldo_total_anterior}"
        )
        print(
            f"Capital actual          : "
            f"{saldo_capital_actual}"
        )
        print(
            f"Multa pendiente inferida: "
            f"{multa_pendiente_inferida}"
        )
        print(
            f"Multa pagada anterior  : "
            f"{multa_pagada_anterior}"
        )
        print(
            f"Amortización capital   : "
            f"{amortizacion_capital_anterior}"
        )
        print("==============================================\n")


        # =====================================================
        # 12. RESTAURAR SOLO LA PARTE QUE AFECTÓ AL CAPITAL
        # =====================================================

        pendiente = amortizacion_capital_anterior
        restaurada = Decimal("0.00")
        prestamos_restaurados = 0

        for prestamo in prestamos:

            if pendiente <= Decimal("0.00"):
                break

            saldo_actual = Decimal(
                str(
                    prestamo.saldo_actual or 0
                )
            ).quantize(CENTAVOS)

            restaurar = pendiente

            prestamo.saldo_actual = (
                saldo_actual + restaurar
            ).quantize(CENTAVOS)

            prestamo.estado = "ACTIVO"

            pendiente = (
                pendiente - restaurar
            ).quantize(CENTAVOS)

            restaurada += restaurar
            prestamos_restaurados += 1

            print(
                f"  CAPITAL RESTAURADO -> "
                f"Préstamo {prestamo.id} "
                f"| +{restaurar} "
                f"| capital={prestamo.saldo_actual}"
            )

        pendiente = pendiente.quantize(CENTAVOS)
        restaurada = restaurada.quantize(CENTAVOS)

        if pendiente > Decimal("0.00"):
            raise Exception(
                "No fue posible restaurar completamente "
                "la amortización de capital anterior. "
                f"Pendiente: S/ {pendiente}"
            )

        db.flush()

        saldo_restaurado = (
            db.query(
                func.coalesce(
                    func.sum(
                        Prestamo.saldo_actual
                    ),
                    0
                )
            )
            .filter(
                Prestamo.accion_id == movimiento.accion_id,
                Prestamo.periodo_id < movimiento.periodo_id,
                Prestamo.saldo_actual > 0
            )
            .scalar()
        )

        saldo_restaurado = Decimal(
            str(
                saldo_restaurado or 0
            )
        ).quantize(CENTAVOS)

        return {
            "ok": True,
            "accion_id": movimiento.accion_id,
            "periodo_id": movimiento.periodo_id,
            "amortizacion_restaurada": restaurada,
            "prestamos_restaurados": prestamos_restaurados,
            "saldo_total_restaurado": saldo_restaurado,

            # La multa que fue pagada por la amortización anterior
            # vuelve a estar pendiente al editar.
            "saldo_multa_restaurado": multa_pagada_anterior,

            "multa_separada": multa_pagada_anterior,
            "solo_multa": False
        }

    #
    # Obtener Periodo anterior a un periodo dado
    #
    @staticmethod
    def obtener_periodo_anterior(db, periodo_id):

        periodo_actual = (
            db.query(Periodo)
            .filter(Periodo.id == periodo_id)
            .first()
        )

        if not periodo_actual:
            raise Exception("Período no encontrado.")

        return (
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

    # -----------------------------------------------------
    # RECONSTRUIR SALDOS DE PRÉSTAMOS DE UNA ACCIÓN - PERÍODO
    # -----------------------------------------------------
    @staticmethod
    def reconstruir_saldos_accion_periodo(
        db,
        accion_id,
        periodo_id,
        amortizacion,
        multa_periodo_anterior=Decimal("0.00"),
        saldo_multa_restaurado=None
    ):
        """
        Reconstruye los saldos de capital de los préstamos
        anteriores al período actual.

        REGLAS:

        1. Prestamo.saldo_actual = SOLO CAPITAL.
        2. La multa es una deuda separada.
        3. La amortización calculada por la cuota reduce CAPITAL.
        4. La multa NO se resta del capital.
        5. Los préstamos del período actual no se modifican.
        6. La amortización se aplica FIFO.
        7. La función es idempotente: recibe el saldo ya restaurado
        y solamente aplica la nueva amortización.
        """

        CENTAVOS = Decimal("0.01")

        amortizacion = Decimal(
            str(
                amortizacion or 0
            )
        ).quantize(CENTAVOS)

        if amortizacion < Decimal("0.00"):
            amortizacion = Decimal("0.00")

        multa_periodo_anterior = Decimal(
            str(
                multa_periodo_anterior or 0
            )
        ).quantize(CENTAVOS)

        if multa_periodo_anterior < Decimal("0.00"):
            multa_periodo_anterior = Decimal("0.00")

        # =====================================================
        # 1. OBTENER PERÍODO
        # =====================================================

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
                "No se pueden reconstruir saldos "
                "de un período cerrado."
            )

        # =====================================================
        # 2. OBTENER PRÉSTAMOS ANTERIORES
        # =====================================================

        prestamos = (
            db.query(Prestamo)
            .join(
                Periodo,
                Prestamo.periodo_id == Periodo.id
            )
            .filter(
                Prestamo.accion_id == accion_id,
                or_(
                    Periodo.anio < periodo.anio,
                    and_(
                        Periodo.anio == periodo.anio,
                        Periodo.mes < periodo.mes
                    )
                )
            )
            .order_by(
                Prestamo.fecha_prestamo.asc(),
                Prestamo.id.asc()
            )
            .all()
        )

        # =====================================================
        # 3. CASO SIN PRÉSTAMOS
        # =====================================================

        if not prestamos:

            deuda_multa = Decimal("0.00")

            if saldo_multa_restaurado is not None:

                deuda_multa = Decimal(
                    str(
                        saldo_multa_restaurado or 0
                    )
                ).quantize(CENTAVOS)

            else:

                deuda_multa = multa_periodo_anterior

            if deuda_multa < Decimal("0.00"):
                deuda_multa = Decimal("0.00")

            print("\n==============================================")
            print("RECONSTRUIR SALDOS - SOLO MULTA")
            print("==============================================")
            print(f"Acción             : {accion_id}")
            print(f"Período            : {periodo_id}")
            print(f"Multa pendiente    : {deuda_multa}")
            print(f"Amortización       : {amortizacion}")
            print("Capital             : 0.00")
            print("==============================================\n")

            return {
                "accion_id": accion_id,
                "periodo_id": periodo_id,
                "amortizacion_aplicada": Decimal("0.00"),
                "amortizacion_pendiente": amortizacion,
                "amortizacion_capital": Decimal("0.00"),
                "multa_aplicada": Decimal("0.00"),
                "saldo_total_prestamos": Decimal("0.00"),
                "saldo_deuda_multa": deuda_multa,
                "saldo_deuda_total": deuda_multa,
                "prestamos_actualizados": 0,
                "prestamos_cancelados": 0
            }

        # =====================================================
        # 4. APLICAR AMORTIZACIÓN
        # =====================================================
        #
        # La cuota primero cancela la multa anterior.
        # El excedente reduce capital.
        #
        # Prestamo.saldo_actual continúa siendo SOLO CAPITAL.
        # La multa permanece separada.
        # =====================================================

        pendiente = amortizacion

        amortizacion_aplicada = Decimal("0.00")
        multa_aplicada = Decimal("0.00")
        amortizacion_capital = Decimal("0.00")

        prestamos_actualizados = 0
        prestamos_cancelados = 0


        # =====================================================
        # 4.1 PAGAR MULTA ANTERIOR
        # =====================================================

        if multa_periodo_anterior > Decimal("0.00"):

            pago_multa = min(
                pendiente,
                multa_periodo_anterior
            ).quantize(CENTAVOS)

            multa_periodo_anterior = (
                multa_periodo_anterior
                - pago_multa
            ).quantize(CENTAVOS)

            pendiente = (
                pendiente
                - pago_multa
            ).quantize(CENTAVOS)

            multa_aplicada = pago_multa

            amortizacion_aplicada += pago_multa

            print(
                f"  AMORTIZACIÓN MULTA -> "
                f"-{pago_multa} "
                f"| multa pendiente={multa_periodo_anterior}"
            )


        # =====================================================
        # 4.2 APLICAR RESTO AL CAPITAL
        # =====================================================

        for prestamo in prestamos:

            if pendiente <= Decimal("0.00"):
                break

            saldo_actual = Decimal(
                str(
                    prestamo.saldo_actual or 0
                )
            ).quantize(CENTAVOS)

            if saldo_actual <= Decimal("0.00"):

                prestamo.saldo_actual = Decimal("0.00")
                prestamo.estado = "CANCELADO"

                continue

            aplicar = min(
                saldo_actual,
                pendiente
            ).quantize(CENTAVOS)

            nuevo_saldo = (
                saldo_actual
                - aplicar
            ).quantize(CENTAVOS)

            if nuevo_saldo < Decimal("0.00"):
                nuevo_saldo = Decimal("0.00")

            prestamo.saldo_actual = nuevo_saldo

            if nuevo_saldo == Decimal("0.00"):

                prestamo.estado = "CANCELADO"
                prestamos_cancelados += 1

            else:

                prestamo.estado = "ACTIVO"

            pendiente = (
                pendiente
                - aplicar
            ).quantize(CENTAVOS)

            amortizacion_capital += aplicar
            amortizacion_aplicada += aplicar

            prestamos_actualizados += 1

            print(
                f"  AMORTIZACIÓN CAPITAL -> "
                f"Préstamo {prestamo.id} "
                f"| -{aplicar} "
                f"| nuevo capital={prestamo.saldo_actual}"
            )


        # =====================================================
        # 4.3 VALIDAR AMORTIZACIÓN
        # =====================================================

        pendiente = max(
            pendiente,
            Decimal("0.00")
        ).quantize(CENTAVOS)

        if pendiente > Decimal("0.01"):
            raise Exception(
                "No fue posible aplicar toda la amortización "
                "a la deuda de la acción. "
                f"Pendiente: S/ {pendiente}"
            )

        # =====================================================
        # 4.4 SALDO DEUDA
        # =====================================================

        saldo_total_prestamos = (
            db.query(
                func.coalesce(
                    func.sum(
                        Prestamo.saldo_actual
                    ),
                    0
                )
            )
            .filter(
                Prestamo.accion_id == accion_id,
                Prestamo.periodo_id < periodo_id,
                Prestamo.saldo_actual > 0
            )
            .scalar()
        )

        saldo_total_prestamos = Decimal(
            str(
                saldo_total_prestamos or 0
            )
        ).quantize(CENTAVOS)

        saldo_deuda_multa = multa_periodo_anterior.quantize(
            CENTAVOS
        )

        saldo_deuda_total = (
            saldo_total_prestamos
            + saldo_deuda_multa
        ).quantize(CENTAVOS)

        db.flush()

        return {
            "accion_id": accion_id,
            "periodo_id": periodo_id,
            "amortizacion_aplicada": amortizacion_aplicada,
            "amortizacion_pendiente": pendiente,
            "amortizacion_capital": amortizacion_capital,
            "multa_aplicada": multa_aplicada,
            "saldo_total_prestamos": saldo_total_prestamos,
            "saldo_deuda_multa": saldo_deuda_multa,
            "saldo_deuda_total": saldo_deuda_total,
            "prestamos_actualizados": prestamos_actualizados,
            "prestamos_cancelados": prestamos_cancelados
}
    # -----------------------------------------------------
    # CUOTA MÍNIMA 
    # -----------------------------------------------------
    @staticmethod
    def calcular_cuota_minima(monto_total):

        monto_total = Decimal(str(monto_total))

        if monto_total <= 3000:return Decimal("417")
        elif monto_total <= 7500:return Decimal("504")
        elif monto_total <= 12500:return Decimal("566")
        elif monto_total <= 15000:return Decimal("590")
        elif monto_total <= 17500:return Decimal("611")
        elif monto_total <= 20000:return Decimal("677")
        elif monto_total <= 22500:return Decimal("743")
        elif monto_total <= 25000:return Decimal("809")
        elif monto_total <= 27500:return Decimal("875")
        elif monto_total <= 30000:return Decimal("941")

        return Decimal("941")

    # -----------------------------------------------------
    # CALCULAR SCRORE PARA ASIGNACION DE PRIORIDAD DE SOLICITUDES DE PRESTAMOS 
    # -- duplicado por que esta en utilidades_services.py tambien
    # -----------------------------------------------------
    @staticmethod
    def calcular_score(db, socio, accion, monto):

        # ================================================
        # Criterio	                                Máximo
        # Antigüedad del socio	                    20
        # Número de acciones	                    20
        # Historial de pago (multas)	            20
        # Préstamos cancelados	                    20
        # Monto solicitado respecto al límite	    20
        # Total	                                   100
        # ================================================

        score = 0

        # =====================================
        # 1. ANTIGÜEDAD (20 puntos)
        # =====================================

        hoy = date.today()

        meses = (
            (hoy.year - socio.fecha_ingreso.year) * 12
            +
            hoy.month
            -
            socio.fecha_ingreso.month
        )

        if meses >= 60:
            score += 20
        elif meses >= 36:
            score += 15
        elif meses >= 24:
            score += 10
        elif meses >= 12:
            score += 5

        # =====================================
        # 2. NÚMERO DE ACCIONES (20 puntos)
        # =====================================

        acciones = (
            db.query(Accion)
            .filter(
                Accion.socio_id == socio.id,
                Accion.estado == "ACTIVO"
            )
            .count()
        )

        score += min(
            acciones * 2,
            20
        )

        # =====================================
        # 3. HISTORIAL DE MULTAS (20 puntos)
        # =====================================

        multas = (
            db.query(
                func.coalesce(
                    func.sum(Movimiento.multa),
                    0
                )
            )
            .filter(
                Movimiento.socio_id == socio.id
            )
            .scalar()
        )

        multas = float(multas)

        if multas == 0:
            score += 20
        elif multas <= 20:
            score += 15
        elif multas <= 50:
            score += 10
        elif multas <= 100:

            score += 5

        # =====================================
        # 4. PRÉSTAMOS CANCELADOS (20 puntos)
        # =====================================
        cancelados = (
            db.query(Prestamo)
            .filter(
                Prestamo.socio_id == socio.id,
                Prestamo.estado == "CANCELADO"
            )
            .count()
        )
        score += min(
            cancelados * 5,
            20
        )

        # =====================================
        # 5. MONTO SOLICITADO (20 puntos)
        # Menor monto = menor riesgo
        # =====================================

        monto = float(monto)

        if monto <= 3000:
            score += 20
        elif monto <= 6000:
            score += 15
        elif monto <= 10000:
            score += 10
        elif monto <= 15000:
            score += 5
        # =====================================

        return round(score, 2)