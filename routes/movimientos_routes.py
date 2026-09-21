from flask import Blueprint, jsonify, session
from flask import render_template
from flask import request
from flask import redirect
from flask import url_for
from flask import flash
from decimal import Decimal

from flask_login import login_required
from sqlalchemy import func

from database.connection import SessionLocal
from services.cierre_service import CierreService
from services.movimiento_service import MovimientoService
from services.prestamo_service import PrestamoService
from services.registro_mensual_service import RegistroMensualService
from services.utilidades_service import UtilidadesService
from services.interes_service import InteresService

from models.movimiento import Movimiento
from models.prestamo   import Prestamo
from models.accion import Accion
from models.periodo import Periodo
from models.configuracion import Configuracion
from sqlalchemy.orm import joinedload


movimientos_bp = Blueprint(
    "movimientos",
    __name__,
    url_prefix="/movimientos"
)
#@movimientos_bp.route("/nuevo/<int:socio_id>/<int:accion_id>")
@movimientos_bp.route("/nuevo/<int:accion_id>")
@login_required
def nuevo(accion_id):

    db = SessionLocal()

    try:
        prestamo_id = request.form.get("prestamo_id")

        accion = (
            db.query(Accion)
            .options(
                joinedload(Accion.socio),
                joinedload(Accion.prestamos)
            )
            .filter(
                Accion.id == accion_id
            )
            .first()
        )

        prestamos = [

            p for p in accion.prestamos
            if p.estado == "ACTIVO"
        ]

        periodos = (
            db.query(Periodo)
            .filter(
                Periodo.cerrado == False
            )
            .all()
        )

        return render_template(
            "movimientos/form.html",
            accion=accion,
            socio=accion.socio,
            prestamos=prestamos,
            periodos=periodos
        )

    finally:

        db.close()

#
# Guardar Nuevo Movimiento
#        
@movimientos_bp.route("/guardar", methods=["POST"])
@login_required
def guardar():

    db = SessionLocal()
    accion_id = None

    try:

        socio_id = int(request.form["socio_id"])
        accion_id = int(request.form["accion_id"])
        periodo_id = int(request.form["periodo_id"])

        sobre = Decimal(
            str(request.form.get("sobre", "0"))
        )

        accion = (
            db.query(Accion)
            .filter(
                Accion.id == accion_id,
                Accion.socio_id == socio_id
            )
            .first()
        )

        if not accion:
            raise Exception(
                "La acción no pertenece al socio."
            )

        periodo = (
            db.query(Periodo)
            .filter(
                Periodo.id == periodo_id
            )
            .first()
        )

        if not periodo:
            raise Exception(
                "El período no existe."
            )

        if periodo.cerrado:
            raise Exception(
                "No se puede registrar un movimiento "
                "en un período cerrado."
            )

        # ======================================================
        # PRÉSTAMO ACTIVO DE LA ACCIÓN
        # ======================================================

        prestamo = (
            db.query(Prestamo)
            .filter(
                Prestamo.accion_id == accion_id,
                Prestamo.estado == "ACTIVO"
            )
            .first()
        )

        # ======================================================
        # EVITAR DUPLICADO
        # ======================================================

        existe = (
            db.query(Movimiento)
            .filter(
                Movimiento.accion_id == accion_id,
                Movimiento.periodo_id == periodo_id
            )
            .first()
        )

        if existe:

            flash(
                "Ya existe un movimiento registrado "
                "para esta acción en el período seleccionado.",
                "warning"
            )

            return redirect(
                url_for(
                    "movimientos.nuevo",
                    accion_id=accion_id
                )
            )

        # ======================================================
        # REGISTRAR MOVIMIENTO
        # ======================================================

        datos = MovimientoService.registrar_movimiento(
            db=db,
            socio_id=socio_id,
            accion_id=accion_id,
            periodo_id=periodo_id,
            prestamo=prestamo,
            aporte=request.form["aporte"],
            cuota_pagada=request.form["cuota"],
            multa=request.form["multa"],
            sobre=sobre,
            observacion=request.form.get(
                "observacion",
                ""
            )
        )

        # IMPORTANTE:
        # registrar_movimiento debe devolver saldo_prestamo
        # pero NO saldo_interes.

        movimiento = Movimiento(**datos)

        db.add(movimiento)

        # ======================================================
        # ACTUALIZAR SALDO DEL PRÉSTAMO
        # ======================================================

        if prestamo:

            prestamo.saldo_actual = Decimal(
                str(datos["saldo_prestamo"] or 0)
            )

            if prestamo.saldo_actual <= 0:

                prestamo.saldo_actual = Decimal("0.00")
                prestamo.estado = "CANCELADO"

            else:

                prestamo.estado = "ACTIVO"

        db.commit()

        flash(
            "Movimiento registrado correctamente.",
            "success"
        )

        return redirect(
            url_for(
                "acciones.detalle",
                id=accion_id
            )
        )

    except Exception as e:

        db.rollback()

        flash(
            str(e),
            "danger"
        )

        if accion_id:

            return redirect(
                url_for(
                    "acciones.detalle",
                    id=accion_id
                )
            )

        return redirect(
            url_for(
                "socios.listar"
            )
        )

    finally:
        db.close()



