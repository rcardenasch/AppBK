from flask import Blueprint
from flask import request
from flask import jsonify
from flask import Blueprint
from flask import render_template

from flask_login import login_required
from sqlalchemy.orm import joinedload
from flask import redirect
from flask import url_for
from flask import flash

from datetime import date
from decimal import Decimal

from database.connection import SessionLocal

from models.periodo import Periodo
from models.prestamo import Prestamo
from models.socio import Socio
from models.accion import Accion
from models.movimiento import Movimiento
from models.configuracion import Configuracion
from services.prestamo_service import PrestamoService


prestamos_bp = Blueprint(
    "prestamos",
    __name__,
    url_prefix="/prestamos"
)

@prestamos_bp.route("/")
@login_required
def index():

    db=SessionLocal()
    
    prestamos = (
        db.query(Prestamo)
        .options(
            joinedload(Prestamo.socio),
            joinedload(Prestamo.accion)
        )
        .order_by(
            Prestamo.fecha_prestamo.desc()
        )
        .all()
    )

    accion = db.query(Accion).filter(
        Accion.estado == "ACTIVO"
        ).all()

    db.close()

    return render_template(
        "prestamos/index.html",
        prestamos=prestamos,
        accion=accion
    )
@prestamos_bp.route(
    "/nuevo",
    methods=["GET", "POST"]
)
@login_required
def nuevo():

    db = SessionLocal()

    try:

        # NUEVO: Capturar los IDs opcionales desde la URL (?socio_id=X&accion_id=Y)
        socio_seleccionado = request.args.get("socio_id", type=int)
        accion_seleccionada = request.args.get("accion_id", type=int)

        config = (db.query(Configuracion)
            .filter(Configuracion.estado==True)
            .first()
        )

        periodo = (db.query(Periodo)
            .filter(Periodo.cerrado==False)
            .first()
        )

        if not config:

            flash(
                "Debe actualizar la configuración del sistema.",
                "danger"
            )

            return redirect(
                url_for("configuracion.index")
            )

        if request.method == "POST":

            accion_id = int(
                request.form["accion_id"]
            )

            monto = Decimal(
                request.form["monto"]
            )

            accion = (
                db.query(Accion)
                .filter(
                    Accion.id == accion_id
                )
                .first()
            )

            if not accion:
                flash(
                    "Acción no encontrada.",
                    "danger"
                )
                return redirect(
                    url_for("prestamos.nuevo")
                )
           
            saldo_anterior = Decimal(
                request.form.get("saldo_anterior", "0") or "0"
            )

            monto = Decimal(
                request.form.get("monto", "0") or "0"
            )

            tiene_anterior = (
                request.form.get("saldo_anterior") is not None
                and saldo_anterior > 0
            )

            # No permitir valores negativos
            if monto < 0:
                flash(
                    "El monto del préstamo no puede ser negativo.",
                    "danger"
                )
                return redirect(
                    url_for("prestamos.nuevo")
                )

            if saldo_anterior < 0:
                flash(
                    "El saldo anterior no puede ser negativo.",
                    "danger"
                )
                return redirect(
                    url_for("prestamos.nuevo")
                )

            # Debe existir al menos una deuda
            if monto == 0 and saldo_anterior == 0:
                flash(
                    "Debe ingresar un monto de préstamo o un saldo pendiente del período anterior.",
                    "danger"
                )
                return redirect(
                    url_for("prestamos.nuevo")
                )
            
            cuota_minima = PrestamoService.calcular_cuota_minima(
                saldo_anterior + monto
             )

            deuda_total = saldo_anterior + monto
            prestamo = Prestamo(

                socio_id=accion.socio_id,
                accion_id=accion.id,
                periodo_id=periodo.id,
                fecha_prestamo=date.today(),
                monto=monto,
                # deuda total
                saldo_actual = deuda_total,

                # SOLO el saldo heredado genera interés
                saldo_interes = saldo_anterior,
                tasa_interes=config.interes_mensual,
                cuota_minima=cuota_minima,
                estado="ACTIVO"

            )
            
            db.add(prestamo)

            db.commit()

            flash(
                "Préstamo registrado correctamente.",
                "success"
            )

            return redirect(
                url_for("prestamos.index")
            )

        # ==========================
        # GET
        # ==========================

        socios = (

            db.query(Socio)
            .filter(
                Socio.estado == True
            )
            .order_by(
                Socio.nombres
            )
            .all()

        )

        acciones = (
            db.query(Accion)
            .join(Accion.socio)
            .options(
                joinedload(Accion.socio)
            )
            .filter(
                Accion.estado == "ACTIVO"
            )
            .order_by(
                Socio.nombres,
                Accion.numero_accion
            )
            .all()
        )
        return render_template(

            "prestamos/nuevo.html",
            socios=socios,
            acciones=acciones,
            interes=config.interes_mensual,
            # NUEVO: Enviamos las variables a la plantilla HTML
            socio_seleccionado=socio_seleccionado,
            accion_seleccionada=accion_seleccionada

        )

    finally:

        db.close()

