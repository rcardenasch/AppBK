from decimal import Decimal

from sqlalchemy import func

from models.periodo import Periodo
from models.prestamo import Prestamo
from models.socio import Socio
from models.movimiento import Movimiento
from models.configuracion import Configuracion

from services.interes_service import InteresService
from services.movimiento_service import MovimientoService
from services.prestamo_service import PrestamoService


class RegistroMensualService:

    @staticmethod
    def generar_periodo(db, periodo_id):

        # =========================================================
        # CONFIGURACIÓN
        # =========================================================

        configuracion = (
            db.query(Configuracion)
            .filter(
                Configuracion.estado == True
            )
            .first()
        )

        if not configuracion:
            raise Exception(
                "No existe configuración del sistema"
            )

        # =========================================================
        # PERÍODO
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
                "Periodo no encontrado"
            )

        if periodo.cerrado:
            raise Exception(
                "No se pueden generar movimientos "
                "en un periodo cerrado"
            )

        # =========================================================
        # SOCIOS ACTIVOS
        # =========================================================

        socios = (
            db.query(Socio)
            .filter(
                Socio.estado == True
            )
            .all()
        )

        movimientos_creados = 0
        prestamos_actualizados = 0

        # =========================================================
        # RECORRER SOCIOS
        # =========================================================

        for socio in socios:

            # =====================================================
            # RECORRER ACCIONES
            # =====================================================

            for accion in socio.acciones:

                # =================================================
                # VERIFICAR MOVIMIENTO EXISTENTE
                # =================================================

                movimiento_existente = (
                    db.query(Movimiento)
                    .filter(
                        Movimiento.socio_id == socio.id,
                        Movimiento.accion_id == accion.id,
                        Movimiento.periodo_id == periodo_id
                    )
                    .first()
                )

                if movimiento_existente:
                    continue

                # =================================================
                # APORTE
                # =================================================

                aporte = Decimal(
                    str(
                        configuracion.aporte_minimo or 0
                    )
                ).quantize(
                    Decimal("0.01")
                )

                # =================================================
                # SOBRE
                # =================================================

                sobre = (
                    Decimal("1.00")
                    *
                    Decimal(
                        str(
                            configuracion.sobre_por_accion or 0
                        )
                    )
                ).quantize(
                    Decimal("0.01")
                )

                # =================================================
                # SALDO APERTURA
                # =================================================

                saldo_apertura = (
                    PrestamoService
                    .obtener_saldo_apertura_accion(
                        db=db,
                        accion_id=accion.id,
                        periodo_id=periodo_id
                    )
                )

                saldo_apertura = Decimal(
                    str(
                        saldo_apertura or 0
                    )
                ).quantize(
                    Decimal("0.01")
                )

                # =================================================
                # MULTA ANTERIOR
                # =================================================

                multa_anterior = (
                    MovimientoService
                    .obtener_multa_periodo_anterior_accion(
                        db=db,
                        accion_id=accion.id,
                        periodo_id=periodo_id
                    )
                )

                multa_anterior = Decimal(
                    str(
                        multa_anterior or 0
                    )
                ).quantize(
                    Decimal("0.01")
                )

                # =========================================================
                # DETERMINAR CUOTA POR SOCIO + ACCIÓN
                # =========================================================
                #
                # REGLA:
                #
                # La cuota mínima proviene de la tabla.
                #
                # PERO si la deuda total puede cancelarse con una
                # cuota menor, se utiliza la cuota exacta de cancelación.
                #
                # cuota_cancelacion =
                #       aporte
                #     + interes
                #     + deuda
                #
                # cuota_aplicada =
                #       MIN(cuota_minima_tabla, cuota_cancelacion)
                #
                # Esto aplica para:
                #
                #   1. Préstamo pendiente
                #   2. Multa pendiente
                #   3. Múltiples préstamos
                #   4. Préstamo + multa
                #   5. Préstamo nuevo del período
                #   6. Deuda cercana a cero
                #
                # =========================================================

                CENTAVOS = Decimal("0.01")

                # ---------------------------------------------------------
                # 1. CALCULAR LA DEUDA REAL DEL PERÍODO
                # ---------------------------------------------------------
                #
                # Utilizamos el MOTOR FINANCIERO CENTRAL.
                #
                # IMPORTANTE:
                # Aquí NO estamos registrando ningún movimiento.
                # Solo estamos haciendo una simulación para conocer:
                #
                #   - interés
                #   - deuda total
                #   - préstamos nuevos
                #
                # La cuota provisional es solamente el aporte.
                #
                # ---------------------------------------------------------

                resultado_base = (
                    MovimientoService
                    .calcular_movimiento_accion(
                        db=db,
                        accion_id=accion.id,
                        periodo_id=periodo_id,
                        aporte=aporte,
                        cuota_pagada=aporte,
                        multa_periodo_anterior_override=multa_anterior,
                        saldo_apertura_override=saldo_apertura
                    )
                )

                interes_base = Decimal(
                    str(
                        resultado_base["interes"] or 0
                    )
                ).quantize(CENTAVOS)

                deuda_total = Decimal(
                    str(
                        resultado_base["saldo_deuda"] or 0
                    )
                ).quantize(CENTAVOS)

                saldo_nuevos = Decimal(
                    str(
                        resultado_base["saldo_prestamos_nuevos"] or 0
                    )
                ).quantize(CENTAVOS)


                # =========================================================
                # CASO SIN DEUDA
                # =========================================================

                if deuda_total <= Decimal("0.00"):

                    monto_base_cuota = Decimal("0.00")

                    cuota_pagada = aporte

                    print("CASO                  : SIN DEUDA")

                else:

                    # =====================================================
                    # EXISTE DEUDA
                    # =====================================================

                    monto_base_cuota = deuda_total

                    # -----------------------------------------------------
                    # CUOTA MÍNIMA SEGÚN TABLA
                    # -----------------------------------------------------

                    cuota_minima_tabla = (
                        PrestamoService
                        .calcular_cuota_minima(
                            monto_base_cuota
                        )
                    )

                    cuota_minima_tabla = Decimal(
                        str(
                            cuota_minima_tabla or 0
                        )
                    ).quantize(CENTAVOS)

                    # -----------------------------------------------------
                    # CUOTA EXACTA PARA CANCELAR LA DEUDA
                    # -----------------------------------------------------
                    #
                    # La deuda ya contiene:
                    #
                    #   saldo préstamo
                    #   + multa anterior
                    #   + préstamos nuevos
                    #
                    # El interés se calculó sobre:
                    #
                    #   saldo apertura
                    #   + multa anterior
                    #
                    # Los préstamos nuevos NO generan interés
                    # durante el mismo período.
                    #
                    # -----------------------------------------------------

                    cuota_cancelacion = (
                        aporte
                        + interes_base
                        + deuda_total
                    ).quantize(CENTAVOS)

                    # -----------------------------------------------------
                    # REGLA DEFINITIVA
                    # -----------------------------------------------------

                    cuota_pagada = min(
                        cuota_minima_tabla,
                        cuota_cancelacion
                    ).quantize(CENTAVOS)

                    # -----------------------------------------------------
                    # DEBUG
                    # -----------------------------------------------------

                    print("\n==============================================")
                    print("CÁLCULO CUOTA MÍNIMA / CANCELACIÓN")
                    print("==============================================")

                    print(f"Saldo apertura       : {saldo_apertura}")
                    print(f"Multa anterior       : {multa_anterior}")
                    print(f"Préstamos nuevos     : {saldo_nuevos}")
                    print(f"Deuda total          : {deuda_total}")
                    print(f"Interés              : {interes_base}")
                    print(f"Aporte               : {aporte}")
                    print(f"Cuota tabla           : {cuota_minima_tabla}")
                    print(f"Cuota cancelación    : {cuota_cancelacion}")
                    print(f"Cuota aplicada       : {cuota_pagada}")

                    if cuota_cancelacion < cuota_minima_tabla:

                        print(
                            "REGLA APLICADA       : "
                            "CANCELACIÓN ANTICIPADA"
                        )

                    else:

                        print(
                            "REGLA APLICADA       : "
                            "CUOTA MÍNIMA"
                        )

                    print("==============================================\n")

                # =========================================================
                # DEBUG
                # =========================================================

                print("\n==============================================")
                print("DETERMINACIÓN DE CUOTA")
                print("==============================================")
                print(f"Socio                 : {socio.id}")
                print(f"Acción                : {accion.id}")
                print(f"Período               : {periodo_id}")
                print(f"Saldo préstamo        : {saldo_apertura}")
                print(f"Multa anterior        : {multa_anterior}")
                print(f"Base cuota            : {monto_base_cuota}")
                print(f"Cuota aplicada        : {cuota_pagada}")

                if saldo_apertura > 0:

                    print("CASO                  : 1 - PRÉSTAMO PENDIENTE")

                elif multa_anterior > 0:

                    print("CASO                  : 2 - MULTA PENDIENTE")

                else:

                    print("CASO                  : 3 - SIN DEUDA")

                print("==============================================\n")

                # =================================================
                # CÁLCULO FINANCIERO CENTRALIZADO
                # =================================================

                resultado = (
                    MovimientoService
                    .calcular_movimiento_accion(
                        db=db,
                        accion_id=accion.id,
                        periodo_id=periodo_id,
                        aporte=aporte,
                        cuota_pagada=cuota_pagada,
                        # La cuota ya fue calculada considerando
                        # multa_anterior.
                        multa_periodo_anterior_override=multa_anterior,
                        # Saldo SOLO de préstamos.
                        saldo_apertura_override=saldo_apertura
                    )
                )

                # =================================================
                # VALIDACIÓN
                # =================================================

                if resultado["cuota_pagada"] != cuota_pagada:

                    raise Exception(
                        f"Inconsistencia en cuota calculada "
                        f"para acción {accion.id}."
                    )

                # =========================================================
                # PRÉSTAMO REFERENCIA
                # =========================================================
                #
                # Únicamente para guardar prestamo_id como referencia
                # en Movimiento.
                #
                # NO participa en ningún cálculo.
                # =========================================================

                prestamo_referencia = None

                prestamo_referencia = (
                    db.query(Prestamo)
                    .filter(
                        Prestamo.accion_id == accion.id,
                        Prestamo.saldo_actual > 0
                    )
                    .order_by(
                        Prestamo.fecha_prestamo.asc(),
                        Prestamo.id.asc()
                    )
                    .first()
                )


                # =================================================
                # CREAR MOVIMIENTO
                # =================================================

                movimiento = Movimiento(
                    socio_id=socio.id,
                    accion_id=accion.id,
                    periodo_id=periodo_id,

                    prestamo_id=(
                        prestamo_referencia.id
                        if prestamo_referencia
                        else None
                    ),

                    aporte=resultado["aporte"],
                    cuota_pagada=resultado["cuota_pagada"],
                    interes=resultado["interes"],
                    amortizacion=resultado["amortizacion"],
                    saldo_prestamo=resultado["saldo_prestamo"],

                    multa=Decimal("0.00"),
                    sobre=sobre,

                    observacion=(
                        "Registro mensual automático. "
                        #f"Saldo préstamo: S/ {saldo_apertura:.2f}. "
                        #f"Multa anterior: S/ {multa_anterior:.2f}. "
                        #f"Base cuota: S/ {monto_base_cuota:.2f}. "
                        #f"Cuota aplicada: S/ {cuota_pagada:.2f}."
                    )
                )

                db.add(movimiento)

                # =================================================
                # RECONSTRUIR SALDOS
                # =================================================

                resultado_saldos = (
                    PrestamoService
                    .reconstruir_saldos_accion_periodo(
                        db=db,
                        accion_id=accion.id,
                        periodo_id=periodo_id,
                        amortizacion=resultado["amortizacion"],
                        multa_periodo_anterior=multa_anterior
                    )
                )

                prestamos_actualizados += (
                    resultado_saldos[
                        "prestamos_actualizados"
                    ]
                )

                movimientos_creados += 1

        # =========================================================
        # COMMIT
        # =========================================================

        db.commit()

        return {
            "socios_procesados": len(socios),
            "movimientos_creados": movimientos_creados,
            "prestamos_actualizados": prestamos_actualizados
        }