# ==============================
# Generar movimiento masivos del periodo
# ==============================
@movimientos_bp.route(
    "/generar/<int:periodo_id>",
    methods=["POST"]
)
@login_required
def generar(periodo_id):
    db = SessionLocal()
    try:
        periodo = (
            db.query(Periodo)
            .filter(
                Periodo.id == periodo_id
            )
            .first()
        )
        if not periodo:
            flash(
                "Periodo no encontrado.",
                "danger"
            )
            return redirect(
                url_for("periodos.index")
            )
        if periodo.cerrado:
            flash(
                "No se pueden generar movimientos de un periodo cerrado.",
                "warning"
            )
            return redirect(
                url_for(
                    "periodos.index",
                    id=periodo_id
                )
            )
        print("Ingrese a resultado")
        resultado = (
            RegistroMensualService.generar_periodo(
                db,
                periodo_id
            )
        
        )

        # =====================================================
        # GUARDAR RESULTADO PARA MOSTRARLO DESPUÉS, en vez del Flask
        # =====================================================

        session[
            "resultado_generacion_periodo"
        ] = {

            "socios_procesados": int(
                resultado.get(
                    "socios_procesados",
                    0
                )
            ),

            "movimientos_creados": int(
                resultado.get(
                    "movimientos_creados",
                    0
                )
            ),

            "prestamos_actualizados": int(
                resultado.get(
                    "prestamos_actualizados",
                    0
                )
            )
        }

        return redirect(
            url_for(
                "periodos.index",
                id=periodo_id
                
            )
        )
    except Exception as e:

        db.rollback()
        flash(
            f"Error al generar movimientos: {str(e)}",
            "danger"
        )
        return redirect(
            url_for(
                "periodos.index",
                id=periodo_id
            )
        )
    finally:

        db.close()


#
# RECUPERA MOVIMIENTO MEDIANTE AJAX AL MODAL EDITAR MOVIMIENTO
#
@movimientos_bp.route(
    "/api/movimiento/<int:id>",
    methods=["GET"]
)
@login_required
def api_movimiento(id):

    db = SessionLocal()

    try:

        movimiento = (
            db.query(Movimiento)
            .filter(
                Movimiento.id == id
            )
            .first()
        )

        if not movimiento:

            return jsonify({
                "ok": False,
                "mensaje":
                    "Movimiento no encontrado."
            }), 404


        return jsonify({

            "ok": True,
            "movimiento": {
                "id":
                    movimiento.id,
                "socio_id":
                    movimiento.socio_id,
                "accion_id":
                    movimiento.accion_id,
                "periodo_id":
                    movimiento.periodo_id,
                "prestamo_id":
                    movimiento.prestamo_id,
                "aporte":
                    float(
                        movimiento.aporte or 0
                    ),
                "cuota_pagada":
                    float(
                        movimiento.cuota_pagada or 0
                    ),
                "multa":
                    float(
                        movimiento.multa or 0
                    ),
                "sobre":
                    float(
                        movimiento.sobre or 0
                    ),
                "interes":
                    float(
                        movimiento.interes or 0
                    ),
                "amortizacion":
                    float(
                        movimiento.amortizacion or 0
                    ),
                "saldo_prestamo":
                    float(
                        movimiento.saldo_prestamo or 0
                    ),
                "observacion":
                    movimiento.observacion or ""
            }

        })

    except Exception as e:

        return jsonify({

            "ok": False,
            "mensaje": str(e)

        }), 400

    finally:

        db.close()


# ============================================================
# API DE DEUDA DE UNA ACCIÓN
# ============================================================