@prestamos_bp.route("/detalle/<int:id>")
@login_required
def detalle(id):

    db = SessionLocal()

    try:

        prestamo = (
            db.query(Prestamo)
            .options(

                joinedload(Prestamo.socio),

                joinedload(Prestamo.accion),

                joinedload(Prestamo.movimientos)
                    .joinedload(Movimiento.periodo),

                joinedload(Prestamo.movimientos)
                    .joinedload(Movimiento.socio),

                joinedload(Prestamo.movimientos)
                    .joinedload(Movimiento.accion),

            )
            .filter(
                Prestamo.id == id
            )
            .first()
        )

        if not prestamo:

            flash(
                "Préstamo no encontrado",
                "danger"
            )

            return redirect(
                url_for("prestamos.index")
            )

        total_pagado = sum(
            m.amortizacion
            for m in prestamo.movimientos
        )

        total_interes = sum(
            m.interes
            for m in prestamo.movimientos
        )

        total_aporte = sum(
            m.aporte
            for m in prestamo.movimientos
        )
        for p in prestamo:
            p.tiene_movimientos = len(p.movimientos) > 0

        return render_template(

            "prestamos/detalle.html",
            prestamo=prestamo,
            total_pagado=total_pagado,
            total_interes=total_interes,
            total_aporte=total_aporte,
            tiene_movimientos =prestamo.movimientos

        )

    finally:

        db.close()

@prestamos_bp.route(
    "/editar/<int:id>",
    methods=["GET", "POST"]
)
@login_required
def editar(id):

    db = SessionLocal()

    try:

        prestamo = (
            db.query(Prestamo)
            .options(
                joinedload(Prestamo.movimientos),
                joinedload(Prestamo.accion)
                    .joinedload(Accion.socio)
            )
            .filter(
                Prestamo.id == id
            )
            .first()
        )

        if not prestamo:

            flash(
                "Préstamo no encontrado.",
                "danger"
            )

            return redirect(
                url_for("prestamos.index")
            )

        # No permitir editar si ya tiene movimientos
        if prestamo.movimientos:

            flash(
                "No se puede editar un préstamo que ya tiene movimientos registrados.",
                "warning"
            )

            return redirect(
                url_for(
                    "prestamos.detalle",
                    id=prestamo.id
                )
            )

        if request.method == "POST":

            accion_id = int(
                request.form["accion_id"]
            )

            accion = db.query(
                Accion
            ).get(
                accion_id
            )

            if not accion:

                flash(
                    "Acción no encontrada.",
                    "danger"
                )

                return redirect(
                    url_for(
                        "prestamos.editar",
                        id=id
                    )
                )

            monto = Decimal(
                request.form["monto"]
            )

            if monto <= 0:

                flash(
                    "Monto inválido.",
                    "danger"
                )

                return redirect(
                    url_for(
                        "prestamos.editar",
                        id=id
                    )
                )

            prestamo.accion_id = accion.id
            prestamo.socio_id = accion.socio_id
            prestamo.monto = monto
            prestamo.saldo_actual = monto
            prestamo.saldo_interes = Decimal("0.00")

            db.commit()

            flash(
                "Préstamo actualizado correctamente.",
                "success"
            )

            return redirect(
                url_for(
                    "prestamos.index"
                )
            )

        acciones = (
            db.query(Accion)
            .options(
                joinedload(Accion.socio)
            )
            .filter(
                Accion.estado == "ACTIVO"
            )
            .order_by(
                Accion.numero_accion
            )
            .all()
        )

        return render_template(
            "prestamos/editar.html",
            prestamo=prestamo,
            acciones=acciones
        )

    except Exception as e:

        db.rollback()

        flash(
            str(e),
            "danger"
        )

        return redirect(
            url_for("prestamos.index")
        )

    finally:

        db.close()

