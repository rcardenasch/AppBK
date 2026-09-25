# routes/usuarios_routes.py

from collections import defaultdict

from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    flash
)

from flask_login import (
    login_required,
    current_user
)

from werkzeug.security import (
    generate_password_hash
)

from sqlalchemy.exc import IntegrityError

from database.connection import SessionLocal

from models.usuario import Usuario
from models.socio import Socio
from models.rol import Rol
from models.permiso import Permiso
from models.rol_permiso import RolPermiso


usuarios_bp = Blueprint(
    "usuarios",
    __name__,
    url_prefix="/usuarios"
)


# ============================================================
# LISTADO
# ============================================================

@usuarios_bp.route("/")
@login_required
def index():

    db = SessionLocal()

    try:

        usuarios = (
            db.query(Usuario)
            .join(Rol)
            .outerjoin(Socio)
            .order_by(
                Usuario.estado.desc(),
                Usuario.nombres.asc()
            )
            .all()
        )

        return render_template(
            "usuarios/index.html",
            usuarios=usuarios
        )

    finally:
        db.close()


# ============================================================
# NUEVO USUARIO
# ============================================================

@usuarios_bp.route("/nuevo", methods=["GET", "POST"])
@login_required
def nuevo():

    db = SessionLocal()

    try:

        roles = (
            db.query(Rol)
            .filter(
                Rol.estado == True
            )
            .order_by(
                Rol.nombre
            )
            .all()
        )

        # Solo socios activos que todavía
        # no tienen usuario
        socios = (
            db.query(Socio)
            .outerjoin(
                Usuario,
                Usuario.socio_id == Socio.id
            )
            .filter(
                Socio.estado == True,
                Usuario.id == None
            )
            .order_by(
                Socio.nombres
            )
            .all()
        )

        if request.method == "POST":

            nombres = request.form.get(
                "nombres",
                ""
            ).strip()

            usuario_nombre = request.form.get(
                "usuario",
                ""
            ).strip().lower()

            correo = request.form.get(
                "correo",
                ""
            ).strip()

            password = request.form.get(
                "password",
                ""
            )

            rol_id = request.form.get(
                "rol_id"
            )

            socio_id = request.form.get(
                "socio_id"
            )

            # ------------------------------------------------
            # VALIDACIONES
            # ------------------------------------------------

            if not nombres:
                flash(
                    "Debe ingresar los nombres del usuario.",
                    "danger"
                )

                return render_template(
                    "usuarios/form.html",
                    roles=roles,
                    socios=socios,
                    modo="nuevo"
                )

            if not usuario_nombre:
                flash(
                    "Debe ingresar el nombre de usuario.",
                    "danger"
                )

                return render_template(
                    "usuarios/form.html",
                    roles=roles,
                    socios=socios,
                    modo="nuevo"
                )

            if not password:
                flash(
                    "Debe ingresar una contraseña inicial.",
                    "danger"
                )

                return render_template(
                    "usuarios/form.html",
                    roles=roles,
                    socios=socios,
                    modo="nuevo"
                )

            if len(password) < 6:

                flash(
                    "La contraseña debe tener al menos 6 caracteres.",
                    "danger"
                )

                return render_template(
                    "usuarios/form.html",
                    roles=roles,
                    socios=socios,
                    modo="nuevo"
                )

            # ------------------------------------------------
            # USUARIO DUPLICADO
            # ------------------------------------------------

            existe_usuario = (
                db.query(Usuario)
                .filter(
                    Usuario.usuario == usuario_nombre
                )
                .first()
            )

            if existe_usuario:

                flash(
                    "El nombre de usuario ya existe.",
                    "danger"
                )

                return render_template(
                    "usuarios/form.html",
                    roles=roles,
                    socios=socios,
                    modo="nuevo"
                )

            # ------------------------------------------------
            # ROL
            # ------------------------------------------------

            rol = (
                db.query(Rol)
                .filter(
                    Rol.id == int(rol_id)
                )
                .first()
            )

            if not rol:

                flash(
                    "El rol seleccionado no existe.",
                    "danger"
                )

                return render_template(
                    "usuarios/form.html",
                    roles=roles,
                    socios=socios,
                    modo="nuevo"
                )

            # ------------------------------------------------
            # SOCIO
            # ------------------------------------------------

            socio = None

            if socio_id:

                socio = (
                    db.query(Socio)
                    .filter(
                        Socio.id == int(socio_id),
                        Socio.estado == True
                    )
                    .first()
                )

                if not socio:

                    flash(
                        "El socio seleccionado no existe o está inactivo.",
                        "danger"
                    )

                    return render_template(
                        "usuarios/form.html",
                        roles=roles,
                        socios=socios,
                        modo="nuevo"
                    )

                usuario_socio = (
                    db.query(Usuario)
                    .filter(
                        Usuario.socio_id == socio.id
                    )
                    .first()
                )

                if usuario_socio:

                    flash(
                        "El socio seleccionado ya tiene un usuario asignado.",
                        "danger"
                    )

                    return render_template(
                        "usuarios/form.html",
                        roles=roles,
                        socios=socios,
                        modo="nuevo"
                    )

            # ------------------------------------------------
            # CREAR
            # ------------------------------------------------

            nuevo_usuario = Usuario(

                nombres=nombres,
                usuario=usuario_nombre,
                correo=correo,
                rol_id=rol.id,
                socio_id=(
                    socio.id
                    if socio
                    else None
                ),
                password_hash=
                    generate_password_hash(
                        password
                    ),
                estado=True,
                debe_cambiar_password=True

            )

            db.add(
                nuevo_usuario
            )

            try:

                db.commit()

            except IntegrityError:

                db.rollback()

                flash(
                    "No se pudo registrar. "
                    "El usuario o socio ya está asociado.",
                    "danger"
                )

                return render_template(
                    "usuarios/form.html",
                    roles=roles,
                    socios=socios,
                    modo="nuevo"
                )

            flash(
                "Usuario registrado correctamente. "
                "En su primer ingreso deberá confirmar o cambiar su contraseña.",
                "success"
            )

            return redirect(
                url_for(
                    "usuarios.index"
                )
            )

        return render_template(
            "usuarios/form.html",
            roles=roles,
            socios=socios,
            modo="nuevo"
        )

    finally:
        db.close()