@movimientos_bp.route(
    "/api/accion/<int:accion_id>",
    methods=["GET"]
)
@login_required
def api_accion(accion_id):

    db = SessionLocal()

    try:

        # =====================================================
        # CONFIGURACIÓN
        # =====================================================

        config = (
            db.query(Configuracion)
            .filter(
                Configuracion.estado == True
            )
            .first()
        )

        aporte_min = (
            Decimal(
                str(
                    config.aporte_minimo
                )
            )
            if config
            and config.aporte_minimo is not None
            else Decimal("0.00")
        ).quantize(
            Decimal("0.01")
        )


        # =====================================================
        # PERÍODO
        # =====================================================

        periodo_id = request.args.get(
            "periodo_id",
            type=int
        )

        if not periodo_id:

            return jsonify({

                "ok": False,

                "error":
                    "Debe indicar el período."
            }), 400


        # =====================================================
        # VERIFICAR ACCIÓN
        # =====================================================

        accion = (
            db.query(Accion)
            .filter(
                Accion.id == accion_id
            )
            .first()
        )

        if not accion:

            return jsonify({

                "ok": False,

                "error":
                    "No existe la acción."
            }), 404


        # =====================================================
        # RESUMEN DE DEUDA
        #
        # MISMO SERVICIO UTILIZADO POR:
        #
        # - Nuevo movimiento
        # - Editar movimiento
        # - Generar período
        # =====================================================

        resumen = (
            PrestamoService.obtener_resumen_deuda_accion(
                db=db,
                accion_id=accion_id,
                periodo_id=periodo_id
            )
        )


        return jsonify({

            "ok": True,
            "accion_id":
                accion_id,
            "periodo_id":
                periodo_id,
            "saldo":
                float(
                    resumen["saldo_base"]
                ),
            "saldo_apertura":
                float(
                    resumen["saldo_apertura"]
                ),
            "multa_periodo_anterior":
                float(
                    resumen[
                        "multa_periodo_anterior"
                    ]
                ),
            "saldo_base":
                float(
                    resumen["saldo_base"]
                ),
            "interes":
                float(
                    resumen["interes"]
                ),
            "aporte":
                float(
                    aporte_min
                ),
            "cuota":
                float(
                    resumen["cuota"]
                )
        })


    except Exception as e:

        return jsonify({

            "ok": False,
            "error": str(e)

        }), 400


    finally:

        db.close()


# ============================================================
# RECALCULA DESDE MOVIMIENTO
# ============================================================
@staticmethod
def recalcular_desde_movimientos(db, prestamo_id):

    movimientos = (
        db.query(Movimiento)
        .filter(
            Movimiento.prestamo_id == prestamo_id
        )
        .order_by(
            Movimiento.periodo_id.asc(),
            Movimiento.id.asc()
        )
        .all()
    )

    prestamo = (
        db.query(Prestamo)
        .filter(
            Prestamo.id == prestamo_id
        )
        .first()
    )

    if not prestamo:
        raise Exception(
            "Préstamo no encontrado."
        )

    # =====================================================
    # SALDO INICIAL DEL PRÉSTAMO
    # =====================================================

    saldo = Decimal(
        str(prestamo.monto or 0)
    )

    # =====================================================
    # RECORRER MOVIMIENTOS EN ORDEN
    # =====================================================

    for movimiento in movimientos:

        resultado = (
            PrestamoService.calcular_pago_sobre_saldo(
                db,
                prestamo,
                saldo,
                movimiento.aporte,
                movimiento.cuota_pagada
            )
        )

        movimiento.interes = (
            resultado["interes"]
        )

        movimiento.amortizacion = (
            resultado["amortizacion"]
        )

        movimiento.saldo_prestamo = (
            resultado["saldo_prestamo"]
        )

        # El siguiente movimiento parte
        # del saldo resultante de este.
        saldo = (
            resultado["saldo_prestamo"]
        )

    # =====================================================
    # ACTUALIZAR PRÉSTAMO
    # =====================================================

    prestamo.saldo_actual = saldo

    if saldo <= 0:

        prestamo.saldo_actual = Decimal("0.00")
        #prestamo.saldo_interes = Decimal("0.00")
        prestamo.estado = "CANCELADO"

    else:

        prestamo.saldo_actual = saldo

        # Para el siguiente período,
        # el interés se calculará sobre este saldo.
        #prestamo.saldo_interes = saldo

        prestamo.estado = "ACTIVO"

    return prestamo


# ============================================================
# EDITAR MOVIMIENTO
# ============================================================

