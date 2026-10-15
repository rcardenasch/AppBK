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
    // MOVIMIENTOS
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
    // PRÉSTAMOS DEL PERÍODO
    // =========================================================

    function obtenerPrestamosPeriodo(periodoId) {

        return redondear(
            SIM.prestamos
                .filter(function (p) {

                    return Number(p.periodo_id) === Number(periodoId);

                })
                .reduce(function (total, p) {

                    return total + numero(p.monto);

                }, 0)
        );
    }


    // =========================================================
    // MULTA DEL PERÍODO ANTERIOR
    //
    // La multa anterior forma parte de la deuda para
    // calcular el interés del período actual.
    // =========================================================

    function obtenerMultaAnterior(movimientos, indice) {

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
    // IMPORTANTE:
    // No usamos el saldo del movimiento actual.
    // Se toma el saldo calculado del período anterior.
    // =========================================================

    function obtenerSaldoApertura(
        movimientos,
        indice,
        resultados
    ) {

        if (indice <= 0) {

            return 0;
        }

        return redondear(
            resultados[indice - 1].saldo
        );
    }


    // =========================================================
    // CALCULAR UN PERÍODO
    // =========================================================

    function calcularPeriodo(
        movimientos,
        indice,
        resultados
    ) {

        const m = movimientos[indice];

        const aporte = redondear(
            numero($("#simAporte").val())
        );

        const tasa = redondear(
            numero($("#simTasa").val()) / 100
        );


        // -----------------------------------------------------
        // SALDO ANTERIOR
        // -----------------------------------------------------

        const saldoApertura =
            obtenerSaldoApertura(
                movimientos,
                indice,
                resultados
            );


        // -----------------------------------------------------
        // MULTA DEL PERÍODO ANTERIOR
        // -----------------------------------------------------

        const multaAnterior =
            obtenerMultaAnterior(
                movimientos,
                indice
            );


        // -----------------------------------------------------
        // PRÉSTAMOS NUEVOS
        // -----------------------------------------------------

        const prestamosNuevos =
            obtenerPrestamosPeriodo(
                m.periodo_id
            );


        // -----------------------------------------------------
        // DEUDA PARA INTERÉS
        //
        // REGLA DEL SISTEMA:
        //
        // saldo préstamo
        // + multa anterior
        // + préstamos nuevos
        // -----------------------------------------------------

        const baseInteres =
            redondear(
                saldoApertura +
                multaAnterior +
                prestamosNuevos
            );


        // -----------------------------------------------------
        // INTERÉS
        // -----------------------------------------------------

        const interes =
            redondear(
                baseInteres * tasa
            );


        // -----------------------------------------------------
        // CUOTA SIMULADA
        //
        // Al cargar inicialmente usamos la cuota real.
        // El usuario puede modificarla.
        // -----------------------------------------------------

        const cuota =
            redondear(
                m._cuotaSimulada !== undefined
                    ? m._cuotaSimulada
                    : m.cuota
            );


        // -----------------------------------------------------
        // DEUDA TOTAL
        // -----------------------------------------------------

        const deudaTotal =
            redondear(
                baseInteres +
                interes
            );


        // -----------------------------------------------------
        // CUOTA MÍNIMA
        //
        // REGLA:
        //
        // aporte
        // + interés
        // + multa anterior
        // -----------------------------------------------------

        const cuotaMinima =
            redondear(
                aporte +
                interes +
                multaAnterior
            );


        // -----------------------------------------------------
        // AMORTIZACIÓN
        //
        // Primero se paga la multa anterior.
        // Lo restante de la cuota va a capital.
        //
        // Ejemplo:
        //
        // multa = 50
        // cuota = 220.50
        // aporte = 170
        // interés = 0.50
        //
        // cuota:
        // 170 + 0.50 + 50 = 220.50
        //
        // amortización:
        // 220.50 - 170 - 0.50 = 50
        //
        // capital amortizado = 0
        // -----------------------------------------------------

        const disponibleDespuesAporteInteres =
            redondear(
                cuota -
                aporte -
                interes
            );


        const multaPagada =
            Math.min(
                Math.max(
                    disponibleDespuesAporteInteres,
                    0
                ),
                multaAnterior
            );


        const amortizacionCapital =
            Math.max(
                redondear(
                    disponibleDespuesAporteInteres -
                    multaPagada
                ),
                0
            );


        // -----------------------------------------------------
        // NO PERMITIR AMORTIZAR MÁS CAPITAL DEL DISPONIBLE
        // -----------------------------------------------------

        const capitalDisponible =
            redondear(
                saldoApertura +
                prestamosNuevos
            );


        const amortizacion =
            Math.min(
                amortizacionCapital,
                capitalDisponible
            );


        // -----------------------------------------------------
        // SALDO DEL PRÉSTAMO
        //
        // La multa NO queda nuevamente sumada aquí si
        // fue pagada en el período.
        // -----------------------------------------------------

        const saldo =
            redondear(
                capitalDisponible -
                amortizacion
            );


        // -----------------------------------------------------
        // VALIDACIÓN
        // -----------------------------------------------------

        const deudaPendiente =
            redondear(
                saldo +
                Math.max(
                    multaAnterior - multaPagada,
                    0
                )
            );


        const cuotaEsperada =
            redondear(
                aporte +
                interes +
                multaAnterior +
                amortizacion
            );


        const diferencia =
            redondear(
                cuota -
                cuotaEsperada
            );


        const correcto =
            Math.abs(diferencia) <= 0.01;


        return {

            periodo: m.periodo,

            periodo_id: m.periodo_id,

            aporte: aporte,

            cuota: cuota,

            cuotaMinima: cuotaMinima,

            interes: interes,

            amortizacion: amortizacion,

            multa: multaAnterior,

            multaPagada: multaPagada,

            sobre: numero(m.sobre),

            prestamos: prestamosNuevos,

            saldo: saldo,

            saldoApertura: saldoApertura,

            deudaTotal: deudaTotal,

            deudaPendiente: deudaPendiente,

            diferencia: diferencia,

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


        // -----------------------------------------------------
        // MUY IMPORTANTE:
        //
        // El primer período parte del saldo real registrado
        // en ese movimiento.
        //
        // Para los siguientes períodos se utiliza el saldo
        // calculado del período anterior.
        // -----------------------------------------------------

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


            resultados.push(resultado);
        }


        // -----------------------------------------------------
        // REDIBUJAR
        // -----------------------------------------------------

        $tbody.empty();


        resultados.forEach(function (resultado) {

            agregarFila(resultado);

        });


        // -----------------------------------------------------
        // EVENTOS DE CUOTA
        // -----------------------------------------------------

        $(".sim-cuota")
            .off("input")
            .on("input", function () {

                const periodoId =
                    Number(
                        $(this).data("periodo-id")
                    );


                const movimiento =
                    movimientos.find(function (m) {

                        return Number(m.periodo_id) ===
                            periodoId;

                    });


                if (!movimiento) {
                    return;
                }


                // IMPORTANTE:
                // Guardamos exactamente lo que escribe
                // el usuario. No usamos toFixed().
                const valor =
                    $(this).val();


                if (valor === "") {

                    movimiento._cuotaSimulada = 0;

                } else {

                    movimiento._cuotaSimulada =
                        numero(valor);

                }


                // El recálculo se hace al terminar de editar.
            });


        $(".sim-cuota")
            .off("change")
            .on("change", function () {

                recalcularSimulador();

            });
    }


    // =========================================================
    // ABRIR SIMULADOR
    // =========================================================

    $("#btnAbrirSimulador").on("click", function () {

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
    // TASA / APORTE
    // =========================================================

    $("#simTasa, #simAporte")
        .on("change", function () {

            recalcularSimulador();

        });


    console.log(
        "Simulador financiero inicializado.",
        SIM
    );

});