# ============================================================
# EDITAR
# ============================================================

@usuarios_bp.route(
    "/editar/<int:id>",
    methods=["GET", "POST"]
)
@login_required
def editar(id):

    db = SessionLocal()

    try:

        usuario = (
            db.query(Usuario)
            .filter(
                Usuario.id == id
            )
            .first()
        )

        if not usuario:

            return "Usuario no encontrado", 404

        roles = (
            db.query(Rol)
            .filter(
                Rol.estado == True
            )
            .order_by(
                Rol.nombre
            )
            .all()
        )

        # Socios libres + el socio actual
        socios = (
            db.query(Socio)
            .outerjoin(
                Usuario,
                Usuario.socio_id == Socio.id
            )
            .filter(
                Socio.estado == True
            )
            .filter(
                (Usuario.id == None) |
                (Usuario.id == usuario.id)
            )
            .order_by(Socio.nombres).all()
        )

        if request.method == "POST":

            nombres = request.form.get("nombres","").strip()
            correo = request.form.get("correo","").strip()
            rol_id = request.form.get("rol_id")
            socio_id = request.form.get("socio_id")
            estado = (request.form.get("estado") == "1")

            if not nombres:

                flash("Los nombres son obligatorios.", "danger")

                return redirect(
                    request.url
                )

            # ------------------------------------------------
            # VALIDAR SOCIO
            # ------------------------------------------------

            nuevo_socio_id = (
                int(socio_id)
                if socio_id
                else None
            )

            if nuevo_socio_id:

                socio = (
                    db.query(Socio)
                    .filter(
                        Socio.id == nuevo_socio_id,
                        Socio.estado == True
                    )
                    .first()
                )

                if not socio:

                    flash("El socio seleccionado no existe.", "danger")
                    return redirect(
                        request.url
                    )

                otro_usuario = (
                    db.query(Usuario)
                    .filter(
                        Usuario.socio_id == nuevo_socio_id,
                        Usuario.id != usuario.id
                    )
                    .first()
                )

                if otro_usuario:

                    flash(
                        "Ese socio ya tiene otro usuario asignado.",
                        "danger"
                    )

                    return redirect(
                        request.url
                    )

            # ------------------------------------------------
            # ACTUALIZAR
            # ------------------------------------------------

            usuario.nombres = nombres
            usuario.correo = correo
            usuario.rol_id = int(rol_id)
            usuario.socio_id = nuevo_socio_id
            usuario.estado = estado

            db.commit()

            flash(
                "Usuario actualizado correctamente.",
                "success"
            )

            return redirect(
                url_for(
                    "usuarios.index"
                )
            )

        return render_template(
            "usuarios/form.html",
            usuario=usuario,
            roles=roles,
            socios=socios,
            modo="editar"
        )

    finally:
        db.close()