@movimientos_bp.route(
    "/editar_movimiento/<int:id>",
    methods=["GET", "POST"]
)
@login_required
def editar_movimiento(id):

    db = SessionLocal()

    try:

        # =====================================================
        # OBTENER MOVIMIENTO
        # =====================================================

        movimiento = (
            db.query(Movimiento)
            .options(
                joinedload(Movimiento.socio),
                joinedload(Movimiento.accion),
                joinedload(Movimiento.prestamo),
                joinedload(Movimiento.periodo)
            )
            .filter(
                Movimiento.id == id
            )
            .first()
        )

        if not movimiento:
            return jsonify({
                "ok": False,
                "mensaje": "Movimiento no encontrado."
            }), 404

        # =====================================================
        # GET
        # =====================================================

        if request.method == "GET":

            return jsonify({

                "ok": True,

                "movimiento": {

                    "id": movimiento.id,
                    "socio_id": movimiento.socio_id,
                    "accion_id": movimiento.accion_id,
                    "periodo_id": movimiento.periodo_id,
                    "aporte": float(movimiento.aporte or 0),
                    "cuota_pagada": float(movimiento.cuota_pagada or 0),
                    "multa": float(movimiento.multa or 0),
                    "sobre": float(movimiento.sobre or 0),
                    "interes": float(movimiento.interes or 0),
                    "amortizacion": float(movimiento.amortizacion or 0),
                    "saldo_prestamo": float(movimiento.saldo_prestamo or 0),
                    "observacion": (movimiento.observacion or ""),
                    "prestamo_id": movimiento.prestamo_id
                }
            })

        # =====================================================
        # PERÍODO CERRADO
        # =====================================================

        if movimiento.periodo.cerrado:

            return jsonify({
                "ok": False,
                "mensaje": (
                    "No se puede modificar un movimiento "
                    "de un período cerrado."
                )
            }), 400

        # =====================================================
        # GUARDAR VALORES ANTERIORES
        # =====================================================

        amortizacion_anterior = Decimal(
            str(
                movimiento.amortizacion or 0
            )
        ).quantize(
            Decimal("0.01")
        )

        interes_anterior = Decimal(
            str(
                movimiento.interes or 0
            )
        ).quantize(
            Decimal("0.01")
        )

        saldo_anterior = Decimal(
            str(
                movimiento.saldo_prestamo or 0
            )
        ).quantize(
            Decimal("0.01")
        )

        # =====================================================
        # DATOS NUEVOS
        # =====================================================

        aporte = Decimal(
            str(
                request.form.get(
                    "aporte",
                    "0"
                )
            )
        ).quantize(
            Decimal("0.01")
        )

        cuota_pagada = Decimal(
            str(
                request.form.get(
                    "cuota_pagada",
                    request.form.get(
                        "cuota",
                        "0"
                    )
                )
            )
        ).quantize(
            Decimal("0.01")
        )

        multa = Decimal(
            str(
                request.form.get(
                    "multa",
                    "0"
                )
            )
        ).quantize(
            Decimal("0.01")
        )

        sobre = Decimal(
            str(
                request.form.get(
                    "sobre",
                    "0"
                )
            )
        ).quantize(
            Decimal("0.01")
        )

        observacion = request.form.get(
            "observacion",
            ""
        )

        # =====================================================
        # VALIDACIONES
        # =====================================================

        if aporte < 0:
            raise Exception(
                "El aporte no puede ser negativo."
            )

        if cuota_pagada <= 0:
            raise Exception(
                "La cuota pagada no puede ser negativa ó Cero."
            )

        if multa < 0:
            raise Exception(
                "La multa no puede ser negativa."
            )

        if sobre < 0:
            raise Exception(
                "El sobre no puede ser negativo."
            )

        # =========================================================
        # 1. RESTAURAR AMORTIZACIÓN ANTERIOR
        # =========================================================

        restauracion = PrestamoService.restaurar_amortizacion_movimiento(
            db=db,
            movimiento=movimiento
        )


        # =========================================================
        # 2. OBTENER SALDO RESTAURADO DE LA ACCIÓN
        # =========================================================

        if restauracion.get("solo_multa"):

            # -----------------------------------------------------
            # CASO ESPECIAL:
            # La acción no tiene préstamos.
            # La deuda anterior corresponde únicamente a una multa.
            #
            # Esa multa restaurada se considera como saldo de
            # apertura y NO debe volver a sumarse como multa.
            # -----------------------------------------------------

            saldo_restaurado = Decimal(
                str(
                    restauracion.get(
                        "saldo_multa_restaurado",
                        0
                    )
                )
            ).quantize(
                Decimal("0.01")
            )

        else:

            # -----------------------------------------------------
            # CASO NORMAL:
            # existen préstamos y la amortización anterior ya fue
            # restaurada sobre ellos.
            # -----------------------------------------------------

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
            ).quantize(
                Decimal("0.01")
            )


        # =========================================================
        # 3. CALCULAR NUEVO MOVIMIENTO
        # =========================================================

        resultado = (
            MovimientoService
            .calcular_movimiento_accion(
                db=db,
                accion_id=movimiento.accion_id,
                periodo_id=movimiento.periodo_id,
                aporte=aporte,
                cuota_pagada=cuota_pagada,
                # IMPORTANTE:
                # NO pasar multa_periodo_anterior_override
                # para que el motor consulte la multa anterior.
                saldo_apertura_override=saldo_restaurado
            )
        )

        # =========================================================
        # VALIDAR AMORTIZACIÓN CONTRA DEUDA
        # =========================================================

        deuda_calculada = Decimal(str(resultado["saldo_deuda"] or 0)).quantize(Decimal("0.01"))
        amortizacion_calculada = Decimal(str(resultado["amortizacion"] or 0)).quantize(Decimal("0.01"))
        interes_calculado = Decimal(str(resultado["interes"] or 0)).quantize(Decimal("0.01"))
        multa_periodo_anterior=Decimal(str(resultado["multa_periodo_anterior"] or 0)).quantize(Decimal("0.01"))
        # La amortización nunca puede superar la deuda
        if amortizacion_calculada > deuda_calculada:

            raise Exception(
                "La amortización calculada supera la deuda "
                "pendiente de la acción."
            )

        # =========================================================
        # VALIDAR CUOTA TOTAL
        # cuota = aporte + interés + amortización + sobre
        # =========================================================
        cuota_esperada = (
            aporte
            + interes_calculado
            + amortizacion_calculada
            # Agregué
            + sobre
            + multa_periodo_anterior
        ).quantize(
            Decimal("0.01")
        )

        #if cuota_pagada != cuota_esperada:

        #    raise Exception(
        #        "La cuota no coincide con sus componentes. "
        #        f"Cuota registrada: S/ {cuota_pagada:.2f} | "
        #        f"Esperada: S/ {cuota_esperada:.2f}"
        #    )

        # =========================================================
        # 4. DEBUG
        # =========================================================
        print("\n==============================================")
        print("EDITAR MOVIMIENTO - RECÁLCULO")
        print("==============================================")
        print(f"Movimiento              : "f"{movimiento.id}" )
        print(f"Acción                  : "f"{movimiento.accion_id}")
        print(f"Período                 : "f"{movimiento.periodo_id}")
        print(f"Saldo anterior          : "f"{saldo_anterior}")
        print(f"Interés anterior        : "f"{interes_anterior}")
        print(f"Amortización anterior   : "f"{amortizacion_anterior}")
        print(f"Saldo restaurado        : "f"{saldo_restaurado}")
        print(f"Multa NO reaplicada     : "f"S/ 0.00")
        print(f"Base interés            : "f"{resultado['saldo_base_interes']}")
        print(f"Interés nuevo           : "f"{resultado['interes']}")
        print(f"Aporte                  : "f"{aporte}")
        print(f"Cuota                   : "f"{cuota_pagada}")
        print(f"Amortización nueva      : "f"{resultado['amortizacion']}")
        print(f"Saldo final             : "f"{resultado['saldo_prestamo']}")
        print("==============================================\n")

        # =========================================================
        # 5. ACTUALIZAR MOVIMIENTO
        # =========================================================

        movimiento.aporte = aporte
        movimiento.cuota_pagada = (cuota_pagada)
        movimiento.multa = multa
        movimiento.sobre = sobre
        movimiento.interes = (resultado["interes"])
        movimiento.amortizacion = (resultado["amortizacion"])
        movimiento.saldo_prestamo = (resultado["saldo_prestamo"])
        movimiento.observacion = (observacion)

        # =========================================================
        # 6. RECONSTRUIR PRÉSTAMOS
        #
        # IMPORTANTÍSIMO:
        #
        # NO pasar multa anterior.
        #
        # El préstamo ya contiene la multa.
        #
        # Solo debemos aplicar la NUEVA amortización.
        # =========================================================

        reconstruccion = (
            PrestamoService
            .reconstruir_saldos_accion_periodo(
                db=db,
                accion_id=movimiento.accion_id,
                periodo_id=movimiento.periodo_id,
                amortizacion=resultado["amortizacion"],
                multa_periodo_anterior=Decimal("0.00"),

                # =================================================
                # SOLO PARA EL CASO:
                # acción sin préstamo + multa anterior
                # =================================================
                saldo_multa_restaurado=(
                    restauracion.get(
                        "saldo_multa_restaurado"
                    )
                    if restauracion.get("solo_multa")
                    else None
                )
            )
        )
        # =========================================================
        # 7. VALIDACIÓN DE CONSISTENCIA
        # =========================================================

        saldo_prestamos = (
            db.query(
                func.coalesce(
                    func.sum(
                        Prestamo.saldo_actual
                    ),
                    0
                )
            )
            .filter(
                Prestamo.accion_id ==
                movimiento.accion_id,
                # NO considerar préstamos creados en el
                # período que se está editando.
                Prestamo.periodo_id <
                movimiento.periodo_id,
                Prestamo.saldo_actual > 0
            )
            .scalar()
        )

        saldo_prestamos = Decimal(
            str(
                saldo_prestamos or 0
            )
        ).quantize(
            Decimal("0.01")
        )

        # =========================================================
        # SALDO DE MULTA
        # =========================================================
        saldo_multa = Decimal(
            str(
                reconstruccion.get(
                    "saldo_deuda_multa",
                    0
                ) or 0
            )
        ).quantize(
            Decimal("0.01")
        )

        # =========================================================
        # SALDO TOTAL REAL DE LA ACCIÓN
        # =========================================================

        saldo_deuda_real = (
            saldo_prestamos +
            saldo_multa
        ).quantize(
            Decimal("0.01")
        )

        # =========================================================
        # SALDO DEL MOVIMIENTO
        # =========================================================
        saldo_movimiento = Decimal(
            str(
                movimiento.saldo_prestamo or 0
            )
        ).quantize(
            Decimal("0.01")
        )

        # =========================================================
        # DEBUG
        # =========================================================
        print("\n==============================================")
        print("VALIDACIÓN SALDOS")
        print("==============================================")
        print(f"Saldo préstamos     : "f"S/ {saldo_prestamos}")
        print(f"Saldo deuda multa   : "f"S/ {saldo_multa}")
        print(f"Saldo deuda real    : "f"S/ {saldo_deuda_real}")
        print(f"Saldo movimiento    : "f"S/ {saldo_movimiento}" )
        print("==============================================\n")

        # =========================================================
        # VALIDAR CONSISTENCIA
        # =========================================================

        #if saldo_movimiento != saldo_deuda_real:

        #    raise Exception(
        #        "Inconsistencia financiera: el saldo del "
        #        "movimiento no coincide con el saldo consolidado "
        #        "de la acción. "
        #        f"Movimiento: S/ {saldo_movimiento} | "
        #        f"Préstamos: S/ {saldo_prestamos} | "
        #        f"Multa: S/ {saldo_multa} | "
        #        f"Total deuda: S/ {saldo_deuda_real}"
        #    )

        # =====================================================
        # 9. CONFIRMAR
        # =====================================================

        db.commit()

        # =====================================================
        # 10. RESPUESTA
        # =====================================================

        return jsonify({

            "ok": True,

            "mensaje": ("Movimiento actualizado correctamente."),
            "id": movimiento.id,
            "accion_id": movimiento.accion_id,
            "aporte": float(movimiento.aporte or 0 ),
            "cuota_pagada": float(movimiento.cuota_pagada or 0),
            "multa": float(movimiento.multa or 0),
            "sobre": float(movimiento.sobre or 0),
            "interes": float(movimiento.interes or 0),
            "amortizacion": float(movimiento.amortizacion or 0),
            "saldo_prestamo": float(movimiento.saldo_prestamo or 0),
            "saldo_prestamos": float(saldo_prestamos),
            "reconstruccion": {

                "prestamos_actualizados": (reconstruccion["prestamos_actualizados"]),
                "prestamos_cancelados": (reconstruccion["prestamos_cancelados"])
            }
        })

    except Exception as e:

        db.rollback()

        return jsonify({
            "ok": False,
            "mensaje": str(e)
        }), 400

    finally:

        db.close()


