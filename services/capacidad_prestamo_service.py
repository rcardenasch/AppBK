from sqlalchemy import func

from models.configuracion import Configuracion
from models.socio import Socio
from models.prestamo import Prestamo
from models.movimiento import Movimiento
from models.periodo import Periodo
from models.caja_chica import MovimientoCajaChica


class CapacidadPrestamoService:

    @staticmethod
    def calcular(db, periodo_id):

        config = (
            db.query(Configuracion)
            .filter(Configuracion.estado == True)
            .first()
        )

        if not config:
            raise Exception(
                "Debe configurar el sistema."
            )

        periodo = (
            db.query(Periodo)
            .filter(
                Periodo.id == periodo_id,
                Periodo.cerrado==False
            )
            .first()
        )

        if not periodo:
            raise Exception(
                "Periodo no encontrado."
            )

        # -----------------------------
        # Socios activos
        # -----------------------------
        socios_activos = (
            db.query(Socio)
            .filter(
                Socio.estado == True
            )
            .count()
        )
        aporte_minimo = float(
            config.aporte_minimo
        )
        aportes_esperados = (
            socios_activos *
            aporte_minimo
        )
        aportes = (
            db.query(
                func.coalesce(func.sum(Movimiento.aporte),0)
            )
            .filter(
                Movimiento.periodo_id == periodo_id
            )
            .scalar()
        )
        aportes = float(aportes)
        # ------------------------------------
        # Saldo de caja del período anterior -- Ya no considerar
        # ------------------------------------
        periodo_anterior = (
            db.query(Periodo)
            .filter(Periodo.id < periodo.id)
            .order_by(Periodo.id.desc())
            .first()
        )
        saldo_caja = float(
            periodo_anterior.saldo_caja
            if periodo_anterior and periodo_anterior.saldo_caja
            else 0
        )
        # -----------------------------
        # Amortización esperada
        # -----------------------------
        amortizacion = (
            db.query(
                func.coalesce(func.sum(Movimiento.amortizacion),0)
            )
            .filter(
                Movimiento.periodo_id == periodo_id
            )
            .scalar()
        )
        amortizacion = float(amortizacion)
        # -----------------------------
        # Sobre
        # -----------------------------
        sobre = (
            db.query(
                func.coalesce(func.sum(Movimiento.sobre),0)
            )
            .filter(
                Movimiento.periodo_id == periodo_id
            )
            .scalar()
        )
        sobre = float(sobre)

        # -----------------------------
        # Fondo utilidades
        # -----------------------------
        intereses = (
            db.query(
                func.coalesce(
                    func.sum(Movimiento.interes),
                    0
                )
            )
            .filter(
                Movimiento.periodo_id == periodo_id
            )
            .scalar()
        )
        intereses = float(intereses)

        cuota_pagada=(
            db.query(
                func.coalesce(
                    func.sum(Movimiento.cuota_pagada),
                    0
                )
            )
            .filter(
                Movimiento.periodo_id == periodo_id
            )
            .scalar()
        )
        cuota_pagada = float(cuota_pagada)

        # -----------------------------
        # Caja Chica Ingresos
        # -----------------------------
        caja_chica = (
            db.query(
                func.coalesce(func.sum(MovimientoCajaChica.monto), 0)
            )
            .filter(
                MovimientoCajaChica.periodo_id == periodo_id,
                MovimientoCajaChica.tipo == 'INGRESO'
            )
            .scalar()
        )
        caja_chica = float(caja_chica)

        print("Caja chica:",caja_chica)


        # -----------------------------
        # Capacidad
        # -----------------------------
        capacidad = (
            # saldo_caja # evaluar
            #+ aportes
            #+ amortizacion
            #+ intereses
            + cuota_pagada
            + sobre
            # + caja_chica
        )

        return {

            "periodo": periodo,
            "socios_activos": socios_activos,
            "aporte_minimo": aporte_minimo,
            "aportes_esperados": aportes_esperados,
            "aportes_recibidos": aportes,
            "amortizacion_recibida": amortizacion,
            "intereses_esperados": intereses,
            "capacidad": capacidad,
            "saldo_caja": saldo_caja

        }