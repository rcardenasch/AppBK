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
        Revierte la amortización que fue aplicada por un movimiento
        editado.

        REGLAS IMPORTANTES:

        1. Prestamo.saldo_actual representa SOLO CAPITAL.
        2. La multa NO forma parte de Prestamo.saldo_actual.
        3. La amortización se restaura FIFO.
        4. Los préstamos del período actual no participan.
        5. Si la lógica anterior había incorporado la multa anterior
        dentro de Prestamo.saldo_actual, se descuenta UNA SOLA VEZ
        antes de restaurar la amortización.
        """

        amortizacion = Decimal(
            str(movimiento.amortizacion or 0)
        ).quantize(Decimal("0.01"))

        if amortizacion <= Decimal("0.00"):
            return {
                "ok": True,
                "amortizacion_restaurada": Decimal("0.00"),
                "prestamos_restaurados": 0,
                "saldo_total_restaurado": Decimal("0.00"),
                "saldo_multa_restaurado": Decimal("0.00")
            }

        # =====================================================
        # VALIDAR PERÍODO
        # =====================================================

        periodo = (
            db.query(Periodo)
            .filter(
                Periodo.id == movimiento.periodo_id
            )
            .first()
        )

        if not periodo:
            raise Exception("Período no encontrado.")

        if periodo.cerrado:
            raise Exception(
                "No se puede restaurar un movimiento "
                "de un período cerrado."
            )

        # =====================================================
        # MULTA DEL PERÍODO ANTERIOR
        # =====================================================

        multa_anterior = (
            MovimientoService.obtener_multa_periodo_anterior_accion(
                db=db,
                accion_id=movimiento.accion_id,
                periodo_id=movimiento.periodo_id
            )
        )

        multa_anterior = Decimal(
            str(multa_anterior or 0)
        ).quantize(Decimal("0.01"))

        # =====================================================
        # OBTENER PRÉSTAMOS ANTERIORES
        #
        # IMPORTANTE:
        # comparar por AÑO + MES, no por ID.
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
        # CASO: NO EXISTEN PRÉSTAMOS
        # =====================================================

        if not prestamos:

            if multa_anterior <= Decimal("0.00"):
                raise Exception(
                    f"La acción {movimiento.accion_id} no tiene "
                    "préstamos anteriores ni deuda por multa."
                )

            deuda_multa_restaurada = min(
                amortizacion,
                multa_anterior
            ).quantize(Decimal("0.01"))

            db.flush()

            print("\n==============================================")
            print("RESTAURAR AMORTIZACIÓN - SOLO MULTA")
            print("==============================================")
            print(f"Movimiento             : {movimiento.id}")
            print(f"Acción                 : {movimiento.accion_id}")
            print(f"Período                : {movimiento.periodo_id}")
            print(f"Multa anterior         : {multa_anterior}")
            print(f"Amortización anterior  : {amortizacion}")
            print(f"Multa restaurada       : {deuda_multa_restaurada}")
            print("Préstamos restaurados  : 0")
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
        # DEBUG
        # =====================================================

        print("\n==============================================")
        print("RESTAURAR AMORTIZACIÓN")
        print("==============================================")
        print(f"Movimiento             : {movimiento.id}")
        print(f"Acción                 : {movimiento.accion_id}")
        print(f"Período                : {movimiento.periodo_id}")
        print(f"Amortización           : {amortizacion}")
        print(f"Multa anterior         : {multa_anterior}")

        for prestamo in prestamos:
            print(
                f"  ANTES -> Préstamo {prestamo.id} "
                f"| período={prestamo.periodo_id} "
                f"| saldo={prestamo.saldo_actual}"
            )

        # =====================================================
        # IMPORTANTE:
        #
        # La versión anterior de reconstruir_saldos_accion_periodo()
        # hacía esto:
        #
        #     saldo_actual += multa_anterior
        #
        # Eso contaminó Prestamo.saldo_actual.
        #
        # Por ejemplo:
        #
        # CAPITAL REAL       = 17159.70
        # MULTA               =    50.00
        # SALDO CONTAMINADO   = 17209.70
        #
        # Antes de restaurar la amortización debemos volver a separar
        # la multa del capital.
        #
        # La multa se descuenta UNA SOLA VEZ del primer préstamo.
        # =====================================================

        multa_a_quitar = multa_anterior

        if multa_a_quitar > Decimal("0.00"):

            for prestamo in prestamos:

                if multa_a_quitar <= Decimal("0.00"):
                    break

                saldo_actual = Decimal(
                    str(prestamo.saldo_actual or 0)
                ).quantize(Decimal("0.01"))

                if saldo_actual <= Decimal("0.00"):
                    continue

                quitar = min(
                    saldo_actual,
                    multa_a_quitar
                ).quantize(Decimal("0.01"))

                prestamo.saldo_actual = (
                    saldo_actual - quitar
                ).quantize(Decimal("0.01"))

                multa_a_quitar -= quitar

                multa_a_quitar = multa_a_quitar.quantize(
                    Decimal("0.01")
                )

                if prestamo.saldo_actual > Decimal("0.00"):
                    prestamo.estado = "ACTIVO"
                else:
                    prestamo.estado = "CANCELADO"

                print(
                    f"  MULTA SEPARADA -> Préstamo {prestamo.id} "
                    f"| -{quitar} "
                    f"| nuevo capital={prestamo.saldo_actual}"
                )

        # =====================================================
        # RESTAURAR AMORTIZACIÓN
        #
        # FIFO: préstamo más antiguo primero.
        # =====================================================

        pendiente = amortizacion
        restaurada = Decimal("0.00")
        prestamos_restaurados = 0

        for prestamo in prestamos:

            if pendiente <= Decimal("0.00"):
                break

            saldo_actual = Decimal(
                str(prestamo.saldo_actual or 0)
            ).quantize(Decimal("0.01"))

            restaurar = pendiente

            prestamo.saldo_actual = (
                saldo_actual + restaurar
            ).quantize(Decimal("0.01"))

            prestamo.estado = "ACTIVO"

            pendiente -= restaurar
            restaurada += restaurar
            prestamos_restaurados += 1

            pendiente = pendiente.quantize(Decimal("0.01"))
            restaurada = restaurada.quantize(Decimal("0.01"))

            print(
                f"  AMORTIZACIÓN RESTAURADA -> "
                f"Préstamo {prestamo.id} "
                f"| +{restaurar} "
                f"| nuevo capital={prestamo.saldo_actual}"
            )

        pendiente = pendiente.quantize(Decimal("0.01"))
        restaurada = restaurada.quantize(Decimal("0.01"))

        if pendiente > Decimal("0.00"):
            raise Exception(
                "No fue posible restaurar completamente "
                "la amortización del movimiento. "
                f"Pendiente: S/ {pendiente}"
            )

        # =====================================================
        # FLUSH
        # =====================================================

        db.flush()

        # =====================================================
        # SALDO DE CAPITAL RESTAURADO
        # =====================================================

        saldo_total = (
            db.query(
                func.coalesce(
                    func.sum(Prestamo.saldo_actual),
                    0
                )
            )
            .filter(
                Prestamo.accion_id == movimiento.accion_id,
                Prestamo.periodo_id < movimiento.periodo_id
            )
            .scalar()
        )

        saldo_total = Decimal(
            str(saldo_total or 0)
        ).quantize(Decimal("0.01"))

        print("----------------------------------------------")
        print(f"Amortización restaurada : {restaurada}")
        print(f"Capital restaurado      : {saldo_total}")

        for prestamo in prestamos:
            print(
                f"  DESPUÉS -> Préstamo {prestamo.id} "
                f"| capital={prestamo.saldo_actual}"
            )

        print("==============================================\n")

        return {
            "ok": True,
            "accion_id": movimiento.accion_id,
            "periodo_id": movimiento.periodo_id,
            "amortizacion_restaurada": restaurada,
            "prestamos_restaurados": prestamos_restaurados,
            "saldo_total_restaurado": saldo_total,
            "saldo_multa_restaurado": Decimal("0.00"),
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
        2. Movimiento.saldo_prestamo = CAPITAL + DEUDA POR MULTA.
        3. La multa NO se suma a Prestamo.saldo_actual.
        4. La amortización se aplica primero a la deuda por multa
        cuando corresponda y luego al capital.
        5. Los préstamos del período actual no participan.
        6. Los préstamos se procesan FIFO.
        7. saldo_interes no participa.
        8. La multa nunca debe contaminar el saldo de capital.
        """

        amortizacion = Decimal(
            str(amortizacion or 0)
        ).quantize(Decimal("0.01"))

        multa_periodo_anterior = Decimal(
            str(multa_periodo_anterior or 0)
        ).quantize(Decimal("0.01"))

        periodo = (
            db.query(Periodo)
            .filter(
                Periodo.id == periodo_id
            )
            .first()
        )

        if not periodo:
            raise Exception("Período no encontrado.")

        if periodo.cerrado:
            raise Exception(
                "No se pueden reconstruir saldos "
                "de un período cerrado."
            )

        # ==========================================================
        # 1. OBTENER PRÉSTAMOS ANTERIORES
        #
        # Comparación cronológica real: AÑO + MES.
        # ==========================================================

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

        # ==========================================================
        # 2. MULTA
        #
        # La multa es una deuda independiente del capital.
        # ==========================================================

        if saldo_multa_restaurado is not None:

            deuda_multa = Decimal(
                str(
                    saldo_multa_restaurado or 0
                )
            ).quantize(Decimal("0.01"))

        else:

            deuda_multa = multa_periodo_anterior

        deuda_multa = deuda_multa.quantize(
            Decimal("0.01")
        )

        # ==========================================================
        # 3. CASO SIN PRÉSTAMOS
        # ==========================================================

        if not prestamos:

            amortizacion_a_multa = min(
                amortizacion,
                deuda_multa
            ).quantize(Decimal("0.01"))

            deuda_multa_restante = (
                deuda_multa -
                amortizacion_a_multa
            ).quantize(Decimal("0.01"))

            pendiente = (
                amortizacion -
                amortizacion_a_multa
            ).quantize(Decimal("0.01"))

            print("\n==============================================")
            print("RECONSTRUIR SALDOS - SOLO MULTA")
            print("==============================================")
            print(f"Acción                  : {accion_id}")
            print(f"Período                 : {periodo_id}")
            print(f"Deuda multa inicial     : {deuda_multa}")
            print(f"Amortización            : {amortizacion}")
            print(
                f"Amortización a multa    : "
                f"{amortizacion_a_multa}"
            )
            print(
                f"Deuda multa restante    : "
                f"{deuda_multa_restante}"
            )
            print(f"Amortización pendiente  : {pendiente}")
            print("Capital préstamos       : 0.00")
            print("==============================================\n")

            return {
                "accion_id": accion_id,
                "periodo_id": periodo_id,
                "amortizacion_aplicada": amortizacion_a_multa,
                "amortizacion_pendiente": pendiente,
                "multa_aplicada": amortizacion_a_multa,
                "saldo_total_prestamos": Decimal("0.00"),
                "saldo_deuda_multa": deuda_multa_restante,
                "saldo_deuda_total": deuda_multa_restante,
                "prestamos_actualizados": 0,
                "prestamos_cancelados": 0
            }

        # ==========================================================
        # 4. ASEGURAR QUE LOS SALDOS SEAN CAPITAL
        #
        # NO agregar multa.
        # ==========================================================

        prestamos_con_saldo = []

        for prestamo in prestamos:

            saldo = Decimal(
                str(
                    prestamo.saldo_actual or 0
                )
            ).quantize(Decimal("0.01"))

            if saldo > Decimal("0.00"):

                prestamos_con_saldo.append(
                    prestamo
                )

            else:

                prestamo.saldo_actual = Decimal("0.00")
                prestamo.estado = "CANCELADO"

        # ==========================================================
        # 5. APLICAR AMORTIZACIÓN
        #
        # Primero se paga la multa.
        # El resto va al CAPITAL.
        # ==========================================================

        pendiente = amortizacion
        amortizacion_aplicada = Decimal("0.00")
        multa_aplicada = Decimal("0.00")

        # ==========================================================
        # 5.1 PAGAR MULTA
        # ==========================================================

        if deuda_multa > Decimal("0.00"):

            pago_multa = min(
                pendiente,
                deuda_multa
            ).quantize(Decimal("0.01"))

            deuda_multa = (
                deuda_multa -
                pago_multa
            ).quantize(Decimal("0.01"))

            pendiente = (
                pendiente -
                pago_multa
            ).quantize(Decimal("0.01"))

            multa_aplicada = pago_multa

        # ==========================================================
        # 5.2 APLICAR RESTO AL CAPITAL
        # FIFO
        # ==========================================================

        amortizacion_capital = Decimal("0.00")

        prestamos_actualizados = 0
        prestamos_cancelados = 0

        for prestamo in prestamos_con_saldo:

            if pendiente <= Decimal("0.00"):
                break

            saldo_actual = Decimal(
                str(
                    prestamo.saldo_actual or 0
                )
            ).quantize(Decimal("0.01"))

            if saldo_actual <= Decimal("0.00"):
                prestamo.saldo_actual = Decimal("0.00")
                prestamo.estado = "CANCELADO"
                continue

            amortizacion_prestamo = min(
                saldo_actual,
                pendiente
            ).quantize(Decimal("0.01"))

            nuevo_saldo = (
                saldo_actual -
                amortizacion_prestamo
            ).quantize(Decimal("0.01"))

            if nuevo_saldo < Decimal("0.00"):
                nuevo_saldo = Decimal("0.00")

            prestamo.saldo_actual = nuevo_saldo

            if nuevo_saldo == Decimal("0.00"):

                prestamo.estado = "CANCELADO"
                prestamos_cancelados += 1

            else:

                prestamo.estado = "ACTIVO"

            pendiente = (
                pendiente -
                amortizacion_prestamo
            ).quantize(Decimal("0.01"))

            amortizacion_capital += (
                amortizacion_prestamo
            )

            amortizacion_capital = (
                amortizacion_capital
            ).quantize(Decimal("0.01"))

            amortizacion_aplicada += (
                amortizacion_prestamo
            )

            amortizacion_aplicada = (
                amortizacion_aplicada
            ).quantize(Decimal("0.01"))

            prestamos_actualizados += 1

            print(
                f"  AMORTIZACIÓN -> Préstamo {prestamo.id} "
                f"| -{amortizacion_prestamo} "
                f"| nuevo capital={prestamo.saldo_actual}"
            )

        # ==========================================================
        # 6. VALIDAR PENDIENTE
        # ==========================================================

        pendiente = max(
            pendiente,
            Decimal("0.00")
        ).quantize(Decimal("0.01"))

        if pendiente > Decimal("0.01"):
            raise Exception(
                "No fue posible aplicar toda la amortización "
                "de la acción. "
                f"Pendiente: S/ {pendiente}"
            )

        # ==========================================================
        # 7. FLUSH
        # ==========================================================

        db.flush()

        # ==========================================================
        # 8. SALDO REAL DE CAPITAL
        #
        # IMPORTANTE:
        # aquí SOLO sumamos Prestamo.saldo_actual.
        # NO sumamos multa.
        # ==========================================================

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
                Prestamo.periodo_id < periodo_id
            )
            .scalar()
        )

        saldo_total_prestamos = Decimal(
            str(
                saldo_total_prestamos or 0
            )
        ).quantize(Decimal("0.01"))

        # ==========================================================
        # 9. DEUDA TOTAL
        #
        # CAPITAL + MULTA PENDIENTE
        # ==========================================================

        saldo_deuda_total = (
            saldo_total_prestamos +
            deuda_multa
        ).quantize(Decimal("0.01"))

        # ==========================================================
        # DEBUG
        # ==========================================================

        print("\n==============================================")
        print("RECONSTRUIR SALDOS ACCIÓN")
        print("==============================================")
        print(f"Acción                  : {accion_id}")
        print(f"Período                 : {periodo_id}")
        print(f"Multa inicial           : {multa_periodo_anterior}")
        print(f"Multa aplicada          : {multa_aplicada}")
        print(f"Multa pendiente         : {deuda_multa}")
        print(f"Amortización total      : {amortizacion}")
        print(f"Amortización capital    : {amortizacion_capital}")
        print(f"Capital final           : {saldo_total_prestamos}")
        print(f"Deuda total final       : {saldo_deuda_total}")

        for prestamo in prestamos:

            print(
                f"  Préstamo {prestamo.id} "
                f"| período={prestamo.periodo_id} "
                f"| capital={prestamo.saldo_actual} "
                f"| estado={prestamo.estado}"
            )

        print("==============================================\n")

        return {
            "accion_id": accion_id,
            "periodo_id": periodo_id,

            # Amortización total que efectivamente se pudo aplicar
            "amortizacion_aplicada": amortizacion_aplicada,

            # Lo que no pudo aplicarse
            "amortizacion_pendiente": pendiente,

            # Parte aplicada a multa
            "multa_aplicada": multa_aplicada,

            # CAPITAL solamente
            "saldo_total_prestamos": saldo_total_prestamos,

            # MULTA pendiente
            "saldo_deuda_multa": deuda_multa,

            # CAPITAL + MULTA
            "saldo_deuda_total": saldo_deuda_total,

            "prestamos_actualizados": prestamos_actualizados,
            "prestamos_cancelados": prestamos_cancelados
        }

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