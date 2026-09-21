from flask import Blueprint
from flask import render_template
from flask import request
from flask import redirect
from flask import url_for
from flask import flash
from datetime import date

from flask_login import login_required

from sqlalchemy.orm import joinedload

from database.connection import SessionLocal

from models.solicitud_prestamo import SolicitudPrestamo
from models.periodo import Periodo
from models.socio import Socio
from models.accion import Accion
from services.prestamo_service import PrestamoService


solicitudes_bp = Blueprint(
    "solicitudes",
    __name__,
    url_prefix="/solicitudes"
)
@solicitudes_bp.route("/")
@login_required
def index():

    db = SessionLocal()

    try:
        periodo = (
            db.query(Periodo)
            .filter(Periodo.cerrado==False)# Vigente
            .first()
        )

        solicitudes = (

            db.query(SolicitudPrestamo)

            .options(

                joinedload(SolicitudPrestamo.socio),
                joinedload(SolicitudPrestamo.accion),
                joinedload(SolicitudPrestamo.periodo)

            )
            .filter(SolicitudPrestamo.periodo_id==periodo.id)

            .order_by(
                SolicitudPrestamo.fecha_solicitud.desc()
            )

            .all()

        )



        return render_template(

            "solicitudes/index.html",
            solicitudes=solicitudes,
            periodo=periodo

        )

    finally:

        db.close()


@solicitudes_bp.route(
    "/nuevo",
    methods=["GET","POST"]
)
@login_required
def nuevo():

    db = SessionLocal()

    try:

        if request.method=="POST":
            socio_id = int(request.form["socio_id"])
            accion_id = int(request.form["accion_id"])
            monto_solicitado = float(request.form["monto"])

            socio = db.query(Socio).get(socio_id)

            accion = db.query(Accion).get(accion_id)

            score = PrestamoService.calcular_score(
                db,
                socio,
                accion,
                monto_solicitado
            )

            solicitud = SolicitudPrestamo(

                periodo_id=request.form["periodo_id"],
                socio_id=socio_id,
                accion_id=accion_id,
                monto_solicitado=monto_solicitado,
                prioridad=1,
                score=score,
                estado="PENDIENTE",
                fecha_solicitud=date.today()

            )

            # 2. VALIDAR DUPLICIDAD EN LA RUTA
            existe_solicitud = db.query(SolicitudPrestamo).filter(
                SolicitudPrestamo.socio_id == solicitud.socio_id,
                SolicitudPrestamo.periodo_id == solicitud.periodo_id,
                SolicitudPrestamo.accion_id == solicitud.accion_id
                
            ).first()

            if existe_solicitud:
                flash("Error: El socio ya tiene una solicitud registrada para esta acción en este período.", "danger")
                return redirect(request.referrer or url_for('solicitudes.index'))

            db.add(solicitud)
            db.commit()

            flash(

                "Solicitud registrada.",
                "success"

            )

            return redirect(

                url_for("solicitudes.index")
            )


        periodos = (
            db.query(Periodo)
            .filter(
                Periodo.cerrado==False
            )
            .all()

        )

        socios = (

            db.query(Socio)
            .filter(
                Socio.estado==True

            )
            .order_by(Socio.nombres)
            .all()

        )

        return render_template(

            "solicitudes/nuevo.html",
            periodos=periodos,
            socios=socios

        )

    finally:

        db.close()

# AJAX
@solicitudes_bp.route("/acciones/<int:socio_id>")
@login_required
def acciones(socio_id):

    db=SessionLocal()

    try:

        acciones=(

            db.query(Accion)

            .filter(

                Accion.socio_id==socio_id,

                Accion.estado=="ACTIVO"

            )

            .order_by(Accion.numero_accion)

            .all()

        )

        return {

            "acciones":[

                {

                    "id":a.id,

                    "numero":a.numero_accion,

                    "valor":float(a.valor)

                }

                for a in acciones

            ]

        }

    finally:

        db.close()

@solicitudes_bp.route(
    "/editar/<int:id>",
    methods=["GET", "POST"]
)
@login_required
def editar(id):

    db = SessionLocal()

    try:

        solicitud = (
            db.query(SolicitudPrestamo)
            .options(
                joinedload(SolicitudPrestamo.socio),
                joinedload(SolicitudPrestamo.accion),
                joinedload(SolicitudPrestamo.periodo)
            )
            .filter(
                SolicitudPrestamo.id == id
            )
            .first()
        )

        if not solicitud:

            flash(
                "Solicitud no encontrada.",
                "danger"
            )

            return redirect(
                url_for("solicitudes.index")
            )

        if request.method == "POST":

            solicitud.periodo_id = request.form["periodo_id"]
            solicitud.socio_id = request.form["socio_id"]
            solicitud.accion_id = request.form["accion_id"]
            solicitud.monto_solicitado = request.form["monto"]

            db.commit()

            flash(
                "Solicitud actualizada correctamente.",
                "success"
            )

            return redirect(
                url_for("solicitudes.index")
            )

        periodos = (
            db.query(Periodo)
            .filter(
                Periodo.cerrado == False
            )
            .all()
        )

        socios = (
            db.query(Socio)
            .filter(
                Socio.estado == True
            )
            .order_by(Socio.nombres)
            .all()
        )

        acciones = (
            db.query(Accion)
            .filter(
                Accion.socio_id == solicitud.socio_id,
                Accion.estado == "ACTIVO"
            )
            .order_by(Accion.numero_accion)
            .all()
        )

        return render_template(
            "solicitudes/editar.html",
            solicitud=solicitud,
            socios=socios,
            acciones=acciones,
            periodos=periodos
        )

    finally:

        db.close()


# =====================================
# ELIMINAR ACCION
# =====================================
@solicitudes_bp.route("/eliminar/<int:id>", methods=["POST"])
def eliminar(id):

    db = SessionLocal()
    try:
        solicitud = db.query(SolicitudPrestamo).filter(SolicitudPrestamo.id == id).first()
        if not solicitud:
            flash("Acción no encontrada", "danger")
            return redirect(url_for("acciones.index"))

        db.delete(solicitud)
        db.commit()
        flash("Acción eliminada correctamente", "success")
        return redirect(url_for("solicitudes.index"))
    except Exception as e:
        db.rollback()
        flash(str(e), "danger")
        return redirect(url_for("solicitudes.index"))
    finally:
        db.close()

@solicitudes_bp.route(
    "/anular/<int:id>",
    methods=["POST"]
)
@login_required
def anular(id):

    db = SessionLocal()

    try:

        solicitud = (
            db.query(SolicitudPrestamo)
            .filter(
                SolicitudPrestamo.id == id
            )
            .first()
        )

        if not solicitud:

            flash(
                "Solicitud no encontrada.",
                "danger"
            )

            return redirect(
                url_for("solicitudes.index")
            )

        if solicitud.estado != "PENDIENTE":

            flash(
                "Solo pueden anularse solicitudes pendientes.",
                "warning"
            )

            return redirect(
                url_for("solicitudes.index")
            )

        solicitud.estado = "ANULADA"

        db.commit()

        flash(
            "Solicitud anulada correctamente.",
            "success"
        )

        return redirect(
            url_for("solicitudes.index")
        )

    finally:

        db.close()

