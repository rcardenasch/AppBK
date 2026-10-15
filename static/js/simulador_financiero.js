$(document).ready(function () {

    "use strict";

    // =========================================================
    // VALIDACIÓN
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
    // CONSTANTES
    // =========================================================

    const CENTAVOS = 0.01;


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
    // REDONDEO DEL INTERÉS
    //
    // MISMA REGLA QUE InteresService:
    //
    // interés = saldo * tasa
    // redondeado al múltiplo de S/ 0.50 superior.
    //
    // Ejemplo:
    //
    // 172.09 -> 172.50
    // 172.50 -> 172.50
    // 172.51 -> 173.00
    // =========================================================

    function calcularInteres(saldo, tasa) {

        saldo = redondear(saldo);
        tasa = numero(tasa);

        if (saldo <= 0) {
            return 0;
        }

        const interesBase = saldo * tasa;

        const interes = (
            Math.ceil(
                interesBase * 2 - 1e-10
            ) / 2
        );

        return redondear(interes);

    }


    // =========================================================
    // ORDENAR MOVIMIENTOS
    // =========================================================

    function obtenerMovimientosOrdenados() {

        return [...SIM.movimientos].sort(function (a, b) {

            if (a.anio !== b.anio) {
                return a.anio - b.anio;
            }

            return a.mes - b.mes;

        });

    }


    // =========================================================
    // PRÉSTAMOS INICIALES
    //
    // periodo_id = NULL
    //
    // IMPORTANTE:
    //
    // Para un préstamo inicial utilizamos MONTO,
    // no saldo_actual.
    //
    // saldo_actual puede haber sido modificado por
    // amortizaciones posteriores.
    //
    // El monto representa la deuda inicial con la
    // que comienza el historial.
    // =========================================================

    function obtenerPrestamosIniciales() {

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
    // PRÉSTAMOS NUEVOS DEL PERÍODO
    //
    // Solo los préstamos cuyo periodo_id coincide
    // con el período que estamos simulando.
    // =========================================================

    function obtenerPrestamosPeriodo(periodoId) {

        if (
            periodoId === null ||
            periodoId === undefined
        ) {
            return 0;
        }

        return redondear(

            SIM.prestamos

                .filter(function (p) {

                    return (
                        p.periodo_id !== null &&
                        p.periodo_id !== undefined &&
                        Number(p.periodo_id) === Number(periodoId)
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
    //
    // La multa se genera en el período anterior
    // y se cobra en el período actual.
    //
    // NO se utiliza la multa del mismo período.
    // =========================================================

    function obtenerMultaAnterior(
        movimientos,
        indice
    ) {

        if (indice <= 0) {
            return 0;
        }

        return redondear(
            movimientos[indice - 1].multa
        );

    }


    // =========================================================
    // SALDO DE APERTURA
    //
    // REGLA:
    //
    // PRIMER PERÍODO:
    //   saldo inicial = préstamos con periodo_id NULL
    //
    // SIGUIENTES:
    //   saldo inicial = saldo final calculado
    //   del período anterior.
    //
    // IMPORTANTE:
    // Los préstamos del período actual NO se meten
    // aquí. Se agregan después como préstamos nuevos.
    // =========================================================

    function obtenerSaldoApertura(
        movimientos,
        indice,
        resultados
    ) {

        // -----------------------------------------------------
        // PRIMER PERÍODO
        // -----------------------------------------------------

        if (indice === 0) {

            return obtenerPrestamosIniciales();

        }


        // -----------------------------------------------------
        // SIGUIENTES PERÍODOS
        // -----------------------------------------------------

        return redondear(
            resultados[indice - 1].saldo
        );

    }


    // =========================================================
    // CALCULAR PERÍODO
    // =========================================================

    function calcularPeriodo(
        movimientos,
        indice,
        resultados
    ) {

        const m = movimientos[indice];


        // =====================================================
        // APORTE
        // =====================================================

        const aporte = redondear(
            numero($("#simAporte").val())
        );


        // =====================================================
        // TASA
        //
        // El HTML muestra 1.0 (%)
        // El motor trabaja con 0.01
        // =====================================================

        const tasa = (
            numero($("#simTasa").val()) / 100
        );


        // =====================================================
        // SALDO DE APERTURA
        // =====================================================

        const saldoApertura = obtenerSaldoApertura(
            movimientos,
            indice,
            resultados
        );


        // =====================================================
        // MULTA DEL PERÍODO ANTERIOR
        // =====================================================

        const multaAnterior = obtenerMultaAnterior(
            movimientos,
            indice
        );


        // =====================================================
        // PRÉSTAMOS NUEVOS
        // =====================================================

        const prestamosNuevos = obtenerPrestamosPeriodo(
            m.periodo_id
        );


        // =====================================================
        // BASE PARA INTERÉS
        //
        // EXACTAMENTE IGUAL AL BACKEND
        //
        // saldo apertura
        // + multa período anterior
        //
        // NO incluye préstamo nuevo del período actual.
        // =====================================================

        const baseInteres = redondear(
            saldoApertura +
            multaAnterior
        );


        // =====================================================
        // INTERÉS
        //
        // Usa redondeo al múltiplo de S/ 0.50 superior.
        // =====================================================

        const interes = calcularInteres(
            baseInteres,
            tasa
        );


        // =====================================================
        // CUOTA SIMULADA
        //
        // IMPORTANTE:
        // No utilizar toFixed() aquí.
        //
        // El usuario debe poder escribir:
        //
        // 7
        // 74
        // 743
        // 743.50
        // borrar
        // etc.
        // =====================================================

        let cuota;

        if (
            m._cuotaSimulada !== undefined &&
            m._cuotaSimulada !== null
        ) {

            cuota = numero(
                m._cuotaSimulada
            );

        } else {

            cuota = numero(
                m.cuota
            );

        }

        cuota = redondear(cuota);


        // =====================================================
        // DEUDA TOTAL
        //
        // EXACTAMENTE COMO BACKEND:
        //
        // saldo apertura
        // + multa anterior
        // + préstamos nuevos
        // =====================================================

        const deudaTotal = redondear(
            saldoApertura +
            multaAnterior +
            prestamosNuevos
        );


        // =====================================================
        // AMORTIZACIÓN
        //
        // REGLA REAL DEL SISTEMA:
        //
        // cuota
        // - aporte
        // - interés
        //
        // IMPORTANTE:
        //
        // Aquí NO restamos nuevamente la multa.
        //
        // Si la cuota paga una multa, esa parte
        // está incluida dentro de la amortización
        // registrada del movimiento.
        //
        // Ejemplo:
        //
        // saldo      = 150
        // multa      = 50
        // interés    = 1.50
        // aporte     = 170
        // cuota      = 221.50
        //
        // amortización = 221.50 - 170 - 1.50
        //               = 50.00
        //
        // Si la deuda total es 200:
        //
        // 150 capital
        // 50 multa
        //
        // se cancela toda la deuda.
        // =====================================================

        let amortizacion = redondear(
            cuota -
            aporte -
            interes
        );


        if (amortizacion < 0) {
            amortizacion = 0;
        }


        // =====================================================
        // LIMITAR AMORTIZACIÓN A LA DEUDA REAL
        // =====================================================

        amortizacion = Math.min(
            amortizacion,
            deudaTotal
        );

        amortizacion = redondear(
            amortizacion
        );


        // =====================================================
        // SALDO FINAL
        //
        // El saldo del movimiento incluye:
        //
        // capital
        // + multa anterior
        // + préstamo nuevo
        //
        // menos amortización.
        // =====================================================

        const saldo = redondear(
            deudaTotal -
            amortizacion
        );


        // =====================================================
        // MULTA PAGADA
        //
        // Solo informativo para la simulación.
        //
        // La multa del período actual NO se paga
        // en este mismo período.
        // =====================================================

        const importeDisponibleParaDeuda = Math.max(
            redondear(
                cuota -
                aporte -
                interes
            ),
            0
        );


        const multaPagada = Math.min(
            importeDisponibleParaDeuda,
            multaAnterior
        );


        // =====================================================
        // CAPITAL AMORTIZADO
        //
        // Solo informativo.
        //
        // No reemplaza amortización porque el movimiento
        // guarda la amortización total.
        // =====================================================

        const capitalAmortizado = Math.max(
            redondear(
                amortizacion -
                multaPagada
            ),
            0
        );


        // =====================================================
        // CUOTA MÍNIMA
        //
        // AQUÍ HACEMOS LA DISTINCIÓN:
        //
        // La cuota necesaria para cubrir:
        //
        // aporte
        // + interés
        // + multa anterior
        //
        // es la cuota mínima de ese período.
        //
        // Si la deuda de capital es menor y la cuota
        // mínima de cancelación es inferior, se debe
        // utilizar el importe de cancelación.
        // =====================================================

        const cuotaBase = redondear(
            aporte +
            interes +
            multaAnterior
        );


        const cuotaCancelacion = redondear(
            aporte +
            interes +
            deudaTotal
        );


        // =====================================================
        // CUOTA MÍNIMA REAL
        //
        // Para mantener la lógica de RegistroMensualService:
        //
        // MIN(cuota calculada por tabla, cuota cancelación)
        //
        // Pero aquí usamos la cuota de cancelación solamente
        // cuando corresponde a una deuda que puede cancelarse.
        //
        // Como el simulador debe mostrar lo que actualmente
        // está registrado, la columna se mantiene como
        // referencia de la cuota necesaria.
        // =====================================================

        let cuotaMinima = cuotaBase;

        if (
            deudaTotal > 0 &&
            cuotaCancelacion < cuotaMinima
        ) {

            cuotaMinima = cuotaCancelacion;

        }

        cuotaMinima = redondear(
            cuotaMinima
        );


        // =====================================================
        // CONTROL
        //
        // La cuota esperada según el motor real es:
        //
        // aporte + interés + amortización
        //
        // NO agregamos multa nuevamente porque la multa
        // ya está incluida dentro de amortización.
        // =====================================================

        const cuotaEsperada = redondear(
            aporte +
            interes +
            amortizacion
        );


        const diferencia = redondear(
            cuota -
            cuotaEsperada
        );


        const correcto = (
            Math.abs(diferencia) <= 0.01
        );


        // =====================================================
        // RESULTADO
        // =====================================================

        return {

            periodo: m.periodo,

            periodo_id: m.periodo_id,

            aporte: aporte,

            cuota: cuota,

            cuotaMinima: cuotaMinima,

            interes: interes,

            amortizacion: amortizacion,

            saldo: saldo,

            saldoApertura: saldoApertura,

            multa: multaAnterior,

            multaPagada: multaPagada,

            capitalAmortizado: capitalAmortizado,

            sobre: numero(m.sobre),

            prestamos: prestamosNuevos,

            deudaTotal: deudaTotal,

            diferencia: diferencia,

            correcto: correcto

        };

    }


    // =========================================================
    // AGREGAR FILA
    // =========================================================

    function agregarFila(data) {

        const tr = document.createElement("tr");


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
                <span class="badge bg-primary">
                    ${data.periodo}
                </span>
            </td>

            <td>
                S/ ${dinero(data.aporte)}
            </td>

            <td>

                <input
                    type="number"
                    step="0.01"
                    min="0"
                    class="form-control form-control-sm sim-cuota"
                    value="${data.cuota}"
                    data-periodo-id="${data.periodo_id}"
                >

            </td>

            <td class="text-primary fw-bold">
                S/ ${dinero(data.cuotaMinima)}
            </td>

            <td class="text-primary fw-bold">
                S/ ${dinero(data.amortizacion)}
            </td>

            <td class="text-success fw-bold">
                S/ ${dinero(data.interes)}
            </td>

            <td class="text-danger fw-bold">
                S/ ${dinero(data.saldo)}
            </td>

            <td>
                S/ ${dinero(data.prestamos)}
            </td>

            <td>
                S/ ${dinero(data.multa)}
            </td>

            <td>
                S/ ${dinero(data.sobre)}
            </td>

            <td>

                <span class="badge ${claseControl}">
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
        // RECORRER TODOS LOS PERÍODOS
        // =====================================================

        for (
            let i = 0;
            i < movimientos.length;
            i++
        ) {

            const resultado =
                calcularPeriodo(
                    movimientos,
                    i,
                    resultados
                );


            resultados.push(
                resultado
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
            .on("input", function () {

                const periodoId =
                    $(this).attr(
                        "data-periodo-id"
                    );


                const movimiento =
                    movimientos.find(
                        function (m) {

                            return String(
                                m.periodo_id
                            ) === String(
                                periodoId
                            );

                        }
                    );


                if (!movimiento) {
                    return;
                }


                // =================================================
                // IMPORTANTE
                //
                // NO toFixed()
                //
                // Guardamos el texto convertido a número.
                // Esto permite escribir:
                //
                // 7
                // 74
                // 743
                // 743.50
                // borrar
                // =================================================

                const valor =
                    $(this).val();


                if (valor === "") {

                    movimiento._cuotaSimulada = 0;

                } else {

                    movimiento._cuotaSimulada =
                        numero(valor);

                }

            });


        // =====================================================
        // RECALCULAR AL SALIR DEL INPUT
        // =====================================================

        $(".sim-cuota")
            .off("change")
            .on("change", function () {

                recalcularSimulador();

            });

    }


    // =========================================================
    // ABRIR SIMULADOR
    // =========================================================

    $("#btnAbrirSimulador")
        .on("click", function () {

            recalcularSimulador();

            if ($modal.length) {

                $modal[0].showModal();

            }

        });


    // =========================================================
    // CERRAR
    // =========================================================

    $("#btnCerrarSimulador, #btnCerrarSimulador2")
        .on("click", function () {

            if ($modal.length) {

                $modal[0].close();

            }

        });


    // =========================================================
    // RECALCULAR
    // =========================================================

    $("#btnRecalcularSimulador")
        .on("click", function () {

            recalcularSimulador();

        });


    // =========================================================
    // CAMBIAR TASA / APORTE
    // =========================================================

    $("#simTasa, #simAporte")
        .on("change", function () {

            recalcularSimulador();

        });


    // =========================================================
    // INICIALIZAR
    // =========================================================

    console.log(
        "Simulador financiero inicializado.",
        SIM
    );

});