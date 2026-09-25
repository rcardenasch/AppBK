from flask import Blueprint
from flask import jsonify

from services.utilidades_service import (
    UtilidadesService
)

utilidades_bp = Blueprint(
    "utilidades",
    __name__
)


@utilidades_bp.route(
    "/api/utilidades/simular/<int:anio>",
    methods=["GET"]
)
def simular_utilidades(anio):

    return jsonify({

        "igualitario":
            UtilidadesService
            .simular_igualitario(
                anio
            ),

        "participacion":
            UtilidadesService
            .simular_participacion(
                anio
            )

    })