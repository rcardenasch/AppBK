from functools import wraps

from flask import (
    abort,
    jsonify,
    redirect,
    request,
    url_for
)

from flask_login import current_user


def tiene_permiso(modulo, accion):  # tmabien esta implementado en el modelo usuarios, debe estar solo en un solo lugar revisar

    if not current_user.is_authenticated:
        return False

    if (
        current_user.rol
        and current_user.rol.nombre.upper()
        == "ADMINISTRADOR"
    ):
        return True

    rol = current_user.rol

    if not rol or not rol.estado:
        return False

    for rp in rol.permisos:

        permiso = rp.permiso

        if not permiso:
            continue

        if (
            permiso.modulo.lower() == modulo.lower()
            and
            permiso.accion.lower() == accion.lower()
        ):
            return True

    return False


def requiere_permiso(modulo, accion):

    def decorador(func):

        @wraps(func)
        def wrapper(*args, **kwargs):

            if not current_user.is_authenticated:

                if request.is_json:

                    return jsonify({
                        "ok": False,
                        "mensaje": "Sesión no válida."
                    }), 401

                return redirect(
                    url_for("auth.login")
                )

            if not tiene_permiso(
                modulo,
                accion
            ):

                if request.is_json:

                    return jsonify({
                        "ok": False,
                        "mensaje":
                            "No tiene permisos para realizar esta operación."
                    }), 403

                return abort(403)

            return func(
                *args,
                **kwargs
            )

        return wrapper

    return decorador