# ============================================================
# Calcula valores para pagar todo el prestamo/multa de periodo
# ============================================================
@movimientos_bp.route(
    "/editar_movimiento/<int:id>/pagar_toda_deuda",
    methods=["GET"]
)
@login_required
def pagar_toda_deuda(id):

    db = SessionLocal()

    try:

        movimiento = (
            db.query(Movimiento)
            .filter(Movimiento.id == id)
            .first()
        )

        if not movimiento:
            return jsonify({
                "ok": False,
                "mensaje": "Movimiento no encontrado."
            }), 404

        # =========================================================
        # APORTE ACTUAL
        # =========================================================

        aporte = Decimal(
            str(movimiento.aporte or 0)
        ).quantize(
            Decimal("0.01")
        )

        # =========================================================
        # SALDO DE APERTURA
        # =========================================================

        saldo_apertura = (
            PrestamoService
            .obtener_saldo_apertura_accion(
                db=db,
                accion_id=movimiento.accion_id,
                periodo_id=movimiento.periodo_id
            )
        )

        saldo_apertura = Decimal(
            str(saldo_apertura or 0)
        ).quantize(
            Decimal("0.01")
        )

        # =========================================================
        # MULTA ANTERIOR
        # =========================================================

        multa_anterior = (
            MovimientoService
            .obtener_multa_periodo_anterior_accion(
                db=db,
                accion_id=movimiento.accion_id,
                periodo_id=movimiento.periodo_id
            )
        )

        multa_anterior = Decimal(
            str(multa_anterior or 0)
        ).quantize(
            Decimal("0.01")
        )

        # =========================================================
        # DEUDA
        # =========================================================

        deuda_total = (
            saldo_apertura + multa_anterior
        ).quantize(
            Decimal("0.01")
        )

        # =========================================================
        # CALCULAR INTERÉS
        #
        # Primero usamos una cuota provisional.
        # El interés no depende de la cuota pagada.
        # =========================================================

        cuota_provisional = (
            aporte + deuda_total
        ).quantize(
            Decimal("0.01")
        )

        resultado_interes = (
            MovimientoService
            .calcular_movimiento_accion(
                db=db,
                accion_id=movimiento.accion_id,
                periodo_id=movimiento.periodo_id,
                aporte=aporte,
                cuota_pagada=cuota_provisional,
                multa_periodo_anterior_override=multa_anterior,
                saldo_apertura_override=saldo_apertura
            )
        )

        interes = Decimal(
            str(resultado_interes["interes"] or 0)
        ).quantize(
            Decimal("0.01")
        )

        # =========================================================
        # CUOTA EXACTA PARA DEJAR TODO EN CERO
        #
        # cuota = aporte + interés + deuda
        # =========================================================

        cuota_pagar = (
            aporte
            + interes
            + deuda_total
        ).quantize(
            Decimal("0.01")
        )

        # =========================================================
        # RECALCULAR CON LA CUOTA EXACTA
        # =========================================================

        resultado_final = (
            MovimientoService
            .calcular_movimiento_accion(
                db=db,
                accion_id=movimiento.accion_id,
                periodo_id=movimiento.periodo_id,
                aporte=aporte,
                cuota_pagada=cuota_pagar,
                multa_periodo_anterior_override=multa_anterior,
                saldo_apertura_override=saldo_apertura
            )
        )

        amortizacion = Decimal(
            str(resultado_final["amortizacion"] or 0)
        ).quantize(
            Decimal("0.01")
        )

        saldo_nuevo = Decimal(
            str(resultado_final["saldo_prestamo"] or 0)
        ).quantize(
            Decimal("0.01")
        )

        return jsonify({
            "ok": True,
            "resultado": {
                "aporte": str(aporte),
                "saldo_apertura": str(saldo_apertura),
                "multa_anterior": str(multa_anterior),
                "deuda_total": str(deuda_total),
                "interes": str(interes),
                "cuota_pagar": str(cuota_pagar),
                "amortizacion": str(amortizacion),
                "saldo_nuevo": str(saldo_nuevo)
            }
        })

    except Exception as e:

        db.rollback()

        return jsonify({
            "ok": False,
            "mensaje": str(e)
        }), 500

    finally:
        db.close()

