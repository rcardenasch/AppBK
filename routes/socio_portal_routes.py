
# routes/socio_portal_routes.py

from flask import Blueprint, render_template, redirect, url_for, flash
from flask_login import login_required, current_user

from sqlalchemy import or_, and_

from database.connection import SessionLocal

from models.socio import Socio
from models.accion import Accion
from models.movimiento import Movimiento
from models.prestamo import Prestamo
from models.periodo import Periodo
from models.solicitud_prestamo import SolicitudPrestamo
from models.asistencia import Asistencia
from models.transferencia import Transferencia


socio_portal_bp = Blueprint(
    "socio_portal",
    __name__,
    url_prefix="/socio_portal"
)


@socio_portal_bp.route("/mi_estado_cuenta/<int:periodo_Id>")
@login_required
def mi_estado_cuenta(periodo_Id):
    print("periodo_Id:",periodo_Id)
    db = SessionLocal()

    try:

        # =========================================================
        # VALIDAR SOCIO
        # =========================================================

        socio_id = getattr(current_user, "socio_id", None)

        if not socio_id:

            flash(
                "El usuario no tiene un socio asociado.",
                "warning"
            )

            return redirect(
                url_for("socios.index")
            )

        socio = (
            db.query(Socio)
            .filter(
                Socio.id == socio_id
            )
            .first()
        )

        if not socio:

            flash(
                "No se encontró la información del socio.",
                "danger"
            )

            return redirect(
                url_for("socios.index")
            )

        # =========================================================
        # ÚLTIMO PERÍODO CERRADO
        # =========================================================

        # AJUSTAR "estado" si en tu modelo Periodo
        # utilizas otro campo para identificar el período vigente.

        periodo_vigente = (
            db.query(Periodo)
            .filter(
                Periodo.id == periodo_Id # periodo seleccionado
            )
            .order_by(
                Periodo.anio.desc(),
                Periodo.mes.desc()
            )
            .first()
        )

        # Si no existe un período marcado como CERRADO, USAR EL ULTIMO ABIERTO,
        # tomamos el último período cronológico.
        
        periodos=(db.query(Periodo).order_by(Periodo.anio.desc(),Periodo.mes.desc()).all()) #Lista de periodos

        if not periodo_vigente:

            periodo_vigente = (
                db.query(Periodo)
                          #.filter(
                          #      Periodo.cerrado == False # periodo abierto
                          #  )
                .order_by(
                    Periodo.anio.desc(),
                    Periodo.mes.desc()
                )
                .first()
            )

        if not periodo_vigente and not periodos:

            flash(
                "No existe ningún período registrado.",
                "warning"
            )

            return render_template(
                "socios/mi_estado_cuenta.html",
                socio=socio,
                periodos=periodos,
                periodo=None,
                acciones=[],
                movimientos=[],
                prestamos=[],
                solicitudes=[],
                asistencia=None,
                transferencias=[],
                transferencias_recibidas=[],
                resumen={}
            )

        # =========================================================
        # ACCIONES
        # =========================================================

        acciones = (
            db.query(Accion)
            .filter(
                Accion.socio_id == socio.id
            )
            .order_by(
                Accion.numero_accion.asc()
            )
            .all()
        )

        # =========================================================
        # MOVIMIENTOS 
        # =========================================================

        movimientos = (
            db.query(Movimiento)
            .filter(
                Movimiento.socio_id == socio.id,
                Movimiento.periodo_id <= periodo_Id
            )
            .order_by(
                Movimiento.id.desc()
            )
            .all()
        )
        # =========================================================
        # MOVIMIENTOS DEL PERÍODO
        # =========================================================

        movimientos_periodo = (
            db.query(Movimiento)
            .filter(
                Movimiento.socio_id == socio.id,
                Movimiento.periodo_id == periodo_Id
            )
            .order_by(
                Movimiento.id.desc()
            )
            .all()
        )

        # =========================================================
        # PRÉSTAMOS ACTIVOS
        # =========================================================

        prestamos = (
            db.query(Prestamo)
            .filter(
                Prestamo.socio_id == socio.id,
                Prestamo.estado == "ACTIVO",
                Prestamo.periodo_id<=periodo_Id
            )
            .order_by(
                Prestamo.id.desc()
            )
            .all()
        )

        # =========================================================
        # PRÉSTAMOS - AVANCE HASTA EL PERÍODO SELECCIONADO
        # =========================================================

        for prestamo in prestamos:

            monto = float(prestamo.monto or 0)

            # Amortización acumulada del préstamo
            # hasta el período seleccionado
            amortizado = sum(
                float(m.amortizacion or 0)
                for m in movimientos
                if m.prestamo_id == prestamo.id
                and m.periodo_id <= periodo_Id
            )

            # Evitar superar el monto original
            amortizado = min(max(amortizado, 0), monto)

            saldo_al_periodo = max(
                monto - amortizado,
                0
            )

            porcentaje = (
                (amortizado / monto) * 100
                if monto > 0
                else 0
            )

            porcentaje = min(
                max(porcentaje, 0),
                100
            )

            prestamo.monto_float = monto
            prestamo.pagado_float = amortizado
            prestamo.saldo_periodo_float = saldo_al_periodo
            prestamo.porcentaje_avance = round(
                porcentaje,
                1
            )

        # =========================================================
        # SOLICITUDES DEL PERÍODO
        # =========================================================

        solicitudes = (
            db.query(SolicitudPrestamo)
            .filter(
                SolicitudPrestamo.socio_id == socio.id,
                SolicitudPrestamo.periodo_id <= periodo_Id
            )
            .order_by(
                SolicitudPrestamo.id.desc()
            )
            .all()
        )

        # =========================================================
        # ASISTENCIA DEL PERÍODO
        # =========================================================

        asistencia = (
            db.query(Asistencia)
            .filter(
                Asistencia.socio_id == socio.id,
                Asistencia.periodo_id==periodo_Id
     
            )
            .first()
        )

        # =========================================================
        # TRANSFERENCIAS REALIZADAS
        # =========================================================

        transferencias = (
            db.query(Transferencia)
            .filter(
                Transferencia.socio_origen_id == socio.id

            )
            .order_by(
                Transferencia.fecha_transferencia.desc()
            )
            .all()
        )

        # =========================================================
        # TRANSFERENCIAS RECIBIDAS
        # =========================================================

        transferencias_recibidas = (
            db.query(Transferencia)
            .filter(
                Transferencia.socio_destino_id == socio.id
       
            )
            .order_by(
                Transferencia.fecha_transferencia.desc()
            )
            .all()
        )

        # =========================================================
        # FILTRAR TRANSFERENCIAS DEL PERÍODO
        # =========================================================

        transferencias_periodo = [
            t for t in transferencias
            if t.periodo_id == periodo_Id
        ]

        transferencias_recibidas_periodo = [
            t for t in transferencias_recibidas
            if t.periodo_id == periodo_Id
        ]

        # =========================================================
        # RESUMEN DE ACCIONES
        # =========================================================

        cantidad_acciones = len(acciones)

        valor_acciones = sum(
            float(a.valor or 0)
            for a in acciones
        )

        acciones_activas = [
            a for a in acciones
            if a.estado == "ACTIVO"
        ]

        valor_acciones_activas = sum(
            float(a.valor or 0)
            for a in acciones_activas
        )

        # =========================================================
        # APORTES DEL PERÍODO
        # =========================================================

        total_aportes = sum(
            float(m.aporte or 0)
            for m in movimientos_periodo
        )

        total_cuotas = sum(
            float(m.cuota_pagada or 0)
            for m in movimientos_periodo
        )

        total_intereses = sum(
            float(m.interes or 0)
            for m in movimientos_periodo
        )

        total_amortizacion = sum(
            float(m.amortizacion or 0)
            for m in movimientos_periodo
        )

        total_intereses_total = sum(
            float(m.interes or 0)
            for m in movimientos
        )

        total_amortizacion_total = sum(
            float(m.amortizacion or 0)
            for m in movimientos
        )

        total_multas = sum(
            float(m.multa or 0)
            for m in movimientos_periodo
        )

        total_sobre = sum(
            float(m.sobre or 0)
            for m in movimientos_periodo
        )

        # =========================================================
        # PRÉSTAMOS
        # =========================================================

        saldo_prestamos = sum(
            p.saldo_periodo_float
            for p in prestamos
        )

        monto_prestamos = sum(
            p.monto_float
            for p in prestamos
        )

        monto_pagado = sum(
            p.pagado_float
            for p in prestamos
        )

        porcentaje_avance = (
            monto_pagado / monto_prestamos * 100
            if monto_prestamos > 0
            else 0
        )

        print ("monto prestamos: ",monto_prestamos," Monto pagado: ",monto_pagado,"saldo prestamos: ",saldo_prestamos,"total amortizacion: ",total_amortizacion_total)

        # =========================================================
        # TRANSFERENCIAS
        # =========================================================

        total_transferido = sum(
            float(t.monto or 0)
            for t in transferencias_periodo
            if t.estado == "CONFIRMADA"
        )

        total_recibido = sum(
            float(t.monto or 0)
            for t in transferencias_recibidas_periodo
            if t.estado == "CONFIRMADA"
        )

        # =========================================================
        # SOLICITUDES
        # =========================================================

        monto_solicitado = sum(
            float(s.monto_solicitado or 0)
            for s in solicitudes
            if s.periodo_id<=periodo_Id
        )

        monto_aprobado = sum(
            float(s.monto_aprobado or 0)
            for s in solicitudes
            if s.periodo_id<=periodo_Id
        )
        

        # =========================================================
        # RESUMEN
        # =========================================================

        resumen = {

            "cantidad_acciones": cantidad_acciones,
            "acciones_activas": len(acciones_activas),
            "valor_acciones": valor_acciones,
            "valor_acciones_activas": valor_acciones_activas,
            "total_aportes":total_aportes,
            "total_cuotas":total_cuotas+total_sobre,
            "total_intereses":total_intereses,
            "total_amortizacion": total_amortizacion,
            "total_multas":total_multas,
            "total_sobre":total_sobre,
            "cantidad_prestamos":len(prestamos),
            "monto_prestamos": monto_prestamos,
            "saldo_prestamos": saldo_prestamos,
            "porcentaje_avance": round(porcentaje_avance, 1),
            "monto_solicitado": monto_solicitado,
            "monto_aprobado": monto_aprobado,
            "total_transferido": total_transferido,
            "total_recibido": total_recibido,
            "saldo_transferencias": total_recibido - total_transferido
        }

        return render_template(
            "socios/portal.html",

            socio=socio,
            periodo=periodo_vigente,
            periodos=periodos,
            acciones=acciones,
            movimientos=movimientos_periodo,
            prestamos=prestamos,
            solicitudes=solicitudes,
            asistencia=asistencia,
            transferencias=transferencias_periodo,
            transferencias_recibidas=transferencias_recibidas_periodo,
            resumen=resumen
        )

    finally:

        db.close()

