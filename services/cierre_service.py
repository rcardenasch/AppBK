# services/cierre_service.py

from decimal import Decimal

from sqlalchemy import func, or_, and_

from database.connection import SessionLocal

from models.asistencia import Asistencia
from models.periodo import Periodo
from models.movimiento import Movimiento
from models.fondo_utilidades import FondoUtilidades
from models.prestamo import Prestamo
from models.solicitud_prestamo import SolicitudPrestamo
from models.transferencia import Transferencia


class CierreService:

    @staticmethod
    def validar_requisitos_cierre(db, periodo_id):

        periodo = (
            db.query(Periodo)
            .filter(
                Periodo.id == periodo_id
            )
            .first()
        )

        if not periodo:
            raise Exception(
                f"El período {periodo_id} no existe."
            )

        errores = []

        # ==========================================================
        # 1. SOLICITUDES PENDIENTES
        # ==========================================================

        solicitudes_pendientes = (
            db.query(SolicitudPrestamo)
            .filter(
                SolicitudPrestamo.periodo_id == periodo_id,
                SolicitudPrestamo.estado == "PENDIENTE"
            )
            .count()
        )

        if solicitudes_pendientes > 0:

            errores.append(
                f"Existen {solicitudes_pendientes} "
                f"solicitudes de préstamo pendientes "
                f"de resolver."
            )

        # ==========================================================
        # 2. SOLICITUDES APROBADAS SIN PRÉSTAMO DISTRIBUIDO
        # ==========================================================

        solicitudes_aprobadas = (
            db.query(SolicitudPrestamo)
            .filter(
                SolicitudPrestamo.periodo_id == periodo_id,
                SolicitudPrestamo.estado == "ATENDIDA"
            )
            .all()
        )

        prestamos_sin_distribuir = []

        for solicitud in solicitudes_aprobadas:

            # ------------------------------------------------------
            # Se busca un préstamo generado para esta solicitud.
            #
            # Como SolicitudPrestamo no tiene prestamo_id,
            # usamos socio + período + acción + monto aprobado.
            # ------------------------------------------------------

            prestamo = (
                db.query(Prestamo)
                .filter(
                    Prestamo.socio_id == solicitud.socio_id,
                    Prestamo.periodo_id == periodo_id,
                    Prestamo.accion_id == solicitud.accion_id,
                    Prestamo.monto == solicitud.monto_aprobado
                )
                .first()
            )

            if not prestamo:

                prestamos_sin_distribuir.append(
                    solicitud.id
                )

        if prestamos_sin_distribuir:

            errores.append(
                "Existen solicitudes de préstamo aprobadas "
                "que todavía no han sido distribuidas. "
                f"Solicitudes: "
                f"{', '.join(map(str, prestamos_sin_distribuir))}."
            )

        # ==========================================================
        # 3. PRÉSTAMOS DISTRIBUIDOS EN EL PERÍODO
        # ==========================================================

        total_prestamos_periodo = (
            db.query(Prestamo)
            .filter(
                Prestamo.periodo_id == periodo_id
            )
            .count()
        )

        # ==========================================================
        # 4. TRANSFERENCIAS
        # ==========================================================

        transferencias = (
            db.query(Transferencia)
            .filter(
                Transferencia.periodo_id == periodo_id
            )
            .all()
        )

        total_transferencias = len(
            transferencias
        )

        transferencias_no_confirmadas = [
            t for t in transferencias
            if str(t.estado or "").upper() != "CONFIRMADA"
        ]

        # Si hubo préstamos, debe existir transferencia.
        if total_prestamos_periodo > 0:

            if total_transferencias == 0:

                errores.append(
                    "Existen préstamos distribuidos en este "
                    "período, pero todavía no se han generado "
                    "transferencias."
                )

            elif transferencias_no_confirmadas:

                errores.append(
                    f"Existen {len(transferencias_no_confirmadas)} "
                    f"transferencias que no están CONFIRMADAS."
                )

        # ==========================================================
        # 6. Registro de Asistencia 
        # ==========================================================

        asistencias = (
            db.query(Asistencia)
            .filter(
                Asistencia.periodo_id == periodo_id
            )
            .count()
        )

        if asistencias <= 0:

            errores.append(
                f"No Existen"
                f"Registros de asistencias. "
                f"Por favor de registrar asistencias del periodo: {periodo.anio}-{periodo.mes}"
            )

        # ==========================================================
        # RESULTADO
        # ==========================================================

        if errores:

            return {
                "ok": False,
                "errores": errores
            }

        return {
            "ok": True,
            "errores": [],
            "solicitudes_pendientes": solicitudes_pendientes,
            "solicitudes_aprobadas": len(
                solicitudes_aprobadas
            ),
            "prestamos_distribuidos": (
                total_prestamos_periodo
            ),
            "transferencias": total_transferencias,
            "asistencias":asistencias
        }


    @staticmethod
    def cierre_periodo(periodo_id):

        db = SessionLocal()

        try:

            # =====================================================
            # 1. BUSCAR PERÍODO
            # =====================================================

            periodo = (
                db.query(Periodo)
                .filter(
                    Periodo.id == periodo_id
                )
                .first()
            )

            if not periodo:

                raise Exception(
                    f"Periodo {periodo_id} no existe."
                )

            # =====================================================
            # 2. VALIDAR ESTADO
            # =====================================================

            if periodo.cerrado:

                raise Exception(
                    f"El periodo {periodo.anio}-{periodo.mes:02d} "
                    f"ya fue cerrado."
                )

            # =====================================================
            # 3. VALIDAR QUE SEA EL ÚLTIMO PERÍODO
            # =====================================================

            periodo_ultimo = (
                db.query(Periodo)
                .order_by(
                    Periodo.anio.desc(),
                    Periodo.mes.desc()
                )
                .first()
            )

            if periodo_ultimo.id != periodo.id:

                raise Exception(
                    "Solo se puede cerrar el último período "
                    "registrado."
                )

            # =====================================================
            # 4. VALIDAR FONDO
            # =====================================================

            fondo_existente = (
                db.query(FondoUtilidades)
                .filter(
                    FondoUtilidades.periodo_id == periodo_id
                )
                .first()
            )

            if fondo_existente:

                raise Exception(
                    "Ya existe un cierre financiero "
                    "para este período."
                )

            # =====================================================
            # 5. VALIDAR PRÉSTAMOS Y TRANSFERENCIAS
            # =====================================================

            validacion = (
                CierreService
                .validar_requisitos_cierre(
                    db=db,
                    periodo_id=periodo_id
                )
            )

            if not validacion["ok"]:

                mensaje = (
                    "No se puede cerrar el período:\n"
                    + "\n".join(
                        f"- {error}"
                        for error in validacion["errores"]
                    )
                )

                raise Exception(mensaje)

            # =====================================================
            # 6. MOVIMIENTOS
            # =====================================================

            movimientos = (
                db.query(Movimiento)
                .filter(
                    Movimiento.periodo_id == periodo_id
                )
                .all()
            )

            if not movimientos:

                raise Exception(
                    "No existen movimientos registrados "
                    "para este período."
                )

            # =====================================================
            # 7. TOTALES
            # =====================================================

            total_aportes = Decimal("0.00")
            total_intereses = Decimal("0.00")
            total_multas = Decimal("0.00")
            total_sobres = Decimal("0.00")
            total_amortizacion = Decimal("0.00")
            total_cuotas = Decimal("0.00")

            for mov in movimientos:

                total_aportes += Decimal(
                    str(mov.aporte or 0)
                )

                total_intereses += Decimal(
                    str(mov.interes or 0)
                )

                total_multas += Decimal(
                    str(mov.multa or 0)
                )

                total_sobres += Decimal(
                    str(mov.sobre or 0)
                )

                total_amortizacion += Decimal(
                    str(mov.amortizacion or 0)
                )

                total_cuotas += Decimal(
                    str(mov.cuota_pagada or 0)
                )

            # =====================================================
            # 8. UTILIDAD
            # =====================================================

            utilidad_total = (
                total_intereses
                + total_multas
                + total_sobres
            )

            # =====================================================
            # 9. PERÍODO ANTERIOR
            # =====================================================

            periodo_anterior = (
                db.query(Periodo)
                .filter(
                    or_(
                        Periodo.anio < periodo.anio,
                        and_(
                            Periodo.anio == periodo.anio,
                            Periodo.mes < periodo.mes
                        )
                    )
                )
                .order_by(
                    Periodo.anio.desc(),
                    Periodo.mes.desc()
                )
                .first()
            )

            if periodo_anterior:

                saldo_anterior = Decimal(
                    str(
                        periodo_anterior.saldo_caja
                        or 0
                    )
                )

            else:

                saldo_anterior = Decimal("0.00")

            # =====================================================
            # 10. PRÉSTAMOS ENTREGADOS
            # =====================================================

            fecha_inicio = periodo.fecha_inicio

            if not periodo.fecha_fin:

                raise Exception(
                    "El período no tiene fecha_fin configurada."
                )

            fecha_fin = periodo.fecha_fin

            prestamos_entregados = (
                db.query(
                    func.coalesce(
                        func.sum(
                            Prestamo.monto
                        ),
                        0
                    )
                )
                .filter(
                    Prestamo.periodo_id == periodo_id
                )
                .scalar()
            )

            prestamos_entregados = Decimal(
                str(
                    prestamos_entregados or 0
                )
            )

            # =====================================================
            # 11. SALDO FINAL
            # =====================================================

            saldo_final = (
                saldo_anterior
                + total_aportes
                + total_intereses
                + total_amortizacion
                + total_multas
                + total_sobres
                - prestamos_entregados
            )

            if saldo_final == Decimal("-0.00"):

                saldo_final = Decimal("0.00")

            # =====================================================
            # 12. PRÉSTAMOS ACTIVOS
            # =====================================================

            prestamos_activos = (
                db.query(Prestamo)
                .filter(
                    Prestamo.estado == "ACTIVO"
                )
                .all()
            )

            total_prestamos_activos = len(
                prestamos_activos
            )

            saldo_prestamos_activos = Decimal("0.00")

            for prestamo in prestamos_activos:

                saldo_prestamos_activos += Decimal(
                    str(
                        prestamo.saldo_actual or 0
                    )
                )

            # =====================================================
            # 13. CREAR FONDO DE UTILIDADES
            # =====================================================

            fondo = FondoUtilidades(

                periodo_id=periodo_id,
                intereses=total_intereses,
                multas=total_multas,
                sobres=total_sobres,
                total=utilidad_total
            )

            db.add(fondo)

            # =====================================================
            # 14. CERRAR PERÍODO
            # =====================================================

            periodo.saldo_caja = saldo_final

            periodo.cerrado = True

            # =====================================================
            # 15. COMMIT
            # =====================================================

            db.commit()

            # =====================================================
            # 16. RESPUESTA
            # =====================================================

            return {

                "success": True,

                "periodo_id": periodo_id,

                "periodo": (
                    f"{periodo.anio}-"
                    f"{periodo.mes:02d}"
                ),

                "movimientos": len(
                    movimientos
                ),

                "solicitudes_aprobadas": validacion[
                    "solicitudes_aprobadas"
                ],

                "prestamos_distribuidos": validacion[
                    "prestamos_distribuidos"
                ],

                "transferencias": validacion[
                    "transferencias"
                ],

                "prestamos_activos":
                    total_prestamos_activos,

                "saldo_prestamos":
                    saldo_prestamos_activos,

                "saldo_anterior":
                    saldo_anterior,

                "aportes":
                    total_aportes,

                "intereses":
                    total_intereses,

                "amortizacion":
                    total_amortizacion,

                "multas":
                    total_multas,

                "sobres":
                    total_sobres,

                "cuotas":
                    total_cuotas,

                "prestamos_entregados":
                    prestamos_entregados,

                "saldo_caja":
                    saldo_final,

                "utilidad_total":
                    utilidad_total
            }

        except Exception as e:

            db.rollback()

            return {
                "success": False,
                "error": str(e)
            }

        finally:

            db.close()


    @staticmethod
    def extornar_cierre_periodo(periodo_id):

        db = SessionLocal()

        try:

            # =====================================================
            # 1. BUSCAR PERÍODO
            # =====================================================

            periodo = (
                db.query(Periodo)
                .filter(
                    Periodo.id == periodo_id
                )
                .first()
            )

            if not periodo:

                raise Exception(
                    f"El período {periodo_id} no existe."
                )

            # =====================================================
            # 2. DEBE ESTAR CERRADO
            # =====================================================

            if not periodo.cerrado:

                raise Exception(
                    "El período no está cerrado."
                )

            # =====================================================
            # 3. DEBE SER EL ÚLTIMO PERÍODO
            # =====================================================

            ultimo_periodo = (
                db.query(Periodo)
                .order_by(
                    Periodo.anio.desc(),
                    Periodo.mes.desc()
                )
                .first()
            )

            if ultimo_periodo.id != periodo.id:

                raise Exception(
                    "No se puede extornar este período "
                    "porque existen períodos posteriores."
                )

            # =====================================================
            # 4. BUSCAR FONDO DE UTILIDADES
            # =====================================================

            fondo = (
                db.query(FondoUtilidades)
                .filter(
                    FondoUtilidades.periodo_id == periodo_id
                )
                .first()
            )

            if not fondo:

                raise Exception(
                    "No existe el fondo de utilidades "
                    "correspondiente al cierre."
                )

            # =====================================================
            # 5. EXTORNAR FONDO
            # =====================================================

            db.delete(fondo)

            # =====================================================
            # 6. REABRIR PERÍODO
            # =====================================================

            periodo.cerrado = False

            # =====================================================
            # 7. SALDO CAJA
            # =====================================================
            #
            # El saldo será recalculado al volver a cerrar.
            #
            # No eliminamos movimientos, préstamos,
            # transferencias ni aportes.
            #
            # =====================================================

            periodo.saldo_caja = Decimal("0.00")

            # =====================================================
            # 8. GUARDAR
            # =====================================================

            db.commit()

            return {

                "success": True,

                "periodo_id": periodo_id,

                "periodo": (
                    f"{periodo.anio}-"
                    f"{periodo.mes:02d}"
                ),

                "mensaje": (
                    "El cierre del período fue "
                    "extornado correctamente. "
                    "El período nuevamente está abierto."
                )
            }

        except Exception as e:

            db.rollback()

            return {

                "success": False,

                "error": str(e)
            }

        finally:

            db.close()