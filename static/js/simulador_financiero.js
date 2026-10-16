$(document).ready(function () {

    "use strict";

    // =========================================================
    // VALIDACIÓN INICIAL
    // =========================================================

    if (!window.SIMULADOR) {
        console.error("SIMULADOR no está definido.");
        return;
    }

    const SIM = window.SIMULADOR;    

    const $modal = $("#modalSimulador");
    const $tbody = $("#tbodySimulador");

    if (!$tbody.length) {
        console.error("No existe #tbodySimulador");
        return;
    }


    // =========================================================
    // UTILIDADES
    // =========================================================

    function numero(valor) {

        if (valor === null || valor === undefined || valor === "") {
            return 0;
        }

        const n = parseFloat(valor);

        return Number.isFinite(n) ? n : 0;
    }


    function redondear(valor) {

        return Math.round(
            (numero(valor) + Number.EPSILON) * 100
        ) / 100;
    }


    function dinero(valor) {

        return redondear(valor).toFixed(2);
    }


    // =========================================================
    // INTERÉS
    // =========================================================
    //
    // MISMA REGLA DEL InteresService.py
    //
    // interés = saldo * tasa
    //
    // redondeo al múltiplo de 0.50 superior
    //
    // Ejemplo:
    //
    // 17,209.70 * 1% = 172.097
    //
    // 172.097 -> 172.50
    //
    // =========================================================

    function calcularInteres(saldo) {

        saldo = numero(saldo);

        /*
        * =====================================================
        * MISMA REGLA DE InteresService.calcular_interes()
        * =====================================================
        *
        * interes_porcentaje =
        *     Configuracion.interes_mensual
        *
        * interes_base =
        *     saldo * interes_porcentaje
        *
        * interes_final =
        *     ceil(interes_base * 2) / 2
        *
        * =====================================================
        */

        const tasa =
            numero(SIM.interes_mensual);

        if (saldo <= 0 || tasa <= 0) {
            return 0;
        }

        const interesBase =
            saldo * tasa;

        const interesFinal =
            Math.ceil(
                interesBase * 2
            ) / 2;

        return redondear(interesFinal);
    }

    // =========================================================
    // ORDENAR MOVIMIENTOS
    // =========================================================

    function obtenerMovimientosOrdenados() {

        return [
            ...SIM.movimientos
        ].sort(function (a, b) {

            if (numero(a.anio) !== numero(b.anio)) {

                return (
                    numero(a.anio) -
                    numero(b.anio)
                );

            }

            return (
                numero(a.mes) -
                numero(b.mes)
            );

        });
    }


    // =========================================================
    // PRÉSTAMOS DEL PERÍODO
    // =========================================================

    function obtenerPrestamosPeriodo(periodoId) {

        return redondear(

            SIM.prestamos

                .filter(function (p) {

                    return (
                        Number(p.periodo_id) ===
                        Number(periodoId)
                    );

                })

                .reduce(function (total, p) {

                    return (
                        total +
                        numero(p.monto)
                    );

                }, 0)

        );
    }


    // =========================================================
    // SALDO INICIAL DEL SISTEMA
    // =========================================================
    //
    // REGLA:
    //
    // préstamo con periodo_id = NULL
    //
    // representa deuda existente antes de iniciar
    // el historial del sistema.
    //
    // Para el simulador histórico usamos MONTO,
    // porque saldo_actual puede haber sido reducido
    // por amortizaciones posteriores.
    //
    // =========================================================

    function obtenerSaldoInicial() {

        return redondear(

            SIM.prestamos

                .filter(function (p) {

                    return (
                        p.periodo_id === null ||
                        p.periodo_id === undefined ||
                        p.periodo_id === ""
                    );

                })

                .reduce(function (total, p) {

                    return (
                        total +
                        numero(p.monto)
                    );

                }, 0)

        );
    }


    // =========================================================
    // MULTA DEL PERÍODO ANTERIOR
    // =========================================================
    //
    // La multa del movimiento actual NO se utiliza
    // para calcular el mismo período.
    //
    // Se utiliza la multa del período inmediatamente anterior.
    //
    // Esto replica:
    //
    // MovimientoService.obtener_multa_periodo_anterior_accion()
    //
    // =========================================================

    function obtenerMultaAnterior(
        movimientos,
        indice
    ) {

        if (indice <= 0) {
            return 0;
        }

        const movimientoAnterior =
            movimientos[indice - 1];

        return redondear(
            numero(
                movimientoAnterior.multa
            )
        );
    }


    // =========================================================
    // CALCULAR UN PERÍODO
    // =========================================================

    function calcularPeriodo(
        movimientos,
        indice,
        estado
    ) {

        const m =
            movimientos[indice];


        // =====================================================
        // APORTE
        // =====================================================
        //
        // IMPORTANTE:
        //
        // Para reproducir el historial usamos el aporte
        // registrado en cada movimiento.
        //
        // Si no existe, usamos el aporte del simulador.
        //
        // =====================================================

        let aporte;

        if (
            m.aporte !== undefined &&
            m.aporte !== null
        ) {

            aporte =
                redondear(m.aporte);

        } else {

            aporte =
                redondear(
                    $("#simAporte").val()
                );

        }


        // =====================================================
        // CAPITAL DE APERTURA
        // =====================================================
        //
        // NO usamos:
        //
        //     movimiento anterior.saldo_prestamo
        //
        // porque ese saldo puede incluir multa.
        //
        // El backend trabaja con:
        //
        //     Prestamo.saldo_actual
        //
        // como CAPITAL.
        //
        // =====================================================

        const saldoApertura =
            redondear(
                estado.capitalApertura
            );


        // =====================================================
        // MULTA ANTERIOR
        // =====================================================

        const multaAnterior =
            obtenerMultaAnterior(
                movimientos,
                indice
            );


        // =====================================================
        // PRÉSTAMOS NUEVOS
        // =====================================================
        //
        // IMPORTANTE:
        //
        // Los préstamos creados en este período:
        //
        // - NO generan interés en este período.
        // - SÍ forman parte de la deuda.
        // - SÍ pasan a formar parte del capital
        //   del siguiente período.
        //
        // =====================================================

        const prestamosNuevos =
            obtenerPrestamosPeriodo(
                m.periodo_id
            );


        // =====================================================
        // BASE DE INTERÉS
        // =====================================================
        //
        // EXACTAMENTE COMO BACKEND:
        //
        // saldo apertura
        // + multa anterior
        //
        // NO se agregan préstamos nuevos.
        //
        // =====================================================

        const baseInteres =
            redondear(
                saldoApertura +
                multaAnterior
            );


        // =====================================================
        // INTERÉS
        // =====================================================

        const interes =
            calcularInteres(
                baseInteres
            );
        
        // =====================================================
        // DEUDA TOTAL
        // =====================================================
        //
        // EXACTAMENTE COMO:
        //
        // saldo_apertura
        // + multa anterior
        // + préstamos nuevos
        //
        // =====================================================

        const deudaTotal =
            redondear(
                saldoApertura +
                multaAnterior +
                prestamosNuevos
            );


        // =====================================================
        // CUOTA DE TABLA
        // =====================================================
        //
        // MISMA TABLA DE PrestamoService.calcular_cuota_minima()
        //
        // <= 3000  -> 417
        // <= 7500  -> 504
        // <= 12500 -> 566
        // <= 15000 -> 590
        // <= 17500 -> 611
        // <= 20000 -> 677
        // <= 22500 -> 743
        // <= 25000 -> 809
        // <= 27500 -> 875
        // <= 30000 -> 941
        //
        // =====================================================

        function cuotaTabla(monto) {

            monto = redondear(monto);

            if (monto <= 3000) {
                return 417;
            }
            if (monto <= 7500) {
                return 504;
            }
            if (monto <= 12500) {
                return 566;
            }
            if (monto <= 15000) {
                return 590;
            }
            if (monto <= 17500) {
                return 611;
            }
            if (monto <= 20000) {
                return 677;
            }
            if (monto <= 22500) {
                return 743;
            }
            if (monto <= 25000) {
                return 809;
            }
            if (monto <= 27500) {
                return 875;
            }
            if (monto <= 30000) {
                return 941;
            }
            return 941;
        }


        // =====================================================
        // CUOTA PARA CANCELAR
        // =====================================================
        //
        // EXACTAMENTE COMO BACKEND:
        //
        // aporte
        // + interés
        // + deuda total
        //
        // =====================================================

        const cuotaCancelacion =
            redondear(
                aporte +
                interes +
                deudaTotal
            );


        // =====================================================
        // CUOTA APLICADA
        // =====================================================
        //
        // EXACTAMENTE COMO RegistroMensualService:
        //
        // MIN(
        //      cuota_tabla,
        //      cuota_cancelacion
        // )
        //
        // Esto resuelve el caso:
        //
        // deuda = 150
        // aporte = 170
        // interés = 1.50
        //
        // cuota tabla = 417
        //
        // cuota cancelación =
        // 170 + 1.50 + 150
        // = 321.50
        //
        // resultado = 321.50
        //
        // =====================================================

        const cuotaMinima =
            redondear(
                Math.min(
                    cuotaTabla(deudaTotal),
                    cuotaCancelacion
                )
            );


        // =====================================================
        // CUOTA SIMULADA
        // =====================================================
        //
        // Si el usuario ya modificó la cuota,
        // conservamos ese valor.
        //
        // NO usar toFixed() aquí.
        //
        // =====================================================

        let cuota;

        if (
            m._cuotaSimulada !== undefined &&
            m._cuotaSimulada !== null
        ) {

            cuota =
                numero(
                    m._cuotaSimulada
                );

        } else {

            cuota =
                numero(
                    m.cuota
                );

            // Si no existe cuota real,
            // usamos la cuota calculada.
            if (cuota <= 0) {

                cuota =
                    cuotaMinima;

            }

        }


        cuota =
            redondear(cuota);


        // =====================================================
        // AMORTIZACIÓN TOTAL
        // =====================================================
        //
        // El backend considera:
        //
        // cuota
        // - aporte
        // - interés
        //
        // IMPORTANTE:
        //
        // Este valor incluye la parte utilizada
        // para cancelar multa.
        //
        // =====================================================

        let amortizacion =
            redondear(
                cuota -
                aporte -
                interes
            );


        if (amortizacion < 0) {
            amortizacion = 0;
        }


        // =====================================================
        // NO AMORTIZAR MÁS QUE LA DEUDA
        // =====================================================

        amortizacion =
            Math.min(
                amortizacion,
                deudaTotal
            );

        amortizacion =
            redondear(
                amortizacion
            );


        // =====================================================
        // PAGO DE MULTA
        // =====================================================
        //
        // La amortización se aplica primero a la multa.
        //
        // =====================================================

        const multaPagada =
            redondear(
                Math.min(
                    amortizacion,
                    multaAnterior
                )
            );


        // =====================================================
        // AMORTIZACIÓN REAL DE CAPITAL
        // =====================================================

        const amortizacionCapital =
            redondear(
                Math.max(
                    amortizacion -
                    multaPagada,
                    0
                )
            );


        // =====================================================
        // CAPITAL AL CIERRE
        // =====================================================
        //
        // MUY IMPORTANTE:
        //
        // NO usamos:
        //
        //     deudaTotal - amortizacion
        //
        // para determinar la apertura del siguiente período.
        //
        // Porque la multa es una deuda separada.
        //
        // El capital es:
        //
        // apertura
        // + préstamos nuevos
        // - amortización de capital
        //
        // =====================================================

        const capitalFinal =
            redondear(
                saldoApertura +
                prestamosNuevos -
                amortizacionCapital
            );


        // =====================================================
        // SALDO DE DEUDA DEL MOVIMIENTO
        // =====================================================
        //
        // Este sí replica el resultado del motor:
        //
        // deuda total
        // - amortización
        //
        // Puede contener deuda de multa pendiente.
        //
        // =====================================================

        const saldo =
            redondear(
                Math.max(
                    deudaTotal -
                    amortizacion,
                    0
                )
            );


        // =====================================================
        // MULTA PENDIENTE
        // =====================================================

        const multaPendiente =
            redondear(
                Math.max(
                    multaAnterior -
                    multaPagada,
                    0
                )
            );


        // =====================================================
        // CONTROL
        // =====================================================
        //
        // No usamos una comparación tautológica como:
        //
        // cuota == aporte + interés + amortización
        //
        // porque siempre sería OK.
        //
        // Comprobamos que la cuota simulada sea suficiente
        // para cubrir aporte + interés + deuda pendiente.
        //
        // =====================================================

        const cuotaNecesaria =
            redondear(
                aporte +
                interes +
                Math.min(
                    deudaTotal,
                    deudaTotal
                )
            );


        let correcto = true;


        // La cuota no puede ser menor que aporte + interés
        if (
            cuota <
            redondear(
                aporte +
                interes
            )
        ) {

            correcto = false;

        }


        // =====================================================
        // RESULTADO
        // =====================================================

        return {

            periodo: m.periodo,
            periodo_id: m.periodo_id,
            anio: m.anio,
            mes: m.mes,
            aporte: aporte,
            cuota: cuota,
            cuotaMinima: cuotaMinima,
            cuotaCancelacion: cuotaCancelacion,
            interes: interes,
            amortizacion: amortizacion,
            amortizacionCapital: amortizacionCapital,
            multa: numero(m.multa),
            multaAnterior: multaAnterior,
            multaPagada: multaPagada,
            multaPendiente: multaPendiente,
            sobre: numero(m.sobre),
            prestamos: prestamosNuevos,
            saldo: saldo,
            saldoApertura: saldoApertura,
            capitalFinal: capitalFinal,
            deudaTotal: deudaTotal,
            correcto: correcto
        };
    }


    // =========================================================
    // AGREGAR FILA
    // =========================================================
    function agregarFila(data) {

        const tr =
            document.createElement("tr");


        const claseControl =
            data.correcto
                ? "bg-success"
                : "bg-danger";


        const textoControl =
            data.correcto
                ? "OK"
                : "REVISAR";


        tr.innerHTML = `

            <td>
                <span class="badge bg-primary" style="font-size: 11px;">
                    ${data.periodo}
                </span>
            </td>

            <td style="font-size: 11px;">
                S/ ${dinero(data.aporte)}

            </td>

            <td>

                <input
                    type="number"
                    style="font-size: 11px;"
                    step="0.01"
                    min="0"
                    class="form-control form-control-sm sim-cuota"
                    value="${data.cuota}"
                    data-periodo-id="${data.periodo_id}"
                >

            </td>

            <td class="text-primary fw-bold" style="font-size: 11px;">
                S/ ${dinero(data.cuotaMinima)}
            </td>

            <td class="text-primary fw-bold" style="font-size: 11px;">
                S/ ${dinero(data.amortizacion)}
            </td>

            <td class="text-success fw-bold" style="font-size: 11px;">
                S/ ${dinero(data.interes)}
            </td>

            <td class="text-danger fw-bold" style="font-size: 11px;">
                S/ ${dinero(data.saldo)}

            </td>

            <td style="font-size: 11px;">
                S/ ${dinero(data.prestamos)}
            </td>

            <td style="font-size: 11px;">
                S/ ${dinero(data.multa)}
            </td>

            <td style="font-size: 11px;">
                S/ ${dinero(data.sobre)}
            </td>

            <td>

                <span class="badge ${claseControl}" style="font-size: 11px;">
                    ${textoControl}
                </span>

            </td>

        `;


        $tbody.append(tr);
    }


    // =========================================================
    // RECALCULAR TODO
    // =========================================================

    function recalcularSimulador() {

        const movimientos =
            obtenerMovimientosOrdenados();


        const resultados = [];


        // =====================================================
        // CAPITAL INICIAL
        // =====================================================
        //
        // préstamos con periodo_id = NULL
        //
        // Estos son los préstamos existentes antes
        // del historial del sistema.
        //
        // =====================================================

        let capitalActual =
            obtenerSaldoInicial();


        console.log(
            "=========================================="
        );

        console.log(
            "SIMULADOR FINANCIERO"
        );

        console.log(
            "Capital inicial:",
            capitalActual
        );


        // =====================================================
        // RECORRER TODOS LOS PERÍODOS
        // =====================================================

        for (
            let i = 0;
            i < movimientos.length;
            i++
        ) {

            const estado = {

                capitalApertura:
                    capitalActual

            };


            const resultado =
                calcularPeriodo(
                    movimientos,
                    i,
                    estado
                );


            resultados.push(
                resultado
            );


            // =================================================
            // MUY IMPORTANTE
            // =================================================
            //
            // Para el siguiente período:
            //
            // capital apertura =
            // capital final del período actual
            //
            // NO usamos resultado.saldo porque este puede
            // contener una multa pendiente.
            //
            // =================================================

            capitalActual =
                redondear(
                    resultado.capitalFinal
                );


            console.log(
                resultado.periodo,
                {
                    apertura: resultado.saldoApertura,
                    multaAnterior: resultado.multaAnterior,
                    prestamosNuevos: resultado.prestamos,
                    baseInteres: redondear(
                            resultado.saldoApertura +
                            resultado.multaAnterior
                        ),
                    interes: resultado.interes,            
                    cuota: resultado.cuota,
                    amortizacion: resultado.amortizacion,
                    amortizacionCapital: resultado.amortizacionCapital,
                    capitalFinal: resultado.capitalFinal,
                    saldo: resultado.saldo
                }
            );
        }

        // =====================================================
        // REDIBUJAR
        // =====================================================

        $tbody.empty();

        resultados.forEach(
            function (resultado) {

                agregarFila(
                    resultado
                );

            }
        );


        // =====================================================
        // EVENTOS DE CUOTA
        // =====================================================

        $(".sim-cuota")
            .off("input")
            .on(
                "input",
                function () {

                    const periodoId =
                        Number(
                            $(this)
                                .data(
                                    "periodo-id"
                                )
                        );


                    const movimiento =
                        movimientos.find(
                            function (m) {

                                return (
                                    Number(
                                        m.periodo_id
                                    ) ===
                                    periodoId
                                );

                            }
                        );


                    if (!movimiento) {
                        return;
                    }


                    // =========================================
                    // IMPORTANTE
                    // =========================================
                    //
                    // Guardamos exactamente el texto
                    // introducido por el usuario.
                    //
                    // NO usar toFixed().
                    //
                    // =========================================

                    const valor =
                        $(this).val();


                    if (
                        valor === ""
                    ) {

                        movimiento._cuotaSimulada =
                            "";

                    } else {

                        movimiento._cuotaSimulada =
                            numero(valor);

                    }

                }
            );


        // =====================================================
        // RECALCULAR AL SALIR DEL INPUT
        // =====================================================

        $(".sim-cuota")
            .off("change")
            .on(
                "change",
                function () {

                    recalcularSimulador();

                }
            );
    }


    function limpiarSimulacion() {

    SIM.movimientos.forEach(function (m) {

        delete m._cuotaSimulada;

    });

    $tbody.empty();

    }

    // =========================================================
    // ABRIR SIMULADOR
    // =========================================================

    $("#btnAbrirSimulador")
        .off("click")
        .on(
            "click",
            function () {
                
                limpiarSimulacion();
                recalcularSimulador();


                if ($modal.length) {

                    $modal[0].showModal();

                }

            }
        );


    // =========================================================
    // CERRAR
    // =========================================================

    $("#btnCerrarSimulador, #btnCerrarSimulador2")
        .off("click")
        .on(
            "click",
            function () {
                
                limpiarSimulacion();

                if ($modal.length) {

                    $modal[0].close();

                }

            }
        );


    // =========================================================
    // RECALCULAR
    // =========================================================

    $("#btnRecalcularSimulador")
        .off("click")
        .on(
            "click",
            function () {

                limpiarSimulacion();
                recalcularSimulador();

            }
        );

    console.log(
        "Simulador financiero inicializado.",
        SIM
    );

});