@prestamos_bp.route(
    "/eliminar/<int:id>",
    methods=["POST"]
)
@login_required
def eliminar(id):

    db = SessionLocal()

    try:

        prestamo = (
            db.query(Prestamo)
            .options(
                joinedload(Prestamo.movimientos)
            )
            .filter(
                Prestamo.id == id
            )
            .first()
        )

        if not prestamo:

            flash(
                "Préstamo no encontrado.",
                "danger"
            )

            return redirect(
                url_for("prestamos.index")
            )

        # No permitir eliminar si ya tiene movimientos

        if prestamo.movimientos:

            flash(
                "No se puede eliminar un préstamo que ya tiene movimientos.",
                "warning"
            )

            return redirect(
                url_for(
                    "prestamos.detalle",
                    id=id
                )
            )

        db.delete(prestamo)
        db.commit()

        flash(
            "Préstamo eliminado correctamente.",
            "success"
        )

    except Exception as e:

        db.rollback()

        flash(
            str(e),
            "danger"
        )

    finally:

        db.close()

    return redirect(
        url_for("prestamos.index")
    )

@prestamos_bp.route(
    "/cancelar/<int:id>",
    methods=["POST"]
)
@login_required
def cancelar(id):

    db = SessionLocal()

    try:

        prestamo = (
            db.query(Prestamo)
            .options(
                joinedload(Prestamo.movimientos)
            )
            .filter(
                Prestamo.id == id
            )
            .first()
        )

        if not prestamo:

            flash(
                "Préstamo no encontrado.",
                "danger"
            )

            return redirect(
                url_for("prestamos.index")
            )

        if prestamo.estado != "ACTIVO":

            flash(
                "El préstamo ya no está activo.",
                "warning"
            )

            return redirect(
                url_for("prestamos.detalle", id=id)
            )

        # Si tiene saldo pendiente advertimos al usuario
        if prestamo.saldo_actual > 0:

            flash(
                "El préstamo fue cancelado administrativamente con saldo pendiente.",
                "warning"
            )

        prestamo.estado = "CANCELADO"

        db.commit()

        flash(
            "Préstamo cancelado correctamente.",
            "success"
        )

        return redirect(
            url_for("prestamos.index")
        )

    except Exception as e:

        db.rollback()

        flash(
            str(e),
            "danger"
        )

        return redirect(
            url_for("prestamos.index")
        )

    finally:

        db.close()

#AJAX
@prestamos_bp.route(
    "/acciones/<int:socio_id>"
)
@login_required
def acciones_por_socio(socio_id):

    db = SessionLocal()

    try:

        acciones = (

            db.query(Accion)

            .outerjoin(
                Prestamo,
                (Prestamo.accion_id == Accion.id)
                &
                (Prestamo.estado == "ACTIVO")
            )

            .filter(
                Accion.socio_id == socio_id,
                Accion.estado == "ACTIVO",
                Prestamo.id == None
            )

            .order_by(
                Accion.numero_accion
            )

            .all()

        )

        return jsonify([

            {

                "id":a.id,
                "numero":a.numero_accion,
                "valor":float(a.valor)

            }

            for a in acciones

        ])

    finally:

        db.close()

#AJAX
@prestamos_bp.route("/api/<int:id>")
@login_required
def api_prestamo(id):

    db = SessionLocal()

    try:

        prestamo = db.query(
            Prestamo
        ).get(id)

        if not prestamo:

            return jsonify(
                {"error":"No existe"}
            ),404

        return jsonify({

            "id": prestamo.id,
            "saldo": float(prestamo.saldo_actual),
            "saldo_interes": float(prestamo.saldo_interes),
            "monto": float(prestamo.monto),
            "interes": float(prestamo.tasa_interes),
            "cuota_minima": float(prestamo.cuota_minima)

        })

    finally:

        db.close()