@movimientos_bp.route(
    "/editar_movimiento/<int:id>/calcular",
    methods=["POST"]
)
@login_required
def calcular_edicion_movimiento(id):

    db = SessionLocal()

    try:

        movimiento = (
            db.query(Movimiento)
            .filter(Movimiento.id == id)
            .first()
        )

        if not movimiento:
            return jsonify({
                "ok": False,
                "mensaje": "Movimiento no encontrado."
            }), 404

        # =========================================================
        # DATOS RECIBIDOS
        # =========================================================

        def decimal_form(nombre, defecto="0"):
            valor = request.form.get(nombre, defecto)

            if valor is None or str(valor).strip() == "":
                valor = defecto

            return Decimal(
                str(valor)
            ).quantize(
                Decimal("0.01")
            )

        aporte = decimal_form("aporte")
        cuota_pagada = decimal_form("cuota_pagada")
        multa_actual = decimal_form("multa")
        sobre = decimal_form("sobre")

        # =========================================================
        # MULTA DEL PERÍODO ANTERIOR
        # =========================================================

        multa_anterior = (
            MovimientoService
            .obtener_multa_periodo_anterior_accion(
                db=db,
                accion_id=movimiento.accion_id,
                periodo_id=movimiento.periodo_id
            )
        )

        multa_anterior = Decimal(str(multa_anterior or 0)).quantize(Decimal("0.01"))

        # =========================================================
        # SALDO DE APERTURA
        # =========================================================

        saldo_apertura = (
            PrestamoService
            .obtener_saldo_apertura_accion(
                db=db,
                accion_id=movimiento.accion_id,
                periodo_id=movimiento.periodo_id
            )
        )

        saldo_apertura = Decimal(str(saldo_apertura or 0)).quantize(Decimal("0.01"))

        # =========================================================
        # DEUDA REAL
        # =========================================================

        deuda_total = (
            saldo_apertura + multa_anterior
        ).quantize(
            Decimal("0.01")
        )

        # =========================================================
        # CALCULAR INTERÉS
        #
        # El interés considera:
        # saldo de apertura + multa anterior
        # =========================================================

        resultado = (
            MovimientoService
            .calcular_movimiento_accion(
                db=db,
                accion_id=movimiento.accion_id,
                periodo_id=movimiento.periodo_id,
                aporte=aporte,
                cuota_pagada=cuota_pagada,
                multa_periodo_anterior_override=multa_anterior,
                saldo_apertura_override=saldo_apertura
            )
        )

        interes = Decimal(str(resultado["interes"] or 0)).quantize(Decimal("0.01") )
        amortizacion = Decimal(str(resultado["amortizacion"] or 0)).quantize(Decimal("0.01"))
        saldo_nuevo = Decimal(str(resultado["saldo_prestamo"] or 0)).quantize(Decimal("0.01"))

        return jsonify({
            "ok": True,

            "resultado": {
                "aporte": str(aporte),
                "cuota_pagada": str(cuota_pagada),
                "interes": str(interes),
                "amortizacion": str(amortizacion),
                "saldo_apertura": str(saldo_apertura),
                "multa_anterior": str(multa_anterior),
                "deuda_total": str(deuda_total),
                "saldo_nuevo": str(saldo_nuevo),
                "multa_actual": str(multa_actual),
                "sobre": str(sobre)
            }
        })

    except Exception as e:

        db.rollback()

        return jsonify({
            "ok": False,
            "mensaje": str(e)
        }), 500

    finally:
        db.close()


