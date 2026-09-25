from decimal import Decimal
from sqlalchemy import func, or_, and_
import re

from database.connection import SessionLocal
from models.accion import Accion
from models.prestamo import Prestamo
from models.periodo import Periodo
from models.movimiento import Movimiento
from models.socio import Socio
from models.caja_chica import CajaChica, MovimientoCajaChica
from services.interes_service import InteresService


class AdquisicionAccionService:

    CENTAVOS = Decimal("0.01")

    @staticmethod
    def D(valor):
        if valor is None:
            return Decimal("0.00")

        return Decimal(str(valor)).quantize(
            Decimal("0.01")
        )

    # ==========================================================
    # OBTENER PERÍODOS DESDE ENERO HASTA EL MES ANTERIOR
    # AL PERÍODO DE COMPRA
    # ==========================================================

    @staticmethod
    def obtener_periodos_historicos(
        db,
        periodo_compra
    ):

        periodos = (
            db.query(Periodo)
            .filter(
                or_(
                    Periodo.anio < periodo_compra.anio,

                    and_(
                        Periodo.anio == periodo_compra.anio,
                        Periodo.mes <= periodo_compra.mes
                    )
                )
            )
            .order_by(
                Periodo.anio.asc(),
                Periodo.mes.asc()
            )
            .all()
        )

        return periodos

    # ==========================================================
    # CALCULAR INTERÉS
    # ==========================================================

    @staticmethod
    def calcular_interes(
        saldo
    ):

        db = SessionLocal()
        saldo = (
            AdquisicionAccionService
            .D(saldo)
        )

        if saldo <= Decimal("0.00"):
            return Decimal("0.00")

        # IMPORTANTE:
        # utilizar el mismo servicio que usa todo
        # el sistema.
        interes = InteresService.calcular_interes(db,saldo)

        return (
            AdquisicionAccionService
            .D(interes)
        )

    # ==========================================================
    # SIMULAR ADQUISICIÓN
    # ==========================================================

    @staticmethod
    def simular_adquisicion(
        db,
        valor_accion,
        periodo_id,
        aporte_enero=Decimal("150.00"),
        aporte_mensual=Decimal("170.00")
    ):

        valor_accion = (
            AdquisicionAccionService
            .D(valor_accion)
        )

        aporte_enero = (
            AdquisicionAccionService
            .D(aporte_enero)
        )

        aporte_mensual = (
            AdquisicionAccionService
            .D(aporte_mensual)
        )

        if valor_accion <= Decimal("0.00"):
            raise Exception(
                "El valor de la acción debe ser mayor a cero."
            )

        periodo_compra = (
            db.query(Periodo)
            .filter(
                Periodo.id == periodo_id
            )
            .first()
        )

        if not periodo_compra:
            raise Exception(
                "No se encontró el período de compra."
            )

        if periodo_compra.cerrado:
            raise Exception(
                "El período seleccionado está cerrado."
            )

        # ======================================================
        # SALDO INICIAL
        # ======================================================

        saldo = valor_accion

        detalle = []

        periodos = (
            AdquisicionAccionService
            .obtener_periodos_historicos(
                db,
                periodo_compra
            )
        )

        # ======================================================
        # RECORRER LOS MESES ANTERIORES
        # ======================================================

        for periodo in periodos:

            saldo_anterior = saldo

            # Enero = 150
            # Desde febrero = 170
            if periodo.mes == 1:
                aporte = aporte_enero
            else:
                aporte = aporte_mensual

            interes = (
                AdquisicionAccionService
                .calcular_interes(
                    saldo_anterior
                )
            )

            saldo = (
                saldo_anterior
                + aporte
                + interes
            ).quantize(
                Decimal("0.01")
            )

            detalle.append({
                "periodo_id": periodo.id,
                "anio": periodo.anio,
                "mes": periodo.mes,
                "saldo_anterior": saldo_anterior,
                "aporte": aporte,
                "interes": interes,
                "saldo": saldo
            })

        # ======================================================
        # TOTAL
        # ======================================================

        aportes = sum(
            (
                x["aporte"]
                for x in detalle
            ),
            Decimal("0.00")
        )

        intereses = sum(
            (
                x["interes"]
                for x in detalle
            ),
            Decimal("0.00")
        )

        cuota_pagar = (
            valor_accion
            + aportes
            + intereses
        ).quantize(
            Decimal("0.01")
        )

        return {
            "valor_accion":valor_accion,
            "aportes": aportes,
            "intereses": intereses,
            "cuota_pagar": cuota_pagar,
            "saldo_final": saldo,
            "periodo_compra": periodo_compra,
            "detalle": detalle
        }


    @staticmethod
    def registrar_adquisicion(
        db,
        socio_id,
        periodo_id,
        valor_accion,
        usuario_id
    ):
        """
        Registra la adquisición de una nueva acción.

        La simulación histórica NO genera movimientos de meses anteriores.

        En el período actual se registra:

            - Una nueva Acción
            - Un préstamo de adquisición cancelado
            - Un Movimiento con:
                * aportes históricos
                * intereses acumulados
                * cuota final
                * amortización
            - Un MovimientoCajaChica de S/ 1.70

        El costo de S/ 1.70 corresponde exclusivamente
        a caja chica y NO se agrega como un nuevo campo
        en Movimiento.
        """

        # ==========================================================
        # NORMALIZAR VALORES
        # ==========================================================

        valor_accion = (
            AdquisicionAccionService.D(valor_accion)
        )

        if valor_accion <= Decimal("0.00"):
            raise Exception(
                "El valor de la acción debe ser mayor a cero."
            )

        # ==========================================================
        # SOCIO
        # ==========================================================

        socio = (
            db.query(Socio)
            .filter(
                Socio.id == socio_id
            )
            .first()
        )

        if not socio:
            raise Exception(
                "No se encontró el socio."
            )

        # ==========================================================
        # PERÍODO
        # ==========================================================

        periodo = (
            db.query(Periodo)
            .filter(
                Periodo.id == periodo_id
            )
            .first()
        )

        if not periodo:
            raise Exception(
                "No se encontró el período."
            )

        if periodo.cerrado:
            raise Exception(
                "El período seleccionado está cerrado."
            )

        # ==========================================================
        # VERIFICAR PERÍODO ABIERTO ACTUAL
        # ==========================================================

        periodo_abierto = (
            db.query(Periodo)
            .filter(
                Periodo.cerrado == False
            )
            .order_by(
                Periodo.anio.desc(),
                Periodo.mes.desc()
            )
            .first()
        )

        if not periodo_abierto:
            raise Exception(
                "No existe un período abierto."
            )

        if periodo_abierto.id != periodo.id:
            raise Exception(
                "La adquisición debe registrarse "
                "en el período abierto actual."
            )

        # ==========================================================
        # SIMULAR ADQUISICIÓN
        # ==========================================================

        resultado = (
            AdquisicionAccionService
            .simular_adquisicion(
                db=db,
                valor_accion=valor_accion,
                periodo_id=periodo_id
            )
        )

        intereses = (
            AdquisicionAccionService.D(
                resultado["intereses"]
            )
        )

        aportes_historicos = (
            AdquisicionAccionService.D(
                resultado["aportes"]
            )
        )

        # ==========================================================
        # CUOTA CALCULADA
        # ==========================================================

        cuota_calculada = (
            AdquisicionAccionService.D(
                resultado["cuota_pagar"]
            )
        )

        # ==========================================================
        # COSTO DE NUEVA ACCIÓN, en futuro desde tabla: configuracion costo_nueva_accion=1.7
        # ==========================================================

        COSTO_NUEVA_ACCION = Decimal("1.70")

        # El costo se agrega después del cálculo matemático
        cuota_final = (
            cuota_calculada +
            COSTO_NUEVA_ACCION
        ).quantize(
            Decimal("0.01")
        )

        # ==========================================================
        # AMORTIZACIÓN
        # ==========================================================

        amortizacion_final = (
            cuota_final -
            intereses
        ).quantize(
            Decimal("0.01")
        )

        if amortizacion_final < Decimal("0.00"):
            amortizacion_final = Decimal("0.00")

        # ==========================================================
        # CREAR NUEVA ACCIÓN
        # ==========================================================
        numero_accion = (
            AdquisicionAccionService
            .generar_numero_accion(
                db,
                socio_id
            )
        )

        print("Número generado:",numero_accion)

        nueva_accion = Accion(
            socio_id=socio_id,
            numero_accion=numero_accion,
            valor=valor_accion,
            estado="ACTIVO"
        )

        db.add(nueva_accion)
        db.flush()

        print(
            "Creé la acción nueva:",
            numero_accion
        )

        # ==========================================================
        # CREAR PRÉSTAMO DE ADQUISICIÓN
        # ==========================================================

        nuevo_prestamo = Prestamo(
            socio_id=socio_id,
            accion_id=nueva_accion.id,
            periodo_id=periodo_id,
            fecha_prestamo=periodo.fecha_inicio,
            monto=cuota_final,
            saldo_actual=Decimal("0.00"),
            saldo_interes=Decimal("0.00"),
            cuota_minima=cuota_final,
            tasa_interes=Decimal("0.01"),
            estado="CANCELADO"
        )

        db.add(nuevo_prestamo)
        db.flush()

        print(
            "Creé el préstamo de adquisición:",
            nuevo_prestamo.monto
        )

        # ==========================================================
        # MOVIMIENTO DE LA ADQUISICIÓN
        # ==========================================================

        movimiento = Movimiento(
            socio_id=socio_id,
            periodo_id=periodo_id,
            accion_id=nueva_accion.id,
            prestamo_id=nuevo_prestamo.id,
            # Aportes históricos acumulados
            aporte=Decimal("0.00"), # no aportes_historicos, # porque al adquirir una accion no se realiza un aporte, solo se calcula para losinteres de periodos anteriores
            # Pago total de la adquisición
            cuota_pagada=cuota_final,
            # Intereses históricos
            interes=intereses,
            # Cuota final - intereses
            amortizacion=amortizacion_final,
            saldo_prestamo=Decimal("0.00"),
            multa=Decimal("0.00"),
            sobre=Decimal("0.00"),
            observacion=(
                "Adquisición de nueva acción. "
                f"Valor S/ {valor_accion:.2f}. "
                f"Aportes acumulados S/ "
                f"{aportes_historicos:.2f}. "
                f"Intereses acumulados S/ "
                f"{intereses:.2f}. "
                f"Cuota calculada S/ "
                f"{cuota_calculada:.2f}. "
                f"Costo nueva acción S/ "
                f"{COSTO_NUEVA_ACCION:.2f}. "
                f"Total cancelado S/ "
                f"{cuota_final:.2f}."
            )
        )

        db.add(movimiento)
        db.flush()

        print(
            "Creé el movimiento:",
            movimiento.id,
            "cuota:",
            movimiento.cuota_pagada
        )

        # ==========================================================
        # CAJA CHICA
        # ==========================================================

        caja_chica = (
            db.query(CajaChica)
            .filter(
                CajaChica.activo == True
            )
            .order_by(
                CajaChica.id.asc()
            )
            .first()
        )

        if not caja_chica:
            raise Exception(
                "No existe una caja chica activa."
            )

        # ==========================================================
        # ACTUALIZAR SALDO DE CAJA CHICA
        # ==========================================================

        saldo_actual = (
            AdquisicionAccionService.D(
                caja_chica.saldo_actual
            )
        )

        nuevo_saldo_caja = (
            saldo_actual +
            COSTO_NUEVA_ACCION
        ).quantize(
            Decimal("0.01")
        )

        caja_chica.saldo_actual = nuevo_saldo_caja

        # ==========================================================
        # REGISTRAR MOVIMIENTO DE CAJA CHICA
        # ==========================================================

        movimiento_caja = MovimientoCajaChica(
            caja_id=caja_chica.id,
            periodo_id=periodo_id,
            tipo="INGRESO",
            concepto="Nueva acción",
            monto=COSTO_NUEVA_ACCION,
            observacion=(
                f"Costo de adquisición de la acción "
                f"{numero_accion}. "
                f"Socio ID: {socio_id}. "
                f"Movimiento adquisición ID: "
                f"{movimiento.id}."
            )
        )

        db.add(movimiento_caja)
        db.flush()

        print(
            "Movimiento caja chica creado:",movimiento_caja.id,
            "monto:",movimiento_caja.monto,
            "nuevo saldo:",caja_chica.saldo_actual
        )

        # ==========================================================
        # RESULTADO
        # ==========================================================

        return {
            "ok": True,

            "socio_id": socio_id,
            "periodo_id": periodo_id,
            "accion_id": nueva_accion.id,
            "numero_accion": numero_accion,
            "prestamo_id": nuevo_prestamo.id,
            "movimiento_id": movimiento.id,
            "movimiento_caja_chica_id": (movimiento_caja.id),
            "valor_accion": valor_accion,
            "aportes_historicos": (aportes_historicos),
            "intereses": intereses,
            "cuota_calculada": (cuota_calculada),
            "costo_nueva_accion": (COSTO_NUEVA_ACCION),
            "total": cuota_final,
            "amortizacion": (amortizacion_final)
        }

    @staticmethod
    def generar_numero_accion(db,socio_id):
        """
        Genera el siguiente número de acción.

        Ejemplos:
            JP03 -> JP04
            JP04 -> JP05

        Si JP04 ya existe, busca JP05, luego JP06, etc.
        """

        acciones = (
            db.query(Accion.numero_accion)
            .filter(
                Accion.numero_accion.isnot(None)
            )
            .all()
        )

        numeros_usados = set()

        # 1. Corrección de la consulta del prefijo
        prefijo = (
            db.query(
                func.substr(Accion.numero_accion, 1, 2) # Cambiado a (1, 2) para obtener exactamente 2 letras
            )
            .filter(
                Accion.socio_id == socio_id,
                Accion.numero_accion.isnot(None) # Filtro de seguridad
            )
            .limit(1)  # <-- Esto le dice a SQL que solo tome la primera fila encontrada
            .scalar() # Eliminamos .first() para que use solo .scalar() y traiga el string directo
        )

        print("Prefijo:", prefijo)

        # Control de seguridad por si el socio no tiene acciones previas todavía
        if not prefijo:
            prefijo = "BK"  # Puedes asignar un prefijo por defecto aquí si está vacío

        numeros_usados = set()

        for (numero_accion,) in acciones:

            if not numero_accion:
                continue

            numero_accion = str(numero_accion).strip().upper()

            # Captura JP03, JP04, JP100, etc.
            match = re.match(r"^([A-Z]+)(\d+)$", numero_accion)

            if not match:
                continue

            prefijo_actual = match.group(1)
            numero = int(match.group(2))

            # Trabajamos con el mismo prefijo
            if prefijo_actual == prefijo:
                numeros_usados.add(numero)

        # Empezamos desde 1 si no existe ninguna
        siguiente = 1

        if numeros_usados:
            siguiente = max(numeros_usados) + 1

        # Verificación adicional:
        # si JP04 ya existe, busca JP05, etc.
        while True:

            numero_generado = f"{prefijo}{siguiente:02d}"

            existe = (
                db.query(Accion.id)
                .filter(
                    Accion.numero_accion == numero_generado
                )
                .first()
            )

            if not existe:
                return numero_generado

            siguiente += 1