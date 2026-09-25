# routes/cajachica_routes.py

from flask import Blueprint, jsonify
from flask import render_template
from flask import request
from flask import redirect
from flask import url_for
from flask import flash

from flask_login import current_user, current_user, login_required

from sqlalchemy.orm import joinedload

from database.connection import SessionLocal

from models.configuracion import Configuracion
from models.movimiento import Movimiento
from models.periodo import Periodo
from models.socio import Socio
from models.accion import Accion
from models.caja_chica import CajaChica
from models.caja_chica import MovimientoCajaChica


cajas_bp = Blueprint(
    "cajas",
    __name__,
    url_prefix="/cajas"
)


@cajas_bp.route("/")
@login_required
def index():

    db = SessionLocal()

    try:

        periodo = (
            db.query(Periodo)
            .filter(
                Periodo.cerrado == False
            )
            .first()
        )

        if not periodo:

            flash(
                "No existe un período abierto.",
                "warning"
            )
            return redirect(
                url_for("periodos.index")
            )

        socios = (

            db.query(Socio)
            .options(
                joinedload(Socio.acciones)
            )
            .filter(
                Socio.estado == True
            )
            .order_by(
                Socio.nombres
            )
            .all()
        )

        config = db.query(
            Configuracion
        ).first()

        return render_template(
            "asistencias/index.html",
            periodo=periodo,
            socios=socios,
            config=config

        )

    finally:

        db.close()

@cajas_bp.route("/guardar", methods=["POST"])
@login_required
def guardar():

    db = SessionLocal()

    try:

        data = request.get_json()

        periodo_id = data["periodo_id"]
        cajachica = data["cajachica"]

        periodo = (
            db.query(Periodo)
            .filter(Periodo.id == periodo_id)
            .first()
        )

        if not periodo:
            raise Exception("Período no encontrado.")

        existe = (
            db.query(MovimientoCajaChica)
            .filter(
                MovimientoCajaChica.periodo_id == periodo_id
            )
            .count()
        )

        if existe:
            raise Exception(
                "El movimiento de caja chica del período ya fue registrada."
            )

        config = db.query(
            Configuracion
        ).first()

        caja_id=db.query(CajaChica.caja_id).filter(CajaChica.estado == True).scalar()

        registrados = 0
        total_multas = 0
        total_tardanzas = 0
        total_faltas = 0

        for fila in cajachica:

            socio_id = int(fila["socio_id"])
            estado = fila["estado"]
            observacion = fila["observacion"]

            acciones = (
                db.query(Accion)
                .filter(
                    Accion.socio_id == socio_id,
                    Accion.estado == "ACTIVO"
                )
                .count()
            )

            multa = 0

            if estado == "TARDANZA":

                multa = acciones * float(
                    config.multa_tardanza
                )

                total_tardanzas += 1

            elif estado == "FALTA":

                multa = acciones * float(
                    config.multa_falta
                )

                total_faltas += 1

            movimiento_caja_chica = MovimientoCajaChica(
                caja_id=caja_id
                periodo_id=periodo_id,
                acciones=acciones,
                socio_id=socio_id,
                estado=estado,
                multa=multa,
                observacion=observacion,
                usuario_id=current_user.id
            )

            db.add(movimiento_caja_chica)

           # 1. Buscamos la acción activa del socio
            accion_1 = (
                db.query(Accion)
                .filter(
                    Accion.socio_id == socio_id,
                    Accion.estado == "ACTIVO"
                )
                .first()
            )

            if multa > 0:
                # 2. BUSCAMOS si ya existe un movimiento para este socio y periodo con esa acción
                movimiento = (
                    db.query(Movimiento)
                    .filter(
                        Movimiento.periodo_id == periodo_id,
                        Movimiento.socio_id == socio_id,
                        Movimiento.accion_id == accion_1.id
                    )
                    .first()
                )

                if movimiento:
                    # 3. SI EXISTE, lo editamos (actualizamos los campos necesarios)
                    movimiento.multa = multa
                    movimiento.observacion = f"Multa por {estado.lower()} en reunión mensual (Actualizado)"
                    # Nota: No hace falta hacer db.add(), SQLAlchemy detecta los cambios automáticamente
                else:
                    # 4. SI NO EXISTE, creamos el nuevo registro
                    movimiento = Movimiento(
                        periodo_id=periodo_id,
                        socio_id=socio_id,
                        accion_id=accion_1.id,
                        aporte=0,
                        amortizacion=0,
                        interes=0,
                        multa=multa,
                        sobre=0,
                        observacion=f"Multa por {estado.lower()} en reunión mensual"
                    )
                    db.add(movimiento)

            registrados += 1
            total_multas += multa

        db.commit()

        return jsonify({

            "ok": True,
            "registrados": registrados,
            "tardanzas": total_tardanzas,
            "faltas": total_faltas,
            "multas": float(total_multas),
            "mensaje": f"Se registraron {registrados} asistencias correctamente."

        })

    except Exception as e:

        db.rollback()

        return jsonify({

            "ok": False,
            "mensaje": str(e)

        }), 400

    finally:

        db.close()