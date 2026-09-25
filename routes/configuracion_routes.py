from flask import Blueprint
from flask import render_template
from flask import request
from flask import redirect
from flask import url_for
from flask import flash

from flask_login import login_required

from database.connection import SessionLocal
from sqlalchemy.orm import joinedload

from models.periodo import Periodo
from models.configuracion import Configuracion


configuracion_bp = Blueprint(
    "configuracion",
    __name__,
    url_prefix="/configuracion"
)


@configuracion_bp.route("/")
@login_required
def index():

    db=SessionLocal()

    try:

        configuracion=db.query(
            Configuracion
        ).order_by(
            Configuracion.id
        ).all()

        periodo = (
            db.query(Periodo)
            .filter(Periodo.cerrado == False)
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
        
        return render_template(
            "configuracion/index.html",
            configuracion=configuracion,
            periodo=periodo
        )

    finally:

        db.close()



@configuracion_bp.route("/nuevo", methods=["GET", "POST"])
@login_required
def nuevo():
    db = SessionLocal()
    try:
        if request.method == "POST":
            estado_bool = request.form.get("estado") == "1"

            # VALIDACIÓN: Si la nueva configuración se marca como Activa, desactivamos las anteriores
            if estado_bool:
                db.query(Configuracion).filter(Configuracion.estado == True).update({"estado": False})

            nueva_config = Configuracion(
                aporte_minimo=float(request.form["aporte_minimo"]),
                sobre_por_accion=float(request.form["sobre_por_accion"]),
                interes_mensual=float(request.form["interes_mensual"]),
                metodo_distribucion=request.form["metodo_distribucion"],
                multa_tardanza=float(request.form["multa_tardanza"]),
                multa_falta=float(request.form["multa_falta"]),
                estado=estado_bool
            )
            
            db.add(nueva_config)
            db.commit()
            flash("Configuración creada correctamente", "success")
            return redirect(url_for("configuracion.index"))
            
        periodo = db.query(Periodo).filter(Periodo.cerrado == False).first()
        return render_template("configuracion/form.html", configuracion=None, periodo=periodo)
    except Exception as e:
        db.rollback()
        flash(f"Error al guardar: {str(e)}", "danger")
        return redirect(url_for("configuracion.index"))
    finally:
        db.close()

@configuracion_bp.route("/editar/<int:id>", methods=["GET", "POST"])
@login_required
def editar(id):
    db = SessionLocal()
    try:
        config = db.query(Configuracion).get(id)
        if not config:
            flash("No se encontró la configuración", "warning")
            return redirect(url_for("configuracion.index"))

        if request.method == "POST":
            estado_bool = request.form.get("estado") == "1"

            # VALIDACIÓN: Si esta configuración pasa a ser Activa, desactivamos todas las DEMÁS
            if estado_bool:
                db.query(Configuracion).filter(
                    Configuracion.id != id, 
                    Configuracion.estado == True
                ).update({"estado": False})

            config.aporte_minimo = float(request.form["aporte_minimo"])
            config.sobre_por_accion = float(request.form["sobre_por_accion"])
            config.interes_mensual = float(request.form["interes_mensual"])
            config.metodo_distribucion = request.form["metodo_distribucion"]
            config.multa_tardanza = float(request.form["multa_tardanza"])
            config.multa_falta = float(request.form["multa_falta"])
            config.estado = estado_bool

            db.commit()
            flash("Configuración actualizada correctamente", "success")
            return redirect(url_for("configuracion.index"))

        periodo = db.query(Periodo).filter(Periodo.cerrado == False).first()
        return render_template("configuracion/form.html", configuracion=config, periodo=periodo)
    except Exception as e:
        db.rollback()
        flash(f"Error al editar: {str(e)}", "danger")
        return redirect(url_for("configuracion.index"))
    finally:
        db.close()

@configuracion_bp.route("/cambiar_estado/<int:id>", methods=["POST"])
@login_required
def estado(id):
    db = SessionLocal()
    try:
        config = db.query(Configuracion).get(id)
        if not config:
            flash("No se encontró la configuración", "warning")
            return redirect(url_for("configuracion.index"))

        # Invertimos el estado actual
        nuevo_estado = not config.estado

        # VALIDACIÓN: Si se va a ACTIVAR, desactivamos todas las demás primero
        if nuevo_estado:
            db.query(Configuracion).filter(
                Configuracion.id != id, 
                Configuracion.estado == True
            ).update({"estado": False})

        config.estado = nuevo_estado
        db.commit()
        flash("Estado actualizado correctamente", "success")
    except Exception as e:
        db.rollback()
        flash(f"Error al cambiar estado: {str(e)}", "danger")
    finally:
        db.close()
    return redirect(url_for("configuracion.index"))

@configuracion_bp.route("/eliminar/<int:id>", methods=["POST"])
@login_required
def eliminar(id):
    db = SessionLocal()
    try:
        config = db.query(Configuracion).get(id)
        if not config:
            flash("No se encontró la configuración", "warning")
            return redirect(url_for("configuracion.index"))

        db.delete(config)
        db.commit()
        flash("Configuración eliminada correctamente", "success")
    except Exception as e:
        db.rollback()
        flash(f"Error al eliminar: {str(e)}", "danger")
    finally:
        db.close()
    return redirect(url_for("configuracion.index"))

@configuracion_bp.route("/detalle/<int:id>")
@login_required
def detalle(id):

    db = SessionLocal()

    try:

        configuracion = (
            db.query(Configuracion)
            .first()
        )

        if not configuracion:

            flash(
                "Configuracion no encontrado",
                "danger"
            )

            return redirect(
                url_for("configuracion.index")
            )
 

        return render_template(

            "configuracion/detalle.html",
            configuracion=configuracion

        )

    finally:

        db.close()