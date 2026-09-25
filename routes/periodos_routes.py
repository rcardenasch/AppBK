# routes/periodos.py

from decimal import Decimal

from flask import Blueprint, session
from flask import jsonify
from sqlalchemy import func

from models.asistencia import Asistencia
from models.movimiento import Movimiento
from models.prestamo import Prestamo
from models.solicitud_prestamo import SolicitudPrestamo
from models.transferencia import Transferencia
from services.cierre_service import CierreService
from flask import render_template
from flask_login import login_required

from flask import request
from flask import redirect
from flask import url_for
from flask import flash

from datetime import date

from database.connection import SessionLocal

from models.periodo import Periodo
from services.movimiento_service import MovimientoService

periodos_bp = Blueprint(
    "periodos",
    __name__,
    url_prefix="/periodos"
)

# ============================================================
# PRECIERRE DE CONSISTENCIA
# ============================================================

@periodos_bp.route(
    "/precierre/<int:periodo_id>",
    methods=["GET"]
)
@login_required
def precierre(periodo_id):

    db = SessionLocal()

    try:

        # =====================================================
        # PERÍODO
        # =====================================================

        periodo = (
            db.query(Periodo)
            .filter(
                Periodo.id == periodo_id
            )
            .first()
        )

        if not periodo:

            flash(
                "Período no encontrado.",
                "danger"
            )

            return redirect(
                url_for("periodos.index")
            )


        # =====================================================
        # RESULTADOS
        # =====================================================

        validaciones = []
        errores = 0
        advertencias = 0
        correctos = 0


        def agregar(
            codigo,
            titulo,
            descripcion,
            estado,
            cantidad=0,
            detalle=None
        ):

            nonlocal errores
            nonlocal advertencias
            nonlocal correctos

            if estado == "ERROR":
                errores += 1

            elif estado == "WARNING":
                advertencias += 1

            else:
                correctos += 1

            validaciones.append({

                "codigo": codigo,
                "titulo": titulo,
                "descripcion": descripcion,
                "estado": estado,
                "cantidad": cantidad,
                "detalle": detalle or []
            })


        # =====================================================
        # 1. ESTADO DEL PERÍODO
        # =====================================================

        if periodo.cerrado:

            agregar(
                "PERIODO_CERRADO",
                "Período abierto",
                "El período ya se encuentra cerrado.",
                "ERROR"
            )

        else:

            agregar(
                "PERIODO_ABIERTO",
                "Período abierto",
                "El período está disponible para revisión y cierre.",
                "OK"
            )


        # =====================================================
        # 2. MOVIMIENTOS DEL PERÍODO
        # =====================================================

        movimientos = (
            db.query(Movimiento)
            .filter(
                Movimiento.periodo_id == periodo_id
            )
            .all()
        )

        if not movimientos:

            agregar(
                "SIN_MOVIMIENTOS",
                "Movimientos registrados",
                "No existen movimientos registrados para el período.",
                "ERROR"
            )

        else:

            agregar(
                "MOVIMIENTOS_EXISTENTES",
                "Movimientos registrados",
                "Existen movimientos para el período.",
                "OK",
                len(movimientos)
            )


        # =====================================================
        # 3. DUPLICADOS SOCIO + ACCIÓN
        # =====================================================

        duplicados = (
            db.query(
                Movimiento.socio_id,
                Movimiento.accion_id,
                func.count(Movimiento.id).label("cantidad")
            )
            .filter(
                Movimiento.periodo_id == periodo_id
            )
            .group_by(
                Movimiento.socio_id,
                Movimiento.accion_id
            )
            .having(
                func.count(Movimiento.id) > 1
            )
            .all()
        )

        detalle_duplicados = []

        for socio_id, accion_id, cantidad in duplicados:

            detalle_duplicados.append({
                "socio_id": socio_id,
                "accion_id": accion_id,
                "cantidad": cantidad
            })


        if duplicados:

            agregar(
                "MOVIMIENTOS_DUPLICADOS",
                "Movimientos duplicados",
                "Existe más de un movimiento para la misma acción en el período.",
                "ERROR",
                len(duplicados),
                detalle_duplicados
            )

        else:

            agregar(
                "MOVIMIENTOS_DUPLICADOS",
                "Movimientos duplicados",
                "No existen duplicados por socio, acción y período.",
                "OK"
            )


        # =====================================================
        # 4. VALORES NEGATIVOS
        # =====================================================

        negativos = []

        for m in movimientos:

            campos = {

                "aporte": m.aporte,
                "cuota_pagada": m.cuota_pagada,
                "interes": m.interes,
                "amortizacion": m.amortizacion,
                "saldo_prestamo": m.saldo_prestamo,
                "multa": m.multa,
                "sobre": m.sobre
            }

            campos_negativos = [
                campo
                for campo, valor in campos.items()
                if Decimal(
                    str(valor or 0)
                ) < Decimal("0.00")
            ]

            if campos_negativos:

                negativos.append({

                    "movimiento_id": m.id,

                    "accion_id":
                        m.accion_id,

                    "campos":
                        ", ".join(
                            campos_negativos
                        )
                })


        if negativos:

            agregar(
                "VALORES_NEGATIVOS",
                "Valores negativos",
                "Existen importes negativos en movimientos.",
                "ERROR",
                len(negativos),
                negativos
            )

        else:

            agregar(
                "VALORES_NEGATIVOS",
                "Valores negativos",
                "No existen importes negativos.",
                "OK"
            )


        # =====================================================
        # 5. CONSISTENCIA DE CUOTA
        #
        # REGLAS:
        #
        # CUOTA BASE = APORTE + INTERÉS + AMORTIZACIÓN
        #
        # La multa del período actual NO forma parte de la cuota.
        #
        # La multa del período anterior puede:
        #
        #   1. No pagarse
        #   2. Pagarse parcialmente
        #   3. Pagarse completamente
        #
        # Por eso:
        #
        #   pago_multa = cuota - cuota_base
        #
        # y:
        #
        #   multa_pendiente =
        #       multa_anterior - pago_multa
        #
        # Clasificación:
        #
        #   OK
        #       - No se pagó multa anterior
        #       - Se pagó el 100% de la multa anterior
        #
        #   ADVERTENCIA
        #       - Se pagó parcialmente la multa anterior
        #
        #   ERROR
        #       - Se pagó más multa de la existente
        #       - La cuota no puede ser explicada por sus componentes
        # =====================================================

        inconsistencias_cuota = []

        for m in movimientos:

            # =================================================
            # DATOS DEL MOVIMIENTO
            # =================================================

            aporte = Decimal(
                str(m.aporte or 0)
            ).quantize(
                Decimal("0.01")
            )

            interes = Decimal(
                str(m.interes or 0)
            ).quantize(
                Decimal("0.01")
            )

            amortizacion = Decimal(
                str(m.amortizacion or 0)
            ).quantize(
                Decimal("0.01")
            )

            cuota = Decimal(
                str(m.cuota_pagada or 0)
            ).quantize(
                Decimal("0.01")
            )

            # =================================================
            # MULTA DEL PERÍODO ANTERIOR
            # =================================================

            multa_anterior = (
                MovimientoService
                .obtener_multa_periodo_anterior_accion(
                    db=db,
                    accion_id=m.accion_id,
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

            # =================================================
            # CUOTA BASE
            #
            # NO incluye multa.
            # =================================================

            cuota_base = (
                aporte
                + interes
                + amortizacion
            ).quantize(
                Decimal("0.01")
            )

            # =================================================
            # DETERMINAR PAGO DE MULTA
            #
            # Si la cuota es mayor que la cuota base,
            # la diferencia representa pago de multa anterior.
            # =================================================

            pago_multa = (
                cuota
                - cuota_base
            ).quantize(
                Decimal("0.01")
            )

            # =================================================
            # CASO: CUOTA MENOR A LA BASE
            #
            # Esto no puede explicarse con el pago de multa.
            # =================================================

            if pago_multa < Decimal("0.00"):

                multa_pendiente = multa_anterior

                diferencia = (
                    cuota
                    - cuota_base
                ).quantize(
                    Decimal("0.01")
                )

                inconsistencias_cuota.append({

                    "movimiento_id": m.id,
                    "accion_id": m.accion_id,
                    "aporte": str(aporte),
                    "multa_anterior": str(multa_anterior),
                    "pago_multa": "0.00",
                    "multa_pendiente": str(multa_pendiente),
                    "interes": str(interes),
                    "amortizacion": str(amortizacion),
                    "cuota_base": str(cuota_base),
                    "cuota_esperada": str(cuota_base),
                    "cuota_registrada": str(cuota),
                    "diferencia": str(diferencia),
                    "estado": "ERROR",
                    "detalle": (
                        "La cuota registrada es menor que "
                        "aporte + interés + amortización."
                    )
                })

                continue

            # =================================================
            # CASO: NO EXISTE MULTA ANTERIOR
            # =================================================

            if multa_anterior == Decimal("0.00"):

                if pago_multa == Decimal("0.00"):

                    estado = "OK"
                    detalle = (
                        "La cuota coincide con aporte + "
                        "interés + amortización."
                    )

                else:

                    estado = "ERROR"
                    detalle = (
                        "Se registra un pago de multa, "
                        "pero no existe multa pendiente "
                        "del período anterior."
                    )

                multa_pendiente = Decimal("0.00")

            # =================================================
            # CASO: EXISTE MULTA ANTERIOR
            # =================================================

            else:

                # ---------------------------------------------
                # NO PAGÓ MULTA
                # ---------------------------------------------

                if pago_multa == Decimal("0.00"):

                    estado = "OK"

                    detalle = (
                        "No se pagó la multa del período "
                        "anterior. La multa queda pendiente."
                    )

                    multa_pendiente = multa_anterior

                # ---------------------------------------------
                # PAGÓ TODA LA MULTA
                # ---------------------------------------------

                elif pago_multa == multa_anterior:

                    estado = "OK"

                    detalle = (
                        "Se pagó el 100% de la multa "
                        "del período anterior."
                    )

                    multa_pendiente = Decimal("0.00")

                # ---------------------------------------------
                # PAGO PARCIAL
                # ---------------------------------------------

                elif (
                    pago_multa > Decimal("0.00")
                    and pago_multa < multa_anterior
                ):

                    estado = "ADVERTENCIA"

                    detalle = (
                        "Se pagó parcialmente la multa "
                        "del período anterior."
                    )

                    multa_pendiente = (
                        multa_anterior
                        - pago_multa
                    ).quantize(
                        Decimal("0.01")
                    )

                # ---------------------------------------------
                # PAGÓ MÁS DE LA MULTA
                # ---------------------------------------------

                else:

                    estado = "ERROR"

                    detalle = (
                        "El pago de multa es mayor que "
                        "la multa pendiente del período anterior."
                    )

                    multa_pendiente = Decimal("0.00")

            # =================================================
            # CUOTA ESPERADA
            #
            # Cuota base + pago de multa
            # =================================================

            cuota_esperada = (
                cuota_base
                + pago_multa
            ).quantize(
                Decimal("0.01")
            )

            diferencia = (
                cuota
                - cuota_esperada
            ).quantize(
                Decimal("0.01")
            )

            # =================================================
            # VALIDACIÓN FINAL
            # =================================================

            if diferencia != Decimal("0.00"):

                estado = "ERROR"

                detalle = (
                    "La cuota registrada no coincide "
                    "con sus componentes financieros."
                )

            # =================================================
            # REGISTRAR RESULTADO
            #
            # Guardamos OK también si quieres mostrar
            # el detalle completo en la vista.
            # =================================================

            if estado != "OK" or multa_anterior > Decimal("0.00"):

                inconsistencias_cuota.append({

                    "movimiento_id": m.id,
                    "accion_id": m.accion_id,
                    "aporte": str(aporte),
                    "multa_anterior": str(
                        multa_anterior
                    ),
                    "pago_multa": str(
                        pago_multa
                    ),
                    "multa_pendiente": str(
                        multa_pendiente
                    ),
                    "interes": str(interes),
                    "amortizacion": str(
                        amortizacion
                    ),
                    "cuota_base": str(
                        cuota_base
                    ),
                    "cuota_esperada": str(
                        cuota_esperada
                    ),
                    "cuota_registrada": str(
                        cuota
                    ),
                    "diferencia": str(
                        diferencia
                    ),
                    "estado": estado,
                    "detalle": detalle
                })


        # =====================================================
        # RESULTADO GENERAL
        # =====================================================

        errores_cuota = [
            x
            for x in inconsistencias_cuota
            if x["estado"] == "ERROR"
        ]

        advertencias_cuota = [
            x
            for x in inconsistencias_cuota
            if x["estado"] == "ADVERTENCIA"
        ]


        # =====================================================
        # EXISTEN ERRORES
        # =====================================================

        if errores_cuota:

            agregar(
                "CUOTA_COMPONENTES",
                "Consistencia de cuota",
                (
                    "Existen cuotas que no pueden justificarse "
                    "con aporte, interés, amortización y pago "
                    "de multa anterior."
                ),
                "ERROR",
                len(errores_cuota),
                inconsistencias_cuota
            )


        # =====================================================
        # SOLO ADVERTENCIAS
        # =====================================================

        elif advertencias_cuota:

            agregar(
                "CUOTA_COMPONENTES",
                "Consistencia de cuota",
                (
                    "Existen cuotas con pago parcial de "
                    "la multa del período anterior. "
                    "Requieren revisión."
                ),
                "ADVERTENCIA",
                len(advertencias_cuota),
                inconsistencias_cuota
            )


        # =====================================================
        # TODO CORRECTO
        # =====================================================

        else:

            agregar(
                "CUOTA_COMPONENTES",
                "Consistencia de cuota",
                (
                    "Todas las cuotas son consistentes. "
                    "Las multas anteriores pueden no haberse "
                    "pagado o haberse cancelado completamente."
                ),
                "OK"
            )


        # =====================================================
        # 6. CONSISTENCIA MOVIMIENTO VS PRÉSTAMOS
        # =====================================================

        inconsistencias_saldo = []

        for m in movimientos:

            if not m.accion_id:
                continue

            # =================================================
            # 1. AMORTIZACIÓN REGISTRADA
            # =================================================

            amortizacion = Decimal(
                str(m.amortizacion or 0)
            ).quantize(
                Decimal("0.01")
            )

            # =================================================
            # 2. SALDO ACTUAL DE LOS PRÉSTAMOS
            #
            # IMPORTANTE:
            # Este saldo YA es posterior a la amortización.
            # =================================================

            saldo_prestamos = (
                db.query(
                    func.coalesce(
                        func.sum(Prestamo.saldo_actual),
                        0
                    )
                )
                .filter(
                    Prestamo.accion_id == m.accion_id,
                    Prestamo.periodo_id < periodo_id,
                    Prestamo.saldo_actual > 0
                )
                .scalar()
            )

            saldo_prestamos = Decimal(
                str(saldo_prestamos or 0)
            ).quantize(
                Decimal("0.01")
            )

            # =================================================
            # 3. MULTA DEL PERÍODO ANTERIOR
            # =================================================

            multa_anterior = (
                MovimientoService
                .obtener_multa_periodo_anterior_accion(
                    db=db,
                    accion_id=m.accion_id,
                    periodo_id=periodo_id
                )
            )

            multa_anterior = Decimal(
                str(multa_anterior or 0)
            ).quantize(
                Decimal("0.01")
            )

            # =================================================
            # 4. SALDO DEL MOVIMIENTO
            #
            # Este campo representa CAPITAL pendiente.
            # NO incluye multa.
            # =================================================

            saldo_movimiento = Decimal(
                str(m.saldo_prestamo or 0)
            ).quantize(
                Decimal("0.01")
            )

            # =================================================
            # 5. RECONSTRUIR SALDO DE CAPITAL INICIAL
            #
            # Si Prestamo.saldo_actual ya tiene aplicada la
            # amortización del período:
            #
            # saldo inicial capital =
            #       saldo actual
            #       + amortización aplicada al capital
            #
            # =================================================

            saldo_apertura_capital = (
                saldo_prestamos +
                amortizacion
            ).quantize(
                Decimal("0.01")
            )

            # =================================================
            # 6. DEUDA TOTAL AL INICIO
            #
            # CAPITAL + MULTA
            #
            # Esto es solamente informativo.
            # NO se usa directamente para calcular
            # saldo_prestamo.
            # =================================================

            deuda_inicial = (
                saldo_apertura_capital +
                multa_anterior
            ).quantize(
                Decimal("0.01")
            )

            # =================================================
            # 7. SALDO ESPERADO DE CAPITAL
            #
            # La multa NO se resta aquí.
            #
            # La amortización del movimiento afecta al capital.
            # =================================================

            saldo_esperado = (
                saldo_apertura_capital -
                amortizacion
            ).quantize(
                Decimal("0.01")
            )

            if saldo_esperado < Decimal("0.00"):
                saldo_esperado = Decimal("0.00")

            # =================================================
            # 8. DIFERENCIA
            # =================================================

            diferencia_movimiento = (
                saldo_movimiento -
                saldo_esperado
            ).quantize(
                Decimal("0.01")
            )

            # =================================================
            # 9. VALIDAR MOVIMIENTO
            # =================================================

            error_movimiento = (
                diferencia_movimiento != Decimal("0.00")
            )

            # =================================================
            # 10. VALIDAR PRÉSTAMOS
            #
            # El saldo real de Prestamo debe coincidir con
            # el saldo esperado después de la amortización.
            # =================================================

            diferencia_prestamos = (
                saldo_prestamos -
                saldo_esperado
            ).quantize(
                Decimal("0.01")
            )

            error_prestamos = (
                diferencia_prestamos != Decimal("0.00")
            )

            # =================================================
            # 11. REGISTRAR ERROR
            # =================================================

            if error_movimiento or error_prestamos:

                inconsistencias_saldo.append({
                    "movimiento_id": m.id,
                    "accion_id": m.accion_id,
                    "saldo_apertura_capital": str(saldo_apertura_capital),
                    "multa_anterior": str(multa_anterior),
                    "deuda_inicial": str(deuda_inicial),
                    "amortizacion": str(amortizacion),
                    "saldo_esperado": str(saldo_esperado),
                    "saldo_prestamos": str(saldo_prestamos),
                    "saldo_movimiento": str(saldo_movimiento),
                    "diferencia_movimiento": str(diferencia_movimiento),
                    "diferencia_prestamos": str(diferencia_prestamos),
                    "error_movimiento": error_movimiento,
                    "error_prestamos": error_prestamos
                })


        # =====================================================
        # RESULTADO
        # =====================================================

        if inconsistencias_saldo:

            agregar(
                "SALDO_MOVIMIENTO_PRESTAMO",
                "Saldo movimiento vs préstamos",
                (
                    "El saldo de capital del movimiento "
                    "no coincide con el saldo reconstruido "
                    "de los préstamos."
                ),
                "ERROR",
                len(inconsistencias_saldo),
                inconsistencias_saldo
            )

        else:

            agregar(
                "SALDO_MOVIMIENTO_PRESTAMO",
                "Saldo movimiento vs préstamos",
                (
                    "El saldo de capital de los movimientos "
                    "coincide con el saldo de los préstamos."
                ),
                "OK"
            )

    
        # =====================================================
        # 7. ESTADO DE PRÉSTAMOS
        # =====================================================

        prestamos = (
            db.query(Prestamo)
            .all()
        )

        inconsistencias_prestamos = []

        for p in prestamos:

            saldo = Decimal(
                str(
                    p.saldo_actual or 0
                )
            ).quantize(
                Decimal("0.01")
            )

            if saldo > 0 and p.estado != "ACTIVO":

                inconsistencias_prestamos.append({
                    "prestamo_id": p.id,
                    "accion_id": p.accion_id,
                    "saldo": str(saldo),
                    "estado": p.estado,
                    "esperado": "ACTIVO"
                })


            elif (
                saldo <= 0
                and p.estado == "ACTIVO"
            ):

                inconsistencias_prestamos.append({
                    "prestamo_id": p.id,
                    "accion_id": p.accion_id,
                    "saldo": str(saldo),
                    "estado": p.estado,
                    "esperado": "CANCELADO"
                })


        if inconsistencias_prestamos:

            agregar(
                "ESTADO_PRESTAMOS",
                "Estado de préstamos",
                "Existen préstamos cuyo estado no corresponde a su saldo.",
                "ERROR",
                len(inconsistencias_prestamos),
                inconsistencias_prestamos
            )

        else:

            agregar(
                "ESTADO_PRESTAMOS",
                "Estado de préstamos",
                "El estado de los préstamos corresponde a su saldo actual.",
                "OK"
            )


        # =====================================================
        # 8. ASISTENCIA
        # =====================================================

        asistencias = (
            db.query(Asistencia)
            .filter(
                Asistencia.periodo_id ==
                periodo_id
            )
            .all()
        )

        socios_con_asistencia = set(
            a.socio_id
            for a in asistencias
        )

        movimientos_socio = set(
            m.socio_id
            for m in movimientos
        )

        faltan_asistencias = sorted(
            movimientos_socio
            - socios_con_asistencia
        )


        if faltan_asistencias:

            agregar(
                "ASISTENCIAS",
                "Asistencias registradas",
                "Existen socios con movimiento pero sin asistencia registrada.",
                "ERROR",
                len(faltan_asistencias),
                [
                    {
                        "socio_id": socio_id
                    }
                    for socio_id
                    in faltan_asistencias
                ]
            )

        else:

            agregar(
                "ASISTENCIAS",
                "Asistencias registradas",
                "Los socios con movimientos tienen asistencia registrada.",
                "OK"
            )

        # =====================================================
        # 9. ASISTENCIA VS MULTA
        # =====================================================

        inconsistencias_multas = []

        for asistencia in asistencias:

            estado = (
                getattr(
                    asistencia,
                    "estado",
                    ""
                )
                or ""
            ).upper().strip()

            if estado not in (
                "TARDANZA",
                "FALTA"
            ):
                continue

            multa_movimiento = (
                db.query(
                    func.coalesce(
                        func.sum(
                            Movimiento.multa
                        ),
                        0
                    )
                )
                .filter(
                    Movimiento.socio_id == asistencia.socio_id,
                    Movimiento.periodo_id == periodo_id
                )
                .scalar()
            )

            multa_movimiento = Decimal(
                str(
                    multa_movimiento or 0
                )
            ).quantize(
                Decimal("0.01")
            )


            if multa_movimiento <= 0:

                inconsistencias_multas.append({

                    "socio_id": asistencia.socio_id,
                    "estado_asistencia": estado,
                    "multa_registrada": str(multa_movimiento)
                })


        if inconsistencias_multas:

            agregar(
                "ASISTENCIA_MULTA",
                "Asistencia vs multas",
                "Existen inasistencias sin multa registrada.",
                "ERROR",
                len(inconsistencias_multas),
                inconsistencias_multas
            )

        else:

            agregar(
                "ASISTENCIA_MULTA",
                "Asistencia vs multas",
                "No se detectaron inconsistencias básicas entre asistencia y multas.",
                "OK"
            )


        # =====================================================
        # 10. SOLICITUDES APROBADAS
        # =====================================================

        solicitudes = (
            db.query(SolicitudPrestamo)
            .filter(
                SolicitudPrestamo.periodo_id ==
                periodo_id,

                SolicitudPrestamo.estado ==
                "ATENDIDA"
            )
            .all()
        )

        monto_aprobado = sum(
            (
                Decimal(
                    str(
                        s.monto_aprobado or 0
                    )
                )
                for s in solicitudes
            ),
            Decimal("0.00")
        ).quantize(
            Decimal("0.01")
        )


        # =====================================================
        # 11. PRÉSTAMOS DEL PERÍODO
        # =====================================================

        prestamos_periodo = (
            db.query(Prestamo)
            .filter(
                Prestamo.periodo_id ==
                periodo_id,

                Prestamo.monto > 0
            )
            .all()
        )


        monto_prestamos_periodo = sum(
            (
                Decimal(
                    str(
                        p.monto or 0
                    )
                )
                for p in prestamos_periodo
            ),
            Decimal("0.00")
        ).quantize(
            Decimal("0.01")
        )


        # -----------------------------------------------------
        # Esto es WARNING, no ERROR automático:
        #
        # Prestamo no tiene solicitud_id.
        # Por ello se compara el total y no cada solicitud.
        # -----------------------------------------------------

        diferencia_aprobado_prestamos = (
            monto_aprobado
            - monto_prestamos_periodo
        ).quantize(
            Decimal("0.01")
        )


        if diferencia_aprobado_prestamos != 0:

            agregar(
                "APROBADOS_VS_PRESTAMOS",
                "Solicitudes aprobadas vs préstamos",
                "El total aprobado no coincide exactamente con los préstamos registrados en el período.",
                "WARNING",
                len(solicitudes),
                [
                    {
                        "monto_aprobado": str(monto_aprobado),
                        "monto_prestamos": str(monto_prestamos_periodo),
                        "diferencia": str(diferencia_aprobado_prestamos)
                    }
                ]
            )

        else:

            agregar(
                "APROBADOS_VS_PRESTAMOS",
                "Solicitudes aprobadas vs préstamos",
                "El total aprobado coincide con los préstamos registrados del período.",
                "OK"
            )


        # =====================================================
        # 12. TRANSFERENCIAS
        # =====================================================

        transferencias = (
            db.query(Transferencia)
            .filter(
                Transferencia.periodo_id ==
                periodo_id
            )
            .all()
        )


        transferencias_confirmadas = [
            t
            for t in transferencias
            if t.estado == "CONFIRMADA"
        ]


        total_transferencias = sum(
            (
                Decimal(
                    str(
                        t.monto or 0
                    )
                )
                for t in transferencias_confirmadas
            ),
            Decimal("0.00")
        ).quantize(
            Decimal("0.01")
        )


        transferencias_invalidas = []

        for t in transferencias_confirmadas:

            monto = Decimal(
                str(
                    t.monto or 0
                )
            ).quantize(
                Decimal("0.01")
            )

            if monto <= 0:

                transferencias_invalidas.append({
                    "id": t.id,
                    "monto": str(monto)
                })

            if (
                t.socio_origen_id ==
                t.socio_destino_id
            ):

                transferencias_invalidas.append({
                    "id": t.id,
                    "error":
                        "Origen y destino son iguales."
                })


        if transferencias_invalidas:

            agregar(
                "TRANSFERENCIAS",
                "Consistencia de transferencias",
                "Existen transferencias confirmadas inválidas.",
                "ERROR",
                len(transferencias_invalidas),
                transferencias_invalidas
            )

        else:

            agregar(
                "TRANSFERENCIAS",
                "Consistencia de transferencias",
                "Las transferencias confirmadas tienen estructura válida.",
                "OK",
                len(transferencias_confirmadas)
            )


        # =====================================================
        # 13. RESUMEN MONETARIO
        # =====================================================

        total_aportes = sum(
            (
                Decimal(
                    str(
                        m.aporte or 0
                    )
                )
                for m in movimientos
            ),
            Decimal("0.00")
        ).quantize(
            Decimal("0.01")
        )


        total_cuotas = sum(
            (
                Decimal(
                    str(
                        m.cuota_pagada or 0
                    )
                )
                for m in movimientos
            ),
            Decimal("0.00")
        ).quantize(
            Decimal("0.01")
        )


        total_intereses = sum(
            (
                Decimal(
                    str(
                        m.interes or 0
                    )
                )
                for m in movimientos
            ),
            Decimal("0.00")
        ).quantize(
            Decimal("0.01")
        )


        total_amortizacion = sum(
            (
                Decimal(
                    str(
                        m.amortizacion or 0
                    )
                )
                for m in movimientos
            ),
            Decimal("0.00")
        ).quantize(
            Decimal("0.01")
        )


        total_multas = sum(
            (
                Decimal(
                    str(
                        m.multa or 0
                    )
                )
                for m in movimientos
            ),
            Decimal("0.00")
        ).quantize(
            Decimal("0.01")
        )


        total_sobre = sum(
            (
                Decimal(
                    str(
                        m.sobre or 0
                    )
                )
                for m in movimientos
            ),
            Decimal("0.00")
        ).quantize(
            Decimal("0.01")
        )


        saldo_prestamos = sum(
            (
                Decimal(
                    str(
                        p.saldo_actual or 0
                    )
                )
                for p in prestamos
                if Decimal(
                    str(
                        p.saldo_actual or 0
                    )
                ) > 0
            ),
            Decimal("0.00")
        ).quantize(
            Decimal("0.01")
        )


        # =====================================================
        # 14. RESULTADO FINAL
        # =====================================================

        puede_cerrar = (
            not periodo.cerrado
            and errores == 0
        )


        return render_template(
            "periodos/precierre.html",

            periodo=periodo,
            validaciones=validaciones,
            errores=errores,
            advertencias=advertencias,
            correctos=correctos,
            puede_cerrar=puede_cerrar,
            resumen={

                "movimientos": len(movimientos),
                "asistencias": len(asistencias),
                "solicitudes_aprobadas": len(solicitudes),
                "monto_aprobado": monto_aprobado,
                "prestamos_periodo": len(prestamos_periodo),
                "monto_prestamos_periodo": monto_prestamos_periodo,
                "total_aportes": total_aportes,
                "total_cuotas": total_cuotas,
                "total_intereses": total_intereses,
                "total_amortizacion": total_amortizacion,
                "total_multas": total_multas,
                "total_sobre": total_sobre,
                "saldo_prestamos": saldo_prestamos,
                "transferencias": len(transferencias_confirmadas),
                "total_transferencias": total_transferencias
            }
        )


    except Exception as e:

        db.rollback()

        flash(
            f"Error generando precierre: {str(e)}",
            "danger"
        )

        return redirect(
            url_for("periodos.index")
        )

    finally:

        db.close()

# ==========================================================
# CERRAR PERÍODO
# ==========================================================
@periodos_bp.route(
    "/<int:periodo_id>/cerrar",
    methods=["POST"]
)
@login_required
def cerrar(periodo_id):

    resultado = (
        CierreService.cierre_periodo(
            periodo_id
        )
    )

    if not resultado["success"]:

        flash(
            f"No se pudo cerrar el periodo: "
            f"{resultado['error']}",
            "danger"
        )

        return redirect(
            url_for(
                "periodos.index",
                id=periodo_id
            )
        )

    flash(
        (
            f"Periodo cerrado correctamente. "
            f"Movimientos: {resultado['movimientos']}. "
            f"Saldo de caja: "
            f"S/ {resultado['saldo_caja']:.2f}. "
            f"Utilidad: "
            f"S/ {resultado['utilidad_total']:.2f}."
        ),
        "success"
    )

    return redirect(
        url_for(
            "periodos.index"
        )
    )

# ===============================================
# EXTORNAR CIERRE DE PERÍODO
# ===============================================
@periodos_bp.route(
    "/<int:periodo_id>/extornar-cierre",
    methods=["POST"]
)
@login_required
def extornar_cierre_periodo(periodo_id):

    try:

        resultado = (
            CierreService
            .extornar_cierre_periodo(
                periodo_id
            )
        )

        if resultado["success"]:

            flash(
                resultado["mensaje"],
                "success"
            )

        else:

            flash(
                f"No se pudo extornar el cierre: "
                f"{resultado['error']}",
                "danger"
            )

    except Exception as e:

        flash(
            f"No se pudo extornar el cierre: {e}",
            "danger"
        )

    return redirect(
        url_for(
            "periodos.index"
        )
    )

###############################################################
# Lista de periodos
###############################################################

@periodos_bp.route("/")
@login_required
def index():
    db = SessionLocal()
    try:
        periodos = db.query(Periodo).order_by(
            Periodo.anio.desc(), 
            Periodo.mes.desc()
        ).all()

        resultado_generacion = session.pop(
            "resultado_generacion_periodo",
            None
        )
        return render_template("periodos/index.html", periodos=periodos,resultado_generacion=resultado_generacion)
    finally:
        db.close()

# CREAR
@periodos_bp.route("/nuevo",
methods=["GET","POST"])
@login_required
def nuevo():

    if request.method=="POST":

        db = SessionLocal()

        try:

            periodo = Periodo(

                anio=int(
                    request.form["anio"]
                ),

                mes=int(
                    request.form["mes"]
                ),

                fecha_inicio=date.fromisoformat(
                    request.form["fecha_inicio"]
                ),

                fecha_fin=date.fromisoformat(
                    request.form["fecha_fin"]
                )

            )


            db.add(periodo)

            db.commit()


            flash(
                "Periodo creado correctamente",
                "success"
            )


            return redirect(
                url_for(
                    "periodos.index"
                )
            )


        except Exception as e:

            db.rollback()

            flash(
                str(e),
                "danger"
            )

        finally:

            db.close()


    return render_template(
        "periodos/form.html"
    )


# EDITAR
@periodos_bp.route(
"/editar/<int:id>",
methods=["GET","POST"]
)
@login_required
def editar(id):

    db=SessionLocal()

    try:

        periodo=db.query(
            Periodo
        ).get(id)


        if request.method=="POST":

            if periodo.cerrado:

                flash(
                    "Periodo cerrado no puede modificarse",
                    "warning"
                )

                return redirect(
                    url_for(
                        "periodos.index"
                    )
                )


            periodo.anio=int(
                request.form["anio"]
            )

            periodo.mes=int(
                request.form["mes"]
            )

            periodo.fecha_inicio=date.fromisoformat(
                request.form["fecha_inicio"]
            )

            periodo.fecha_fin=date.fromisoformat(
                request.form["fecha_fin"]
            )


            db.commit()


            flash(
                "Periodo actualizado",
                "success"
            )


            return redirect(
                url_for(
                    "periodos.index"
                )
            )


        return render_template(
            "periodos/form.html",
            periodo=periodo
        )


    finally:
        db.close()


# ELIMINAR
@periodos_bp.route(
"/eliminar/<int:id>",
methods=["POST"]
)
@login_required
def eliminar(id):

    db=SessionLocal()
    try:

        periodo=db.query(
            Periodo
        ).get(id)

        if periodo.cerrado:
            flash(
                "No puede eliminar un periodo cerrado",
                "danger"
            )
            return redirect(
                url_for(
                    "periodos.index"
                )
            )
        db.delete(periodo)
        db.commit()
        flash(
            "Periodo eliminado",
            "success"
        )
        return redirect(
            url_for(
                "periodos.index"
            )
        )

    finally:
        db.close()