# =======================================
# ELIMINAR MOVIMIENTO
# =======================================
@movimientos_bp.route(
    "/eliminar_movimiento/<int:id>",
    methods=["DELETE"]
)
@login_required
def eliminar_movimiento(id):

    db = SessionLocal()

    try:

        movimiento = (
            db.query(Movimiento)
            .filter(
                Movimiento.id == id
            )
            .first()
        )

        if not movimiento:

            return jsonify({
                "ok": False,
                "mensaje": "Movimiento no encontrado."
            }), 404

        # ======================================================
        # VALIDAR PERÍODO
        # ======================================================

        periodo = (
            db.query(Periodo)
            .filter(
                Periodo.id == movimiento.periodo_id
            )
            .first()
        )

        if periodo and periodo.cerrado:

            return jsonify({
                "ok": False,
                "mensaje": (
                    "No se puede eliminar un movimiento "
                    "de un período cerrado."
                )
            }), 400

        accion_id = movimiento.accion_id
        prestamo_id = movimiento.prestamo_id
        periodo_id = movimiento.periodo_id

        # ======================================================
        # SI TIENE PRÉSTAMO
        # ======================================================

        prestamo = None

        if prestamo_id:

            prestamo = (
                db.query(Prestamo)
                .filter(
                    Prestamo.id == prestamo_id
                )
                .first()
            )

            if not prestamo:

                raise Exception(
                    "El préstamo asociado al movimiento "
                    "no existe."
                )

        # ======================================================
        # ELIMINAR MOVIMIENTO
        # ======================================================

        db.delete(movimiento)
        db.flush()

        # ======================================================
        # RESTAURAR SALDO DEL PRÉSTAMO
        #
        # IMPORTANTE:
        # NO TOCAR PERÍODOS CERRADOS.
        # ======================================================

        if prestamo:

            saldo_apertura = (
                PrestamoService.obtener_saldo_apertura_periodo(
                    db,
                    prestamo,
                    periodo_id
                )
            )

            prestamo.saldo_actual = saldo_apertura

            if saldo_apertura > 0:

                prestamo.estado = "ACTIVO"

            else:

                prestamo.saldo_actual = Decimal("0.00")
                prestamo.estado = "CANCELADO"

        db.commit()

        return jsonify({
            "ok": True,
            "mensaje": (
                "Movimiento eliminado correctamente. "
                "El saldo del préstamo fue restaurado "
                "al saldo de apertura del período."
            ),
            "accion_id": accion_id,
            "prestamo_id": prestamo_id
        })

    except Exception as e:

        db.rollback()

        return jsonify({
            "ok": False,
            "mensaje": str(e)
        }), 400

    finally:
        db.close()

