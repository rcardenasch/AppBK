from flask import Blueprint
from flask import render_template
from flask import request
from flask import flash
from flask import redirect
from flask import url_for

from flask_login import login_user
from flask_login import logout_user

from database.connection import SessionLocal

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

            login_user(user,remember=True)

            return redirect(
                url_for(
                    "dashboard.index"
                )
            )

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