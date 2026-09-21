from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required
from database.connection import SessionLocal
from sqlalchemy import desc,asc
from sqlalchemy.orm import joinedload
from models.accion import Accion
from models.socio import Socio
from models.prestamo import Prestamo
from models.movimiento import Movimiento


acciones_bp = Blueprint("acciones", __name__, url_prefix="/acciones")

# =====================================
# LISTAR ACCIONES
# =====================================
@acciones_bp.route("/")
@acciones_bp.route("/socio/<int:socio_id>") # Corregido: Ahora comparte la función index
def index(socio_id=None):
    db = SessionLocal()

    try:
        query = (
            db.query(Accion)
            .options(
                joinedload(Accion.socio),
                joinedload(Accion.prestamos)
            )

        )

        if socio_id:
            query = query.filter(
                Accion.socio_id == socio_id

            )

        acciones = (query.order_by(Accion.id.desc()).all()

        )

        for accion in acciones:
            accion.saldo_prestamos = sum(
                p.saldo_actual
                for p in accion.prestamos
                if p.estado == "ACTIVO"
            )

        socios = (
            db.query(Socio)
            .filter(Socio.estado == True)
            .order_by(Socio.nombres)
            .all()

        )

        return render_template(

            "acciones/index.html",
            acciones=acciones,
            socios=socios
        )

    finally:

        db.close()

# =====================================
# CREAR ACCION (Unificado)
# =====================================
@acciones_bp.route("/nuevo", methods=["GET", "POST"])
@acciones_bp.route("/nuevo/<int:socio_id>", methods=["GET", "POST"]) # Permite preseleccionar un socio

def nuevo(socio_id=None):
    
    db = SessionLocal()
    
    if request.method == "POST":
        try:
            numero_accion = request.form.get("numero_accion")
            
            # Validar duplicados
            existe = db.query(Accion).filter(Accion.numero_accion == numero_accion).first()
            if existe:
                flash("El número de acción ya existe", "danger")
                return redirect(url_for("acciones.nuevo"))

            accion = Accion(
                socio_id=request.form.get("socio_id"),
                numero_accion=numero_accion,
                valor=request.form.get("valor"),
                estado="ACTIVO"
            )
            db.add(accion)
            db.commit()
            flash("Acción registrada correctamente", "success")
            return redirect(url_for("acciones.index"))
        except Exception as e:
            db.rollback()
            flash(f"Error registrando acción: {str(e)}", "danger")
            return redirect(url_for("acciones.nuevo"))
        finally:
            db.close()

    # ---------------------------------------------------------
    # LOGICA PARA EL METODO GET (Pre-cargar datos y código)
    # ---------------------------------------------------------
    codigo_sugerido = ""
    
    if socio_id:
        socio = db.query(Socio).filter(Socio.id == socio_id).first()
        if socio and socio.nombres:
            # 1. Obtener la inicial en mayúscula (Ej: Romel -> R)
            inicial = socio.nombres[0].upper()
            
            # 2. Contar cuántas acciones existen en la BD que inicien con esa letra
            # Usamos LIKE 'R%' para encontrar R001, R002, etc.
            cantidad_existente = db.query(Accion).filter(
                Accion.numero_accion.like(f"{inicial}%")
            ).count()
            
            # 3. La nueva secuencia será la cantidad actual + 1
            siguiente_secuencia = cantidad_existente + 1
            
            # 4. Formatear con ceros a la izquierda (Ej: R + 001 = R001)
            codigo_sugerido = f"{inicial}{siguiente_secuencia:03d}"
     
    socios = db.query(Socio).filter(Socio.estado == True).order_by(asc(Socio.nombres)).all()


    db.close()
    return render_template("acciones/nuevo.html", 
                           socios=socios, 
                           socio_id=socio_id,
                           codigo_sugerido=codigo_sugerido
                           )

# =====================================
# EDICION Y ACTUALIZACION (Unificado)
# =====================================
@acciones_bp.route("/editar/<int:id>", methods=["GET", "POST"])
def editar(id):
    db = SessionLocal()

    try:
        accion = (
            db.query(Accion)
            .options(
                joinedload(Accion.socio),
                joinedload(Accion.prestamos)
                    .joinedload(Prestamo.movimientos)
            )
            .filter(
                Accion.id == id
            )
            .first()
        )
        if not accion:
            flash("Acción no encontrada", "danger")
            return redirect(url_for("acciones.index"))

        # PROCESAR ACTUALIZACION (POST)
        if request.method == "POST":
            numero_accion = request.form.get("numero_accion")
            
            # Validar duplicado excluyendo la acción actual
            existe = db.query(Accion).filter(Accion.numero_accion == numero_accion, Accion.id != id).first()
            if existe:
                flash("Número de acción ya existe", "danger")
                return redirect(url_for("acciones.editar", id=id))

            accion.socio_id = request.form.get("socio_id")
            accion.numero_accion = numero_accion
            accion.valor = request.form.get("valor")
            accion.estado = request.form.get("estado")
            
            db.commit()
            flash("Acción actualizada correctamente", "success")
            return redirect(url_for("acciones.index"))

        # MOSTRAR FORMULARIO (GET)
        socios = db.query(Socio).filter(Socio.estado == True).all()


        return render_template(
            "acciones/editar.html",
            accion=accion,
            socios=socios
            )

    except Exception as e:
        db.rollback()
        flash(f"Error al procesar: {str(e)}", "danger")
        return redirect(url_for("acciones.index"))
    finally:
        db.close()

# =====================================
# ELIMINAR ACCION
# =====================================
@acciones_bp.route("/eliminar/<int:id>", methods=["POST"])
def eliminar(id):

    db = SessionLocal()
    try:
        accion = db.query(Accion).filter(Accion.id == id).first()
        if not accion:
            flash("Acción no encontrada", "danger")
            return redirect(url_for("acciones.index"))

        if accion.prestamos:
            flash("No se puede eliminar una acción con préstamos asociados", "warning")
            return redirect(url_for("acciones.index"))

        db.delete(accion)
        db.commit()
        flash("Acción eliminada correctamente", "success")
        return redirect(url_for("acciones.index"))
    except Exception as e:
        db.rollback()
        flash(str(e), "danger")
        return redirect(url_for("acciones.index"))
    finally:
        db.close()

@acciones_bp.route("/detalle/<int:id>")
@login_required
def detalle(id):

    db = SessionLocal()

    try:

        accion = (
            db.query(Accion)
            .options(
                joinedload(Accion.socio),
                # Trae los préstamos si existen (si no, trae lista vacía)
                joinedload(Accion.prestamos), 
                # NUEVO: Trae los movimientos directos de la acción, existan préstamos o no
                joinedload(Accion.movimientos) 
            )
            .filter(Accion.id == id)
            .first()
        )

        if not accion:

            flash(
                "Acción no encontrada",
                "danger"
            )

            return redirect(
                url_for("acciones.index")
            )

        socio = accion.socio

        prestamos_activos = [

            p
            for p in accion.prestamos
            if p.estado == "ACTIVO"

        ]

        saldo_prestamos = sum(

            p.saldo_actual

            for p in prestamos_activos

        )
        movimientos = (
            db.query(Movimiento)
            .filter(
                Movimiento.accion_id == accion.id
            )
            .order_by(
                Movimiento.fecha_registro.desc()
            )
            .all()
        )
        print(saldo_prestamos)

        return render_template(

            "acciones/detalle.html",
            accion=accion,
            socio=socio,
            prestamos_activos=prestamos_activos,
            saldo_prestamos=saldo_prestamos,
            movimientos=movimientos

        )

    finally:

        db.close()