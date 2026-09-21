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
        Revierte la amortización que YA fue aplicada por este movimiento.

        IMPORTANTE:
        - NO utiliza Movimiento.prestamo_id para decidir el préstamo.
        - La restauración se hace sobre los préstamos de la acción
        en orden FIFO: más antiguo -> más nuevo.
        - No utiliza saldo_interes.
        - Los préstamos del período actual no participan.
        """

        from decimal import Decimal

        amortizacion = Decimal(
            str(movimiento.amortizacion or 0)
        ).quantize(Decimal("0.01"))

        if amortizacion <= Decimal("0.00"):
            return {
                "ok": True,
                "amortizacion_restaurada": Decimal("0.00"),
                "prestamos_restaurados": 0
            }

        # =====================================================
        # VALIDAR PERÍODO
        # =====================================================

        periodo = (
            db.query(Periodo)
            .filter(Periodo.id == movimiento.periodo_id)
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
        # OBTENER PRÉSTAMOS ANTERIORES AL PERÍODO
        # =====================================================

        prestamos = (
            db.query(Prestamo)
            .filter(
                Prestamo.accion_id == movimiento.accion_id,
                Prestamo.periodo_id < movimiento.periodo_id
            )
            .order_by(
                Prestamo.fecha_prestamo.asc(),
                Prestamo.id.asc()
            )
            .all()
        )

        if not prestamos:

            # ======================================================
            # CASO ESPECIAL:
            # NO HAY PRÉSTAMOS, PERO PUEDE EXISTIR
            # DEUDA POR MULTA DEL PERÍODO ANTERIOR.
            # ======================================================

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

            # ------------------------------------------------------
            # Si no hay multa, realmente no existe deuda que
            # restaurar.
            # ------------------------------------------------------

            if multa_anterior <= Decimal("0.00"):

                raise Exception(
                    f"La acción {movimiento.accion_id} no tiene "
                    f"préstamos anteriores ni deuda por multa."
                )

            # ------------------------------------------------------
            # La amortización anterior se interpreta como pago
            # realizado contra la deuda por multa.
            # ------------------------------------------------------

            deuda_multa_restaurada = min(
                amortizacion,
                multa_anterior
            ).quantize(Decimal("0.01"))

            db.flush()

            print("\n==============================================")
            print("RESTAURAR AMORTIZACIÓN - SOLO MULTA")
            print("==============================================")
            print(f"Movimiento              : {movimiento.id}")
            print(f"Acción                  : {movimiento.accion_id}")
            print(f"Período                 : {movimiento.periodo_id}")
            print(f"Multa anterior          : {multa_anterior}")
            print(f"Amortización anterior   : {amortizacion}")
            print(f"Deuda multa restaurada  : {deuda_multa_restaurada}")
            print("Préstamos restaurados   : 0")
            print("==============================================\n")

            return {
                "ok": True,
                "accion_id": movimiento.accion_id,
                "periodo_id": movimiento.periodo_id,
                "amortizacion_restaurada": deuda_multa_restaurada,
                "prestamos_restaurados": 0,
                "saldo_total_restaurado": Decimal("0.00"),
                "saldo_multa_restaurado": deuda_multa_restaurada,
                "solo_multa": True
            }

        # =====================================================
        # DEBUG: SALDO ANTES DE RESTAURAR
        # =====================================================

        print("\n==============================================")
        print("RESTAURAR AMORTIZACIÓN")
        print("==============================================")
        print(f"Movimiento              : {movimiento.id}")
        print(f"Acción                  : {movimiento.accion_id}")
        print(f"Período                 : {movimiento.periodo_id}")
        print(f"Amortización a restaurar: {amortizacion}")

        for prestamo in prestamos:
            print(
                f"  ANTES -> Préstamo {prestamo.id} "
                f"| período={prestamo.periodo_id} "
                f"| saldo={prestamo.saldo_actual}"
            )

        # =====================================================
        # RESTAURAR
        #
        # IMPORTANTE:
        # La amortización histórica fue aplicada desde el más
        # antiguo hacia el más nuevo.
        #
        # Por eso la reversión sigue el mismo orden.
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

            # -------------------------------------------------
            # Si el préstamo tiene saldo actual, la restauración
            # puede devolverse directamente.
            #
            # En caso de que haya quedado en cero, también se
            # restaura porque pudo haber sido cancelado por esta
            # amortización.
            # -------------------------------------------------

            restaurar = pendiente

            prestamo.saldo_actual = (
                saldo_actual + restaurar
            ).quantize(Decimal("0.01"))

            prestamo.estado = "ACTIVO"

            pendiente -= restaurar
            restaurada += restaurar
            prestamos_restaurados += 1

            print(
                f"  RESTAURADO -> Préstamo {prestamo.id} "
                f"| +{restaurar} "
                f"| nuevo saldo={prestamo.saldo_actual}"
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
        # MUY IMPORTANTE
        #
        # Forzar que SQLAlchemy escriba los cambios antes de
        # cualquier SUM() posterior.
        # =====================================================

        db.flush()

        # =====================================================
        # VALIDACIÓN REAL DESPUÉS DE RESTAURAR
        # =====================================================

        from sqlalchemy import func

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
        print(f"Saldo préstamos restaur.: {saldo_total}")

        for prestamo in prestamos:
            print(
                f"  DESPUÉS -> Préstamo {prestamo.id} "
                f"| saldo={prestamo.saldo_actual}"
            )

        print("==============================================\n")

        return {
            "ok": True,
            "accion_id": movimiento.accion_id,
            "periodo_id": movimiento.periodo_id,
            "amortizacion_restaurada": restaurada,
            "prestamos_restaurados": prestamos_restaurados,
            "saldo_total_restaurado": saldo_total
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
    # RECONSTRUIR SALDOS DE PRÉSTAMOS DE UNA ACCIÓN - Periodo
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
        Reconstruye el saldo de los préstamos incorporados
        a una acción hasta el período anterior.

        REGLAS:

        1. Movimiento.saldo_prestamo y la suma de Prestamo.saldo_actual
        de los préstamos incorporados deben coincidir.
        2. Si existen varios préstamos, se trabaja con el saldo
        consolidado de todos los préstamos incorporados.
        3. Un préstamo registrado en el período actual NO entra
        en el saldo del movimiento actual.
        Se incorpora recién en el período siguiente.
        4. La multa del período anterior se incorpora UNA SOLA VEZ
        al saldo de la acción.
        5. La amortización se aplica a los préstamos más antiguos
        primero.
        6. saldo_interes nunca participa.
        7. El período cerrado no puede modificarse.
        """

        from decimal import Decimal
        from sqlalchemy import func

        amortizacion = Decimal(
            str(amortizacion or 0)
        ).quantize(Decimal("0.01"))

        multa_periodo_anterior = Decimal(
            str(multa_periodo_anterior or 0)
        ).quantize(Decimal("0.01"))

        periodo = (
            db.query(Periodo)
            .filter(Periodo.id == periodo_id)
            .first()
        )

        if not periodo:
            raise Exception("Período no encontrado.")

        if periodo.cerrado:
            raise Exception(
                "No se pueden reconstruir saldos de un período cerrado."
            )

        # ==========================================================
        # 1. SOLO PRÉSTAMOS INCORPORADOS ANTES DEL PERÍODO ACTUAL
        # ==========================================================

        prestamos = (
            db.query(Prestamo)
            .filter(
                Prestamo.accion_id == accion_id,
                Prestamo.periodo_id < periodo_id
            )
            .order_by(
                Prestamo.fecha_prestamo.asc(),
                Prestamo.id.asc()
            )
            .all()
        )

     # =========================================================
        # CASO ESPECIAL DE EDICIÓN:
        # MULTA SOLA SIN PRÉSTAMO
        #
        # La multa ya fue restaurada antes de recalcular
        # el movimiento, por lo que NO debe buscarse nuevamente
        # en multa_periodo_anterior.
        # =========================================================

        if (
            not prestamos
            and saldo_multa_restaurado is not None
        ):

            deuda_multa = Decimal(
                str(
                    saldo_multa_restaurado or 0
                )
            ).quantize(
                Decimal("0.01")
            )

            amortizacion = Decimal(
                str(
                    amortizacion or 0
                )
            ).quantize(
                Decimal("0.01")
            )

            amortizacion_aplicada = min(
                amortizacion,
                deuda_multa
            ).quantize(
                Decimal("0.01")
            )

            deuda_multa_restante = (
                deuda_multa -
                amortizacion_aplicada
            ).quantize(
                Decimal("0.01")
            )

            if deuda_multa_restante < Decimal("0.00"):
                deuda_multa_restante = Decimal("0.00")

            print("\n==============================================")
            print("RECONSTRUIR SALDOS - EDICIÓN MULTA SOLA")
            print("==============================================")
            print(f"Acción                  : {accion_id}")
            print(f"Período                 : {periodo_id}")
            print(f"Saldo multa restaurado  : {deuda_multa}")
            print(f"Amortización solicitada : {amortizacion}")
            print(f"Amortización aplicada   : "f"{amortizacion_aplicada}")
            print(f"Deuda multa restante    : "f"{deuda_multa_restante}")
            print("Préstamos anteriores    : 0")
            print("==============================================\n")

            return {
                "accion_id": accion_id,
                "periodo_id": periodo_id,
                "amortizacion_aplicada": amortizacion_aplicada,
                "amortizacion_pendiente": (amortizacion - amortizacion_aplicada).quantize(Decimal("0.01")),
                "multa_aplicada": Decimal("0.00"),
                "saldo_total_prestamos": Decimal("0.00"),
                "saldo_deuda_multa": deuda_multa_restante,
                "prestamos_actualizados": 0,
                "prestamos_cancelados": 0
            }

        if not prestamos:

            deuda_multa = multa_periodo_anterior

        # ==========================================================
        # 3. SALDOS ACTUALES DE LOS PRÉSTAMOS ANTERIORES
        # ==========================================================

        prestamos_con_saldo = []

        for prestamo in prestamos:

            saldo = Decimal(
                str(prestamo.saldo_actual or 0)
            ).quantize(Decimal("0.01"))

            if saldo > Decimal("0.00"):
                prestamos_con_saldo.append(prestamo)
            else:
                prestamo.saldo_actual = Decimal("0.00")

        # ==========================================================
        # 4. INCORPORAR MULTA DEL PERÍODO ANTERIOR
        # ==========================================================

        multa_aplicada = Decimal("0.00")

        if multa_periodo_anterior > Decimal("0.00"):

            # ======================================================
            # CASO: MULTA SOLA SIN PRÉSTAMOS
            #
            # La multa es una deuda válida de la acción aunque
            # no exista ningún Prestamo.
            #
            # NO se crea un préstamo ficticio.
            # La deuda se mantiene como deuda_multa virtual.
            # ======================================================

            if not prestamos_con_saldo:

                deuda_multa = multa_periodo_anterior

                amortizacion_aplicada = min(
                    amortizacion,
                    deuda_multa
                ).quantize(
                    Decimal("0.01")
                )

                deuda_multa_restante = (
                    deuda_multa -
                    amortizacion_aplicada
                ).quantize(
                    Decimal("0.01")
                )

                if deuda_multa_restante < Decimal("0.00"):
                    deuda_multa_restante = Decimal("0.00")

                pendiente = (
                    amortizacion -
                    amortizacion_aplicada
                ).quantize(
                    Decimal("0.01")
                )

                print("\n==============================================")
                print("RECONSTRUIR SALDOS ACCIÓN - SOLO MULTA")
                print("==============================================")
                print(f"Acción                  : {accion_id}")
                print(f"Período                 : {periodo_id}")
                print(f"Multa anterior          : {multa_periodo_anterior}")
                print(f"Amortización solicitada : {amortizacion}")
                print(f"Amortización aplicada   : {amortizacion_aplicada}")
                print(f"Deuda multa restante    : {deuda_multa_restante}")
                print("Préstamos anteriores    : 0")
                print("==============================================\n")

                return {
                    "accion_id": accion_id,
                    "periodo_id": periodo_id,
                    "amortizacion_aplicada": amortizacion_aplicada,
                    "amortizacion_pendiente": pendiente,
                    "multa_aplicada": multa_periodo_anterior,
                    "saldo_total_prestamos": Decimal("0.00"),
                    "saldo_deuda_multa": deuda_multa_restante,
                    "prestamos_actualizados": 0,
                    "prestamos_cancelados": 0
                }

            # ======================================================
            # CASO NORMAL:
            # EXISTEN PRÉSTAMOS
            #
            # NO CAMBIAR ESTA LÓGICA.
            # ======================================================

            prestamo_multa = prestamos_con_saldo[0]
            saldo_actual = Decimal(
                str(
                    prestamo_multa.saldo_actual or 0
                )
            ).quantize(
                Decimal("0.01")
            )
            prestamo_multa.saldo_actual = (
                saldo_actual +
                multa_periodo_anterior
            ).quantize(
                Decimal("0.01")
            )

            prestamo_multa.estado = "ACTIVO"
            multa_aplicada = multa_periodo_anterior
        # ==========================================================
        # 5. APLICAR AMORTIZACIÓN
        #    MÁS ANTIGUO → MÁS NUEVO
        # ==========================================================

        pendiente = amortizacion
        amortizacion_aplicada = Decimal("0.00")

        prestamos_actualizados = 0
        prestamos_cancelados = 0

        for prestamo in prestamos:

            if pendiente <= Decimal("0.00"):
                break

            saldo_actual = Decimal(
                str(prestamo.saldo_actual or 0)
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
                saldo_actual - amortizacion_prestamo
            ).quantize(Decimal("0.01"))

            if nuevo_saldo < Decimal("0.00"):
                nuevo_saldo = Decimal("0.00")

            prestamo.saldo_actual = nuevo_saldo

            if nuevo_saldo == Decimal("0.00"):

                prestamo.estado = "CANCELADO"
                prestamos_cancelados += 1

            else:

                prestamo.estado = "ACTIVO"

            pendiente -= amortizacion_prestamo
            amortizacion_aplicada += amortizacion_prestamo
            prestamos_actualizados += 1

        pendiente = max(
            pendiente,
            Decimal("0.00")
        ).quantize(Decimal("0.01"))

        amortizacion_aplicada = (
            amortizacion_aplicada
        ).quantize(Decimal("0.01"))

        if pendiente > Decimal("0.01"):
            raise Exception(
                "No fue posible aplicar toda la amortización "
                f"de la acción. Pendiente: S/ {pendiente}"
            )

        # ==========================================================
        # 6. FORZAR FLUSH
        # ==========================================================

        db.flush()

        # ==========================================================
        # 7. SALDO CONSOLIDADO REAL
        # ==========================================================
        saldo_total_prestamos = (
            db.query(
                func.coalesce(
                    func.sum(Prestamo.saldo_actual),
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
            str(saldo_total_prestamos or 0)
        ).quantize(Decimal("0.01"))

        # ==========================================================
        # DEBUG
        # ==========================================================

        print("\n==============================================")
        print("RECONSTRUIR SALDOS ACCIÓN")
        print("==============================================")
        print(f"Acción                  : {accion_id}")
        print(f"Período                 : {periodo_id}")
        print(f"Multa anterior         : {multa_periodo_anterior}")
        print(f"Multa aplicada         : {multa_aplicada}")
        print(f"Amortización solicitada : {amortizacion}")
        print(f"Amortización aplicada   : {amortizacion_aplicada}")
        print(f"Saldo préstamos final  : {saldo_total_prestamos}")

        for prestamo in prestamos:

            print(
                f"  Préstamo {prestamo.id} "
                f"| período={prestamo.periodo_id} "
                f"| saldo={prestamo.saldo_actual}"
            )

        print("==============================================\n")

        return {
            "accion_id": accion_id,
            "periodo_id": periodo_id,
            "amortizacion_aplicada": amortizacion_aplicada,
            "amortizacion_pendiente": pendiente,
            "multa_aplicada": multa_aplicada,
            "saldo_total_prestamos": saldo_total_prestamos,
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