# Eliminar Prestamo, casos excepcionales:

@movimientos_bp.route(
    "/eliminar_prestamo/<int:id>",
    methods=["DELETE"]
)
@login_required
def eliminar_prestamo(id):

    db = SessionLocal()

    try:

        # =====================================================
        # BUSCAR PRESTAMO
        # =====================================================

        prestamo = (
            db.query(Prestamo)
            .filter(
                Prestamo.id == id
            )
            .first()
        )

        if not prestamo:

            return jsonify({
                "ok": False,
                "mensaje": "Préstamo no encontrado."
            }), 404

        # No permitir eliminar físicamente un préstamo si tiene movimientos:
        movimientos = (
            db.query(Movimiento)
            .filter(
                Movimiento.prestamo_id == prestamo.id
            )
            .count()
        )

        if movimientos > 0:

            return jsonify({
                "ok": False,
                "mensaje": (
                    "No se puede eliminar físicamente el préstamo "
                    "porque tiene movimientos registrados. "
                    "Debe mantenerse para conservar el historial."
                )
            }), 400


        # =====================================================
        # VALIDAR PERÍODO
        # =====================================================

        periodo = (
            db.query(Periodo)
            .filter(
                Periodo.id == prestamo.periodo_id
            )
            .first()
        )

        if periodo and periodo.cerrado:

            return jsonify({
                "ok": False,
                "mensaje": (
                    "No se puede eliminar un prestamo "
                    "de un período cerrado."
                )
            }), 400

        # =====================================================
        # GUARDAR DATOS ANTES DE ELIMINAR
        # =====================================================

        accion_id = prestamo.accion_id
        prestamo_id = prestamo.id

        # =====================================================
        # ELIMINAR PRESTAMO
        # =====================================================

        db.delete(prestamo)

        # IMPORTANTE:
        #
        # flush() hace efectiva la eliminación dentro de la
        # transacción, pero todavía NO hace commit.
        #
        db.flush()

        # =====================================================
        # CONFIRMAR
        # =====================================================

        db.commit()

        # =====================================================
        # RESPUESTA
        # =====================================================
        return jsonify({

            "ok": True,
            "mensaje": "Préstamo recalculado correctamente.",
            "accion_id": accion_id,
            "prestamo_id": prestamo_id
        })

    except Exception as e:

        db.rollback()

        return jsonify({

            "ok": False,
            "mensaje": str(e)

        }), 400


    finally:

        db.close()

#








