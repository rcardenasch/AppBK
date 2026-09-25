from decimal import Decimal
from flask import (Blueprint,render_template,request,redirect, session,url_for,flash,jsonify
)
from models.configuracion import Configuracion
from services.adquisicion_accion_service import AdquisicionAccionService
from services.multa_service import MultaService


from flask_login import current_user, login_required

from database.connection import SessionLocal
from sqlalchemy.orm import joinedload

from models.periodo import Periodo
from models.socio import Socio
from models.accion import Accion
from models.prestamo import Prestamo
from models.movimiento import Movimiento


socios_bp = Blueprint(
    "socios",
    __name__,
    url_prefix="/socios"
)


@socios_bp.route("/")
@login_required
def index():

    db=SessionLocal()

    try:

        socios=db.query(
            Socio
        ).order_by(
            Socio.nombres
        ).all()

        return render_template(
            "socios/index.html",
            socios=socios
        )

    finally:

        db.close()

@socios_bp.route(
"/nuevo",
methods=["GET","POST"]
)
@login_required
def nuevo():

    if request.method=="POST":

        db=SessionLocal()

        try:

            socio=Socio(

                nombres=request.form["nombres"],
                documento=request.form["documento"],
                telefono=request.form["telefono"]

            )

            db.add(socio)
            db.commit()

            flash(
                "Socio registrado",
                "success"
            )

            return redirect(
                url_for(
                    "socios.index"
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
        "socios/form.html"
    )

@socios_bp.route(
"/editar/<int:id>",
methods=["GET","POST"]
)
@login_required
def editar(id):

    db=SessionLocal()

    try:

        socio=db.query(
            Socio
        ).get(id)

        if request.method=="POST":

            socio.nombres=request.form["nombres"]
            socio.documento=request.form["documento"]
            socio.telefono=request.form["telefono"]

            db.commit()

            flash(
                "Socio actualizado",
                "success"
            )
            return redirect(
                url_for(
                    "socios.index"
                )
            )

        return render_template(
            "socios/form.html",
            socio=socio
        )

    finally:

        db.close()


@socios_bp.route(
"/estado/<int:id>",
methods=["POST"]
)
@login_required
def estado(id):

    db=SessionLocal()

    try:
        socio=db.query(
            Socio
        ).get(id)

        socio.estado=not socio.estado

        db.commit()

        flash(
            "Estado actualizado",
            "success"
        )

        return redirect(
            url_for(
                "socios.index"
            )
        )

    finally:

        db.close()

@socios_bp.route("/detalle/<int:id>")
@login_required
def detalle(id):
    
    db = SessionLocal()

    periodo = (
            db.query(Periodo)
            .filter(Periodo.cerrado == False)
            .first()
        )

    try:

        socio = (
            db.query(Socio)
            .options(
                joinedload(Socio.acciones)
                
                    .joinedload(Accion.prestamos)
                    .joinedload(Prestamo.movimientos)
            )
            .filter(Socio.id == id)
            .first()
        )

        if not socio:

            flash(
                "Socio no encontrado",
                "danger"
            )

            return redirect(
                url_for("socios.index")
            )

        prestamos_activos = [

            prestamo
            for accion in socio.acciones
            for prestamo in accion.prestamos
            if prestamo.estado == "ACTIVO"

        ]

        saldo_prestamos = sum(

            float(prestamo.saldo_actual)

            for prestamo in prestamos_activos

        )
        # 2. NUEVA SOLUCIÓN DIRECTA: Sumar todas las cuotas de sus movimientos
        cuota_pagada = sum(
            float(movimiento.cuota_pagada)
            for movimiento in socio.movimientos  # <-- Uso directo de tu relación
            if movimiento.periodo_id==periodo.id
        )
        cuota_sobre = sum(
            float(movimiento.sobre)
            for movimiento in socio.movimientos  # <-- Uso directo de tu relación
            if movimiento.periodo_id==periodo.id
        )

        socios = (
            db.query(Socio)
            .filter(Socio.estado == True)
            .order_by(Socio.nombres)
            .all()

        )


        accion_especifica = next((a for a in socio.acciones if a.socio_id == id), None)
        valor_accion = accion_especifica.valor if accion_especifica else 0

        return render_template(

            "socios/detalle.html",
            socio=socio,
            socios=socios,
            valor_accion=valor_accion,
            prestamos_activos=prestamos_activos,
            saldo_prestamos=saldo_prestamos,
            cancelar=cuota_pagada+cuota_sobre,
            cuota_sobre=cuota_sobre,
            movimientos=socio.movimientos,
            periodo=periodo 

        )

    finally:

        db.close()

# ==============================================
# Ruta de previsualización Adquirir Nueva accion
# ==============================================
@socios_bp.route("/adquirir-accion/<int:socio_id>",methods=["GET"])
@login_required
def adquirir_accion(socio_id):

    db = SessionLocal()
    socio = (
        db.query(Socio)
        .filter(
            Socio.id == socio_id
        )
        .first()
    )

    if not socio:
        flash(
            "No se encontró el socio.",
            "danger"
        )

        return redirect(
            url_for("socios.index")
        )

    periodo = (
        db.query(Periodo)
        .filter(
            Periodo.cerrado == False
        )
        .order_by(
            Periodo.anio.desc(),
            Periodo.mes.desc()
        )
        .first()
    )

    if not periodo:
        flash(
            "No existe un período abierto.",
            "warning"
        )

        return redirect(
            url_for(
                "socios.detalle",
                id=socio.id
            )
        )

    resultado_proceso_nueva_accion = session.pop(
            "resultado_proceso_nueva_accion",
            None
        )

    return render_template(
        "socios/adquirir_accion.html",
        socio=socio,
        periodo=periodo,
        resultado_proceso_nueva_accion=resultado_proceso_nueva_accion
    )

@socios_bp.route("/adquirir-accion/calcular/<int:socio_id>", methods=["POST"])
@login_required
def calcular_adquisicion_accion(socio_id):
    db = SessionLocal()
    try:

        valor_accion = Decimal(
            request.form.get(
                "valor_accion",
                "0"
            )
        )

        # Se realiza porque no hay una relacion de configuracion y periodo para extaer el aporte aplicado en el periodo
        aporte_enero = Decimal(
            request.form.get(
                "aporte_enero",
                "150"
            )
        )

        aporte_mensual = Decimal(
            request.form.get(
                "aporte_mensual",
                "170"
            )
        )

        periodo_id = int(
            request.form.get(
                "periodo_id"
            )
        )

        resultado = (
            AdquisicionAccionService
            .simular_adquisicion(
                db=db,
                valor_accion=valor_accion,
                periodo_id=periodo_id,
                aporte_enero=aporte_enero,
                aporte_mensual=aporte_mensual
            )
        )

        return jsonify({
            "ok": True,
            "valor_accion":str(resultado["valor_accion"]),
            "aportes": str(resultado["aportes"]),
            "intereses":str(resultado["intereses"]),
            "cuota_pagar": str(resultado["cuota_pagar"]),
            "detalle": [
                {
                    "periodo": f'{x["anio"]}-{x["mes"]:02d}',
                    "saldo_anterior":str(x["saldo_anterior"]),
                    "aporte":str(x["aporte"]),
                    "interes":str(x["interes"]),
                    "saldo":str(x["saldo"])
                }
                for x in resultado["detalle"]
            ]
        })

    except Exception as e:

        db.rollback()

        return jsonify({
            "ok": False,
            "mensaje": str(e)
        }), 400



# ==========================================================
# CONFIRMAR ADQUISICIÓN
# ==========================================================
@socios_bp.route(
    "/<int:socio_id>/adquirir-accion",
    methods=["POST"]
)
@login_required
def guardar_adquisicion_accion(socio_id):

    db = SessionLocal()

    try:

        valor = Decimal(
            request.form.get(
                "valor_accion",
                "0"
            )
        )

        periodo_id = int(
            request.form.get(
                "periodo_id"
            )
        )

        resultado = (
            AdquisicionAccionService.registrar_adquisicion(
                db=db,
                socio_id=socio_id,
                periodo_id=periodo_id,
                valor_accion=valor,
                usuario_id=current_user.id
            )
        )

        db.commit()
        print("Terminé, Hice commit()")


        # =====================================================
        # GUARDAR RESULTADO PARA MOSTRARLO DESPUÉS, en vez del Flask
        # =====================================================

        session[
            "resultado_proceso_nueva_accion"
        ] = {
            "numero_accion": resultado["numero_accion"],
            "valor_accion": resultado["valor_accion"],
            "intereses": resultado["intereses"],
            "costo_nueva_accion": resultado["costo_nueva_accion"],
            "cuota_calculada": resultado["cuota_calculada"],
            "aportes_historicos": resultado["aportes_historicos"],
            "cuota_final": resultado["total"]
        }

        flash(
            "La nueva acción fue adquirida "
            "y el préstamo quedó cancelado "
            "en el mismo período.",
            "success"
        )

        return redirect(
            url_for(
                "socios.detalle",
                id=socio_id
            )
        )

    except Exception as e:

        db.rollback()

        flash(
            f"No se pudo registrar la adquisición: {e}",
            "danger"
        )

        return redirect(
            url_for(
                "socios.adquirir_accion",
                socio_id=socio_id
            )
        )

    finally:
        db.close()


# ==============================================
# Listado de multas del perido previsualización
# ==============================================
@socios_bp.route(
    "/socios/multas",
    methods=["GET"]
)
@login_required
def multas_periodo():
    db = SessionLocal()
    try:

        periodo = (
            MultaService
            .obtener_periodo_vigente(
                db
            )
        )

        if not periodo:

            flash(
                "No existe un período vigente abierto.",
                "warning"
            )

            return redirect(
                url_for(
                    "socios.index"
                )
            )

        config = (db.query(Configuracion)
            .filter(Configuracion.estado==True)
            .first()
        )
        if not config:
            flash("Se debe configurar parametros","warning")

            return redirect(
                url_for(
                    "configuracion.index"
                )
            )

        movimientos = (
            db.query(Movimiento)
            .join(
                Socio,
                Socio.id == Movimiento.socio_id
            )
            .filter(
                Movimiento.periodo_id == periodo.id
            )
            .order_by(
                Socio.nombres.asc(),
                Movimiento.id.asc()
            )
            .all()
        )

        return render_template(
            "socios/multas_periodo.html",
            periodo=periodo,
            movimientos=movimientos,
            configuracion=config
        )

    except Exception as e:

        flash(
            f"No se pudo cargar el registro de multas: {e}",
            "danger"
        )

        return redirect(
            url_for(
                "socios.index"
            )
        )

# ==============================================
# Ruta que Actualiza multa y observacion
# ==============================================

@socios_bp.route(
    "/socios/movimiento/<int:movimiento_id>/multa",
    methods=["POST"]
)
@login_required
def actualizar_multa_movimiento(
    movimiento_id
):
    db=SessionLocal()
    try:

        multa = Decimal(
            request.form.get(
                "multa",
                "0"
            )
        )

        observacion = request.form.get(
            "observacion",
            ""
        )

        movimiento = (
            MultaService
            .actualizar_multa(
                db=db,
                movimiento_id=movimiento_id,
                multa=multa,
                observacion=observacion
            )
        )

        db.commit()

        flash(
            "La multa y la observación fueron actualizadas correctamente.",
            "success"
        )

    except Exception as e:

        db.rollback()

        flash(
            f"No se pudo actualizar la multa: {e}",
            "danger"
        )

    return redirect(
        url_for(
            "socios.multas_periodo"
        )
    )