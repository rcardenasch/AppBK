from flask import Blueprint
from flask import render_template
from flask import request
from flask import flash
from flask import redirect
from flask import url_for

from flask_login import current_user, login_user
from flask_login import logout_user

from database.connection import SessionLocal

from models.periodo import Periodo
from models.usuario import Usuario

from services.auth_service import AuthService

auth_bp = Blueprint(
    "auth",
    __name__
)


@auth_bp.route("/", methods=["GET", "POST"])
@auth_bp.route("/login", methods=["GET", "POST"])
def login():

    if request.method=="POST":

        usuario=request.form["usuario"]
        password=request.form["password"]
        db=SessionLocal()

        try:

            user=db.query(
                Usuario
            ).filter(
                Usuario.usuario==usuario
            ).first()

            if not user:

                flash(
                    "Usuario no existe",
                    "danger"
                )

                return render_template(
                    "login.html"
                )

            if not user.estado:

                flash(
                    "Usuario inactivo",
                    "warning"
                )

                return render_template(
                    "login.html"
                )

            if not AuthService.verificar(
                    password,
                    user.password_hash
            ):

                flash(
                    "Contraseña incorrecta",
                    "danger"
                )

                return render_template(
                    "login.html"
                )

            periodo=(db.query(Periodo).order_by(Periodo.anio.desc(),Periodo.mes.desc()).first()) #Ultimo periodo

             # Iniciar sesión de Flask-Login
            login_user(user, remember=True)

            # Redirección según el rol del usuario
            rol_nombre = user.rol.nombre

            if rol_nombre in ["Administrador", "Tesorero"]:
                return redirect(url_for("dashboard.index"))
                
            elif rol_nombre in ["Socio"]:
                
                return redirect(url_for("socio_portal.mi_estado_cuenta",periodo_Id=periodo.id))
            
            else:
                # Redirección de respaldo si el rol no coincide con los anteriores
                flash("Rol no autorizado", "warning")
                return render_template("login.html")
         
        finally:

            db.close()

    return render_template(
        "login.html"
    )

@auth_bp.route("/logout")
def logout():

    logout_user()

    return redirect(
        url_for("auth.login")
    )