# ============================================================
# ACTIVAR / DESACTIVAR
# ============================================================

@usuarios_bp.route(
    "/estado/<int:id>",
    methods=["POST"]
)
@login_required
def cambiar_estado(id):

    db = SessionLocal()

    try:

        usuario = (
            db.query(Usuario)
            .filter(
                Usuario.id == id
            )
            .first()
        )

        if not usuario:

            flash(
                "Usuario no encontrado.",
                "danger"
            )

            return redirect(
                url_for("usuarios.index")
            )

        if usuario.id == current_user.id:

            flash(
                "No puede desactivar su propio usuario.",
                "warning"
            )

            return redirect(
                url_for("usuarios.index")
            )

        usuario.estado = not usuario.estado

        db.commit()

        flash(
            "Estado del usuario actualizado.",
            "success"
        )

        return redirect(
            url_for("usuarios.index")
        )

    finally:
        db.close()


# ============================================================
# RESTABLECER CONTRASEÑA
# ============================================================

@usuarios_bp.route(
    "/restablecer-password/<int:id>",
    methods=["POST"]
)
@login_required
def restablecer_password(id):

    db = SessionLocal()

    try:

        usuario = (
            db.query(Usuario)
            .filter(
                Usuario.id == id
            )
            .first()
        )

        if not usuario:

            flash(
                "Usuario no encontrado.",
                "danger"
            )

            return redirect(
                url_for("usuarios.index")
            )

        nueva_password = request.form.get(
            "password",
            ""
        )

        if len(nueva_password) < 6:

            flash(
                "La contraseña debe tener al menos 6 caracteres.",
                "danger"
            )

            return redirect(
                url_for("usuarios.index")
            )

        usuario.password_hash = (
            generate_password_hash(
                nueva_password
            )
        )

        usuario.debe_cambiar_password = True

        db.commit()

        flash(
            "Contraseña restablecida. "
            "El usuario deberá confirmarla o cambiarla en su próximo ingreso.",
            "success"
        )

        return redirect(
            url_for("usuarios.index")
        )

    finally:
        db.close()


# ============================================================
# CAMBIO DE CONTRASEÑA
# ============================================================

