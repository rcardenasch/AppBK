# routes/dashboard_routes.py

from flask import Blueprint, flash, redirect, url_for
from sqlalchemy import desc, func
from flask import render_template

from database.connection import SessionLocal
from models.accion import Accion
from models.caja_chica import MovimientoCajaChica
from models.movimiento import Movimiento

from flask_login import login_required

from models.periodo import Periodo
from models.prestamo import Prestamo
from models.socio import Socio
from models.solicitud_prestamo import SolicitudPrestamo
from services.capacidad_prestamo_service import CapacidadPrestamoService

dashboard_bp=Blueprint(
    "dashboard",
    __name__,
    url_prefix="/dashboard"
)

@dashboard_bp.route("/")
@login_required
def index():

    db = SessionLocal()

    # Ultimo periodo vigente
    periodo = (
            db.query(Periodo)
            .filter(
                Periodo.cerrado == False # periodo vigente
            )
            .order_by(
                Periodo.anio.desc(),
                Periodo.mes.desc()
            )
            .first()
        )

    if not periodo:
        flash(
                "Periodo no encontrado",
                "danger"
            )
        return redirect(
                url_for("periodos.index")
            )

    total_socios=(
        db.query(
            func.coalesce(
                func.count(Socio.id),0)).scalar()
    )
    total_acciones=(
        db.query(
            func.coalesce(
                func.count(Accion.id),0)).filter(Accion.estado=='ACTIVO').scalar()
    )

    prestamos_activos=(
        db.query(
            func.coalesce(
                func.count(Prestamo.id),0)).filter(Prestamo.estado=='ACTIVO').scalar()
    )

    solicitudes=(
        db.query(
            func.coalesce(
                func.count(SolicitudPrestamo.id),0)).filter(SolicitudPrestamo.estado=='PENDIENTE').scalar()
    )

    
    total_aportes = (
        db.query(
            func.coalesce(
                func.sum(Movimiento.aporte),0)).filter(Movimiento.periodo_id==periodo.id).scalar()
    )

    total_sobres = (
            db.query(
                func.coalesce(
                    func.sum(Movimiento.sobre),0)).filter(Movimiento.periodo_id==periodo.id).scalar()
        )

    total_multas = (
        db.query(
            func.coalesce(
                func.sum(Movimiento.multa),0)).filter(Movimiento.periodo_id==periodo.id).scalar()

    )
    total_intereses = (
        db.query(
            func.coalesce(
                func.sum(Movimiento.interes),0)).filter(Movimiento.periodo_id==periodo.id).scalar()

    )
    total_amortizacion = (
            db.query(
                func.coalesce(func.sum(Movimiento.amortizacion),0)
            )
            .filter(
                Movimiento.periodo_id == periodo.id
            )
            .scalar()
        )
        
    total_a_pagar = (
        db.query(
            func.coalesce(
                func.sum(Movimiento.cuota_pagada),0)).filter(Movimiento.periodo_id==periodo.id).scalar()

    ) 
    total_recaudado = (
        total_aportes
        +
        total_sobres
        +
        total_multas
        +
        total_intereses
    )    

    saldo_prestamos = (
        db.query(
            func.coalesce(
                func.sum(Prestamo.saldo_actual
                ),0)
        )
        .filter(
            Prestamo.estado=="ACTIVO"
        ).scalar()
    )

    # Prestado del periodo
    prestado = (
        db.query(
            func.coalesce(
                func.sum(
                    Prestamo.monto),0)).filter(
            Prestamo.estado=="ACTIVO",Prestamo.periodo_id==periodo.id
        ).scalar()
    )


    # -----------------------------
    # Caja Chica Ingresos, falta coordinar con el tesorero para ver la informacion
    # -----------------------------
    caja_chica = (
        db.query(
            func.coalesce(func.sum(MovimientoCajaChica.monto), 0)
        )
        .filter(
            MovimientoCajaChica.periodo_id == periodo.id,
            MovimientoCajaChica.tipo == 'INGRESO'
        )
        .scalar()
        )
   
    #disponible = (
    #    total_a_pagar
    #    +
    #    total_sobres
    #    -
    #    prestado
    #)  

    disponible=(
                CapacidadPrestamoService.calcular(db,periodo.id)["capacidad"] # viene con : cuota_paga + sobre
                -
                float(prestado)
                )
     
    movimientos = (
            db.query(Movimiento).filter(Movimiento.periodo_id==periodo.id)
            .order_by(desc(Movimiento.fecha_registro)).all()
        )
    
    # Consulta para obtener aportes acumulados por cada periodo (año y mes)
    MESES_CORTOS = {
        1: 'Ene', 2: 'Feb', 3: 'Mar', 4: 'Abr', 5: 'May', 6: 'Jun',
        7: 'Jul', 8: 'Ago', 9: 'Sep', 10: 'Oct', 11: 'Nov', 12: 'Dic'
    }

    aportes_mes_raw = (
        db.query(
            Periodo.anio.label('anio'),
            Periodo.mes.label('mes'),
            func.coalesce(func.sum(Movimiento.aporte), 0).label('total')
        )
        .join(Periodo, Movimiento.periodo_id == Periodo.id)  # Relación entre tablas
        .group_by(Periodo.anio, Periodo.mes)
        .order_by(Periodo.anio.asc(), Periodo.mes.asc())      # Ordenados desde el más reciente
        .all()
    )

    lista_meses_aportes = []
    lista_aportes = []
    for registro in aportes_mes_raw:
        # registro[0] = anio, registro[1] = mes, registro[2] = total
        nombre_mes = MESES_CORTOS.get(int(registro.mes), 'S/M')

        # Etiqueta combinada para el gráfico, ej: "Ene 2026"
        lista_meses_aportes.append(f"{nombre_mes} {registro.anio}")
        # Monto acumulado
        lista_aportes.append(float(registro.total))

    lista_meses_prestamos = []
    lista_prestamos = []

    prestamos_mes_raw=(
        db.query(
            Periodo.anio.label('anio'),
            Periodo.mes.label('mes'),
            func.coalesce(func.sum(Prestamo.monto), 0).label('total') # Prestamos otorgados
        )
        .join(Prestamo, Prestamo.periodo_id == Periodo.id)  # Relación entre tablas
        .group_by(Periodo.anio, Periodo.mes)
        .order_by(Periodo.anio.asc(), Periodo.mes.asc())      # Ordenados desde el más reciente
        .all()
    )

    for registro in prestamos_mes_raw:
        # registro[0] = anio, registro[1] = mes, registro[2] = total
        nombre_mes = MESES_CORTOS.get(int(registro.mes), 'S/M')

        # Etiqueta combinada para el gráfico, ej: "Ene 2026"
        lista_meses_prestamos.append(f"{nombre_mes} {registro.anio}")
        # Monto acumulado
        lista_prestamos.append(float(registro.total))

    return render_template(
        "dashboard/index.html",
        movimientos=movimientos,
        periodo=periodo,
        total_socios=total_socios,
        total_acciones=total_acciones,
        prestamos_activos=prestamos_activos,
        solicitudes=solicitudes,
        total_aportes=total_aportes,
        total_sobres=total_sobres,
        total_multas=total_multas,
        total_intereses=total_intereses,
        total_amortizacion=total_amortizacion,
        total_recaudado=total_recaudado,
        saldo_prestamos=saldo_prestamos,
        prestado=prestado,
        disponible=disponible,
        mes_nombre_aportes=lista_meses_aportes,
        aportes_mes=lista_aportes,
        mes_nombre_prestamos=lista_meses_prestamos,
        prestamos_mes=lista_prestamos

        ) 