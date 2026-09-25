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
                # REGLAS DEFINITIVAS
                #
                # CASO 1:
                # La acción tiene préstamo pendiente:
                #
                #     saldo_apertura > 0
                #
                #     Si multa anterior = 0:
                #         base cuota = saldo_apertura
                #
                #     Si multa anterior > 0:
                #         base cuota = saldo_apertura + multa_anterior
                #
                #     La tabla calcular_cuota_minima() devuelve la CUOTA TOTAL.
                #
                #
                # CASO 2:
                # No hay préstamo pendiente pero existe multa anterior:
                #
                #     cuota =
                #         aporte
                #         + multa_anterior
                #         + interés
                #
                #
                # CASO 3:
                # No hay préstamo pendiente ni multa:
                #
                #     cuota = aporte
                #
                #
                # IMPORTANTE:
                # NO utilizar Prestamo.monto.
                # NO buscar el préstamo de mayor monto.
                # La deuda de la acción se obtiene de saldo_apertura.
                # =========================================================

                monto_base_cuota = Decimal("0.00")


                # =========================================================
                # CASO 1
                # LA ACCIÓN TIENE DEUDA DE PRÉSTAMO
                # =========================================================

                if saldo_apertura > Decimal("0.00"):

                    # -----------------------------------------------------
                    # BASE PARA DETERMINAR LA CUOTA
                    # -----------------------------------------------------
                    #
                    # Si existe multa anterior, forma parte de la deuda
                    # sobre la cual se determina la cuota.
                    #
                    # Ejemplo:
                    #
                    # saldo préstamo = 1008.90
                    # multa anterior =   40.00
                    #
                    # base = 1048.90
                    #
                    # -----------------------------------------------------

                    monto_base_cuota = (
                        saldo_apertura +
                        multa_anterior
                    ).quantize(
                        Decimal("0.01")
                    )

                    # -----------------------------------------------------
                    # LA TABLA DEVUELVE LA CUOTA TOTAL
                    # -----------------------------------------------------

                    cuota_pagada = (
                        PrestamoService
                        .calcular_cuota_minima(
                            monto_base_cuota
                        )
                    )

                    cuota_pagada = Decimal(
                        str(
                            cuota_pagada or 0
                        )
                    ).quantize(
                        Decimal("0.01")
                    )


                # =========================================================
                # CASO 2
                # NO HAY PRÉSTAMO PENDIENTE
                # PERO EXISTE MULTA DEL PERÍODO ANTERIOR
                # =========================================================

                elif multa_anterior > Decimal("0.00"):

                    # -----------------------------------------------------
                    # La deuda corresponde solamente a la multa anterior.
                    #
                    # No debemos considerar préstamos históricos
                    # que ya fueron cancelados.
                    #
                    # La cuota debe cubrir:
                    #
                    #     aporte
                    #   + multa anterior
                    #   + interés
                    #
                    # -----------------------------------------------------

                    monto_base_cuota = multa_anterior

                    # -----------------------------------------------------
                    # Usamos el MOTOR FINANCIERO para obtener el interés.
                    #
                    # La cuota provisional permite calcular el interés
                    # sobre la multa anterior.
                    # -----------------------------------------------------

                    resultado_multa = (
                        MovimientoService
                        .calcular_movimiento_accion(
                            db=db,
                            accion_id=accion.id,
                            periodo_id=periodo_id,
                            aporte=aporte,
                            cuota_pagada=(
                                aporte +
                                multa_anterior
                            ).quantize(
                                Decimal("0.01")
                            ),
                            multa_periodo_anterior_override=multa_anterior,
                            saldo_apertura_override=saldo_apertura #Decimal("0.00")
                        )
                    )

                    interes_multa = Decimal(
                        str(
                            resultado_multa["interes"] or 0
                        )
                    ).quantize(
                        Decimal("0.01")
                    )

                    # -----------------------------------------------------
                    # CUOTA TOTAL
                    # -----------------------------------------------------
                    cuota_pagada = (
                        aporte +
                        multa_anterior +
                        interes_multa
                    ).quantize(
                        Decimal("0.01")
                    )

                # =========================================================
                # CASO 3
                # SIN PRÉSTAMO PENDIENTE
                # SIN MULTA ANTERIOR
                # =========================================================
                else:

                    monto_base_cuota = Decimal("0.00")
                    cuota_pagada = aporte

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