@usuarios_bp.route(
    "/cambiar-password",
    methods=["GET", "POST"]
)
@login_required
def cambiar_password():

    db = SessionLocal()

    try:

        usuario = (
            db.query(Usuario)
            .filter(
                Usuario.id == current_user.id
            )
            .first()
        )

        if request.method == "POST":

            password_actual = request.form.get(
                "password_actual",
                ""
            )

            password_nueva = request.form.get(
                "password_nueva",
                ""
            )

            confirmar = request.form.get(
                "confirmar",
                ""
            )

            # En primer ingreso no obligamos
            # a ingresar la contraseña anterior
            # porque el administrador pudo haber
            # proporcionado una contraseña temporal.

            if not usuario.debe_cambiar_password:

                from werkzeug.security import check_password_hash

                if not check_password_hash(
                    usuario.password_hash,
                    password_actual
                ):

                    flash(
                        "La contraseña actual no es correcta.",
                        "danger"
                    )

                    return render_template(
                        "usuarios/cambiar_password.html"
                    )

            if len(password_nueva) < 6:

                flash(
                    "La nueva contraseña debe tener al menos 6 caracteres.",
                    "danger"
                )

                return render_template(
                    "usuarios/cambiar_password.html"
                )

            if password_nueva != confirmar:

                flash(
                    "Las contraseñas no coinciden.",
                    "danger"
                )

                return render_template(
                    "usuarios/cambiar_password.html"
                )

            usuario.password_hash = (
                generate_password_hash(
                    password_nueva
                )
            )

            usuario.debe_cambiar_password = False

            db.commit()

            flash(
                "Contraseña actualizada correctamente.",
                "success"
            )

            return redirect(
                url_for("usuarios.index")
            )

        return render_template(
            "usuarios/cambiar_password.html"
        )

    finally:
        db.close()


# ============================================================
# ROLES
# ============================================================

@usuarios_bp.route(
    "/roles",
    methods=["GET", "POST"]
)
@login_required
def roles():

    db = SessionLocal()

    try:

        if request.method == "POST":

            nombre = request.form.get(
                "nombre",
                ""
            ).strip()

            descripcion = request.form.get(
                "descripcion",
                ""
            ).strip()

            if not nombre:

                flash(
                    "El nombre del rol es obligatorio.",
                    "danger"
                )

                return redirect(
                    url_for("usuarios.roles")
                )

            existe = (
                db.query(Rol)
                .filter(
                    Rol.nombre == nombre
                )
                .first()
            )

            if existe:

                flash(
                    "El rol ya existe.",
                    "warning"
                )

                return redirect(
                    url_for("usuarios.roles")
                )

            rol = Rol(
                nombre=nombre,
                descripcion=descripcion,
                estado=True
            )

            db.add(rol)
            db.commit()

            flash(
                "Rol creado correctamente.",
                "success"
            )

            return redirect(
                url_for("usuarios.roles")
            )

        roles = (
            db.query(Rol)
            .order_by(
                Rol.nombre
            )
            .all()
        )

        return render_template(
            "usuarios/roles.html",
            roles=roles
        )

    finally:
        db.close()


# ============================================================
# ASIGNAR PERMISOS AL ROL
# ============================================================

@usuarios_bp.route(
    "/roles/<int:rol_id>/permisos",
    methods=["GET", "POST"]
)
@login_required
def permisos_rol(rol_id):

    db = SessionLocal()

    try:

        rol = (
            db.query(Rol)
            .filter(
                Rol.id == rol_id
            )
            .first()
        )

        if not rol:

            return "Rol no encontrado", 404

        permisos = (
            db.query(Permiso)
            .order_by(
                Permiso.modulo,
                Permiso.accion
            )
            .all()
        )

        if request.method == "POST":

            seleccionados = request.form.getlist(
                "permisos"
            )

            # Eliminar permisos actuales
            db.query(RolPermiso).filter(
                RolPermiso.rol_id == rol.id
            ).delete(
                synchronize_session=False
            )

            for permiso_id in seleccionados:

                rp = RolPermiso(
                    rol_id=rol.id,
                    permiso_id=int(permiso_id)
                )

                db.add(rp)

            db.commit()

            flash(
                "Permisos del rol actualizados.",
                "success"
            )

            return redirect(
                url_for(
                    "usuarios.permisos_rol",
                    rol_id=rol.id
                )
            )

        permisos_asignados = {
            rp.permiso_id
            for rp in (
                db.query(RolPermiso)
                .filter(
                    RolPermiso.rol_id == rol.id
                )
                .all()
            )
        }

        permisos_por_modulo = defaultdict(list)

        for permiso in permisos:
            permisos_por_modulo[
                permiso.modulo
            ].append(permiso)

        return render_template(
            "usuarios/permisos.html",
            rol=rol,
            permisos=permisos,
            permisos_por_modulo=permisos_por_modulo,
            permisos_asignados=permisos_asignados
        )

    finally:
        db.close()