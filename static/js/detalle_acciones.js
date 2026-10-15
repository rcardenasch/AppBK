
    $(document).ready(function () {

        // Contenedor del Modal nativo (<dialog>)
        const $modal = $("#modalEditarMovimiento");

        const $panelCalculoDeuda = $("#panelCalculoDeuda");
        const $btnMostrarCalculo = $("#btnMostrarCalculoDeuda");

        // Mostrar / ocultar el cálculo de deuda
        $btnMostrarCalculo.on("click", function () {

            const estaOculto = $panelCalculoDeuda.hasClass("d-none");

            $panelCalculoDeuda.toggleClass("d-none", !estaOculto);

            $(this).attr("aria-expanded", String(estaOculto));

            $(this).html(
                estaOculto
                    ? '<i class="bi bi-calculator me-1"></i>' +
                    'Ocultar cálculo de deuda ' +
                    '<i class="bi bi-chevron-up ms-1"></i>'
                    : '<i class="bi bi-calculator me-1"></i>' +
                    'Calcular pago / cancelar deuda ' +
                    '<i class="bi bi-chevron-down ms-1"></i>'
            );
        });

        $(document).on("click", ".btn-editar-movimiento", function () {

            const id = $(this).data("id");

            // Ocultar el cálculo cada vez que se abre un movimiento
            $panelCalculoDeuda.addClass("d-none");

            $btnMostrarCalculo
                .attr("aria-expanded", "false")
                .html(
                    '<i class="bi bi-calculator me-1"></i>' +
                    'Calcular pago / cancelar deuda ' +
                    '<i class="bi bi-chevron-down ms-1"></i>'
                );

            $.get(`/movimientos/editar_movimiento/${id}`, function (resp) {

                if (!resp.ok) {
                    alert(resp.mensaje);
                    return;
                }

                const m = resp.movimiento;

                $("#editMovimientoId").val(m.id);

                $("#editAporte").val(
                    Number(m.aporte).toFixed(2)
                );

                $("#editCuota").val(
                    Number(m.cuota_pagada).toFixed(2)
                );

                $("#editMulta").val(
                    Number(m.multa).toFixed(2)
                );

                $("#editSobre").val(
                    Number(m.sobre).toFixed(2)
                );

                $("#editObservacion").val(
                    m.observacion || ""
                );

                // ===============================
                // INFORMACIÓN INICIAL
                // ===============================

                $("#editSaldoApertura").text(
                    "S/ " + Number(m.saldo_apertura).toFixed(2)
                );

                $("#editMultaAnterior").text(
                    "S/ " + Number(m.multa_anterior).toFixed(2)
                );

                $("#editDeudaTotal").text(
                    "S/ " + Number(m.deuda_total).toFixed(2)
                );

                $("#editInteres").text(
                    "S/ " + Number(m.interes).toFixed(2)
                );

                $("#editAmortizacion").text(
                    "S/ " + Number(m.amortizacion).toFixed(2)
                );

                $("#editSaldoNuevo").text(
                    "S/ " + Number(m.saldo_prestamo).toFixed(2)
                );

                actualizarEstadoDeuda(
                    Number(m.saldo_prestamo)
                );

                if ($modal[0]) {
                    $modal[0].showModal();
                }

                // Calcular nuevamente con los valores actuales
                calcularEdicion();

            }).fail(function () {

                alert("No se pudo cargar el movimiento.");

            });

        });
        // =====================================================
        // 2. CANCELAR / CERRAR MODAL
        // =====================================================
        $("#btnCancelarEditarMovimiento").on("click", function () {
            if ($modal[0]) {
                $modal[0].close();
            }
        });

        // Calcular edicion
        function calcularEdicion() {

            const id = $("#editMovimientoId").val();

            if (!id) {
                return;
            }

            const datos = {
                aporte: $("#editAporte").val(),
                cuota_pagada: $("#editCuota").val(),
                multa: $("#editMulta").val(),
                sobre: $("#editSobre").val()
            };

            $.ajax({

                url: `/movimientos/editar_movimiento/${id}/calcular`,
                method: "POST",
                data: datos,
                success: function (resp) {

                    if (!resp.ok) {

                        alert(resp.mensaje);

                        return;
                    }

                    const r = resp.resultado;

                    $("#editSaldoApertura").text(
                        "S/ " + Number(r.saldo_apertura).toFixed(2)
                    );

                    $("#editMultaAnterior").text(
                        "S/ " + Number(r.multa_anterior).toFixed(2)
                    );

                    $("#editDeudaTotal").text(
                        "S/ " + Number(r.deuda_total).toFixed(2)
                    );

                    $("#editInteres").text(
                        "S/ " + Number(r.interes).toFixed(2)
                    );

                    $("#editAmortizacion").text(
                        "S/ " + Number(r.amortizacion).toFixed(2)
                    );

                    $("#editSaldoNuevo").text(
                        "S/ " + Number(r.saldo_nuevo).toFixed(2)
                    );

                    actualizarEstadoDeuda(
                        Number(r.saldo_nuevo)
                    );

                },

                error: function (xhr) {

                    console.error(xhr.responseText);

                }

            });
        }

        // boton págar toda deuda
        $("#btnPagarTodaDeuda").on("click", function () {

            const id = $("#editMovimientoId").val();

            if (!id) {
                alert("Movimiento no identificado.");
                return;
            }

            const boton = $(this);

            boton.prop("disabled", true);

            boton.html(
                '<span class="spinner-border spinner-border-sm"></span> Calculando...'
            );

            $.get(
                `/movimientos/editar_movimiento/${id}/pagar_toda_deuda`,
                function (resp) {

                    if (!resp.ok) {

                        alert(resp.mensaje);

                        return;
                    }

                    const r = resp.resultado;

                    // =========================================
                    // COLOCAR LA CUOTA EXACTA
                    // =========================================

                    $("#editAporte").val(
                        Number(r.aporte).toFixed(2)
                    );

                    $("#editCuota").val(
                        Number(r.cuota_pagar).toFixed(2)
                    );


                    // =========================================
                    // MOSTRAR RESULTADOS
                    // =========================================

                    $("#editSaldoApertura").text(
                        "S/ " + Number(r.saldo_apertura).toFixed(2)
                    );

                    $("#editMultaAnterior").text(
                        "S/ " + Number(r.multa_anterior).toFixed(2)
                    );

                    $("#editDeudaTotal").text(
                        "S/ " + Number(r.deuda_total).toFixed(2)
                    );

                    $("#editInteres").text(
                        "S/ " + Number(r.interes).toFixed(2)
                    );

                    $("#editAmortizacion").text(
                        "S/ " + Number(r.amortizacion).toFixed(2)
                    );

                    $("#editSaldoNuevo").text(
                        "S/ " + Number(r.saldo_nuevo).toFixed(2)
                    );


                    // =========================================
                    // OBSERVACIÓN AUTOMÁTICA
                    // =========================================

                    const observacionActual =
                        $("#editObservacion").val().trim();

                    const texto =
                        "Pago total de deuda. " +
                        "Cuota calculada automáticamente para " +
                        "dejar el saldo de préstamo y multa anterior " +
                        "en S/ 0.00.";

                    if (!observacionActual) {

                        $("#editObservacion").val(texto);

                    }


                    actualizarEstadoDeuda(
                        Number(r.saldo_nuevo)
                    );

                }
            )
                .fail(function () {

                    alert(
                        "No se pudo calcular la cuota para cancelar la deuda."
                    );

                })
                .always(function () {

                    boton.prop("disabled", false);

                    boton.html(
                        '<i class="bi bi-check2-circle"></i> Pagar toda la deuda'
                    );

                });

        });

        // estado visual deuda:
        function actualizarEstadoDeuda(saldo) {

            const badge = $("#editEstadoDeuda");

            saldo = Number(saldo || 0);

            if (saldo <= 0.00) {

                badge
                    .removeClass("bg-light text-dark bg-warning bg-danger")
                    .addClass("bg-success")
                    .text("Deuda cancelada");

            } else {

                badge
                    .removeClass("bg-light text-dark bg-success bg-danger")
                    .addClass("bg-warning text-dark")
                    .text(
                        "Saldo: S/ " + saldo.toFixed(2)
                    );
            }
        }

        //Agregamos debounce para no disparar una consulta por cada tec

        let timerCalculoEdicion = null;

        function programarCalculoEdicion() {

            clearTimeout(timerCalculoEdicion);

            timerCalculoEdicion = setTimeout(function () {

                calcularEdicion();

            }, 350);
        }

        $("#editAporte, #editCuota, #editMulta, #editSobre")
            .on("input change", function () {

                programarCalculoEdicion();

            });

        // =====================================================
        // 3. GUARDAR EDICION DE MOVIMIENTO (AJAX POST)
        // =====================================================

        $("#btnGuardarEdicionMovimiento").on("click", function () {

            const boton = $(this);

            // Evitar envíos duplicados
            if (boton.prop("disabled")) {
                return;
            }

            const id = $("#editMovimientoId").val();

            if (!id) {
                alert("Movimiento no identificado.");
                return;
            }

            const datos = {
                aporte: $("#editAporte").val(),
                cuota_pagada: $("#editCuota").val(),
                multa: $("#editMulta").val(),
                sobre: $("#editSobre").val(),
                observacion: $("#editObservacion").val()
            };

            // Guardar estado original del botón
            const textoOriginal = boton.html();

            // Mostrar spinner
            boton
                .prop("disabled", true)
                .html(
                    '<span class="spinner-border spinner-border-sm me-2" ' +
                    'role="status" aria-hidden="true"></span>' +
                    'Guardando...'
                );

            $.ajax({
                url: `/movimientos/editar_movimiento/${id}`,
                method: "POST",
                data: datos,

                success: function (resp) {

                    if (!resp.ok) {
                        const mensaje = resp.mensaje || "No se pudo actualizar el movimiento.";

                        if (typeof mostrarMensaje === "function") {
                            mostrarMensaje(mensaje, "danger");
                        } else {
                            alert(mensaje);
                        }

                        return;
                    }

                    // Actualizar la fila
                    actualizarFilaMovimiento(id, resp);

                    const accionId = resp.accion_id;

                    // Cerrar modal
                    if ($modal[0]) {
                        $modal[0].close();
                    }

                    if (typeof mostrarMensaje === "function") {

                        mostrarMensaje(
                            "Movimiento actualizado correctamente.",
                            "success"
                        );

                        setTimeout(function () {
                            if (accionId) {
                                window.location.href =
                                    `/acciones/detalle/${accionId}`;
                            } else {
                                window.location.reload();
                            }
                        }, 1500);

                    } else {

                        alert("Movimiento actualizado correctamente.");

                        if (accionId) {
                            window.location.href =
                                `/acciones/detalle/${accionId}`;
                        } else {
                            window.location.reload();
                        }
                    }
                },

                error: function (xhr) {

                    let mensaje = "Error al actualizar el movimiento.";

                    if (xhr.responseJSON && xhr.responseJSON.mensaje) {
                        mensaje = xhr.responseJSON.mensaje;
                    }

                    if (typeof mostrarMensaje === "function") {
                        mostrarMensaje(mensaje, "danger");
                    } else {
                        alert(mensaje);
                    }
                },

                complete: function () {

                    // Restaurar el botón al terminar la petición
                    boton
                        .prop("disabled", false)
                        .html(textoOriginal);
                }
            });
        });

        // =====================================================
        // 4. ELIMINAR MOVIMIENTO
        // =====================================================
        $(document).on("click", ".btn-eliminar-movimiento", function () {
            const id = $(this).data("id");

            if (!confirm("¿Está seguro de eliminar este movimiento?")) {
                return;
            }

            $.ajax({
                url: `/movimientos/eliminar_movimiento/${id}`,
                method: "DELETE",
                success: function (resp) {
                    if (resp.ok) {
                        location.reload(); // Recarga para actualizar saldos globales
                    } else {
                        alert(resp.mensaje);
                    }
                }
            });
        });
    

    // =====================================================
    // FUNCION GLOBAL: ACTUALIZAR FILA DINÁMICAMENTE
    // =====================================================
    function actualizarFilaMovimiento(id, movimiento) {
        // Busca el botón específico de la fila editada
        const $btn = $(`.btn-editar-movimiento[data-id="${id}"]`);
        if ($btn.length === 0) return;

        const $fila = $btn.closest("tr");
        if ($fila.length === 0) return;

        // Actualiza apuntando directamente a las clases asignadas en el HTML
        // Valida si la propiedad existe en el objeto 'movimiento' que envía tu backend
        if (movimiento.aporte !== undefined) $fila.find(".celda-aporte").text(Number(movimiento.aporte).toFixed(2));
        if (movimiento.cuota_pagada !== undefined) $fila.find(".celda-cuota").text(Number(movimiento.cuota_pagada).toFixed(2));
        if (movimiento.amortizacion !== undefined) $fila.find(".celda-amortizacion").text(Number(movimiento.amortizacion).toFixed(2));
        if (movimiento.multa !== undefined) $fila.find(".celda-multa").text(Number(movimiento.multa).toFixed(2));
        if (movimiento.sobre !== undefined) $fila.find(".celda-sobre").text(Number(movimiento.sobre).toFixed(2));
        if (movimiento.saldo_prestamo !== undefined) $fila.find(".celda-saldo").text(Number(movimiento.saldo_prestamo).toFixed(2));
    }

    // Prestamo
    // =====================================================
    // =====================================================
    // 4. ELIMINAR PRESTAMO
    // =====================================================
    $(document).on("click", ".btn-eliminar-prestamo", function () {

        const id = $(this).data("id");

        if (!confirm("¿Está seguro de eliminar este préstamo?")) {
            return;
        }
        console.log("ingrese a eliminar prestamo");

        $.ajax({
            url: `/movimientos/eliminar_prestamo/${id}`,
            method: "DELETE",

            success: function (resp) {
                console.log("ingrese a success, resp: ", resp);

                if (resp.ok) {
                    location.reload(); // Recarga para actualizar saldos globales
                } else {
                    alert(resp.mensaje);
                }
                console.log("xx");
            }

        });
    });

    // =====================================================
    // FUNCION GLOBAL: ACTUALIZAR FILA DINÁMICAMENTE
    // =====================================================
    function actualizarFilaPrestamo(id, prestamo) {
        // Busca el botón específico de la fila editada
        const $btn = $(`.btn-editar-prestamo[data-id="${id}"]`);
        if ($btn.length === 0) return;

        const $fila = $btn.closest("tr");
        if ($fila.length === 0) return;

        // Actualiza apuntando directamente a las clases asignadas en el HTML
        // Valida si la propiedad existe en el objeto 'movimiento' que envía tu backend
        if (prestamo.monto !== undefined) $fila.find(".celda-monto").text(Number(prestamo.monto).toFixed(2));

    }


// =====================================================
// SIMULADOR FINANCIERO
// =====================================================

    const modalSimulador =
        document.getElementById("modalSimulador");

    const tbodySimulador =
        document.getElementById("tbodySimulador");


    // =====================================================
    // REDONDEO A CENTAVOS
    // =====================================================

    function dinero(valor) {

        return Number(
            Number(valor || 0).toFixed(2)
        );

    }


    // =====================================================
    // INTERÉS
    //
    // MISMA REGLA DE InteresService:
    //
    // redondeo hacia arriba a múltiplos de 0.50
    // =====================================================

    function calcularInteres(saldo, tasa) {

        saldo = dinero(saldo);

        if (saldo <= 0) {

            return 0;

        }

        const interesBase =
            saldo * tasa;

        return dinero(
            Math.ceil(
                interesBase * 2
            ) / 2
        );

    }


    // =====================================================
    // CUOTA MÍNIMA
    //
    // MISMA TABLA DE PrestamoService
    // =====================================================

    function calcularCuotaMinima(deuda) {

        deuda = dinero(deuda);

        if (deuda <= 0) return 0;
        if (deuda <= 3000) return 417;
        if (deuda <= 7500) return 504;
        if (deuda <= 12500) return 566;
        if (deuda <= 15000) return 590;
        if (deuda <= 17500) return 611;
        if (deuda <= 20000) return 677;
        if (deuda <= 22500) return 743;
        if (deuda <= 25000) return 809;
        if (deuda <= 27500) return 875;

        return 941;

    }


        /* ============================================================
        SIMULADOR FINANCIERO DE LA ACCIÓN
        ============================================================ */

        (function () {

            "use strict";

            /* ========================================================
            VARIABLES
            ======================================================== */

            const tbodySimulador = document.getElementById("tbodySimulador");

            const btnAbrirSimulador =
                document.getElementById("btnAbrirSimulador");

            const btnCerrarSimulador =
                document.getElementById("btnCerrarSimulador");

            const btnCerrarSimulador2 =
                document.getElementById("btnCerrarSimulador2");

            const btnRecalcularSimulador =
                document.getElementById("btnRecalcularSimulador");

            const modalSimulador =
                document.getElementById("modalSimulador");

            const simTasa =
                document.getElementById("simTasa");

            const simAporte =
                document.getElementById("simAporte");


            /* ========================================================
            DATOS INICIALES

            Estos datos deben ser proporcionados por Flask.
            ======================================================== */

            const SIMULADOR = {
                movimientos: [
                    {% for m in movimientos|sort(attribute='periodo_id') %}
                    {
                        id: {{ m.id }},
                        periodo_id: {{ m.periodo_id if m.periodo_id is not none else 'null' }},
                        periodo: "{{ m.periodo.anio }}-{{ '%02d'|format(m.periodo.mes) }}",
                        anio: {{ m.periodo.anio }},
                        mes: {{ m.periodo.mes }},
                        aporte: {{ (m.aporte or 0)|float }},
                        cuota: {{ (m.cuota_pagada or 0)|float }},
                        amortizacion: {{ (m.amortizacion or 0)|float }},
                        interes: {{ (m.interes or 0)|float }},
                        saldo: {{ (m.saldo_prestamo or 0)|float }},
                        multa: {{ (m.multa or 0)|float }},
                        sobre: {{ (m.sobre or 0)|float }}
                    }{% if loop.revindex0 %},{% endif %}
                    {% endfor %}
                ]
            };



            /* ========================================================
            FUNCIONES NUMÉRICAS
            ======================================================== */

            function numero(valor) {

                const n = parseFloat(valor);

                if (isNaN(n)) {
                    return 0;
                }

                return n;
            }


            function redondear(valor) {

                return Math.round(
                    (numero(valor) + Number.EPSILON) * 100
                ) / 100;

            }


            function dinero(valor) {

                return redondear(valor).toLocaleString(
                    "es-PE",
                    {
                        minimumFractionDigits: 2,
                        maximumFractionDigits: 2
                    }
                );

            }


            /* ========================================================
            ORDENAR MOVIMIENTOS
            ======================================================== */

            function obtenerMovimientosOrdenados() {

                return [...SIMULADOR.movimientos].sort(
                    function (a, b) {

                        if (a.anio !== b.anio) {
                            return a.anio - b.anio;
                        }

                        return a.mes - b.mes;

                    }
                );

            }


            /* ========================================================
            MULTA DEL PERÍODO ANTERIOR
            ======================================================== */

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


            /* ========================================================
            SALDO DE APERTURA
            ======================================================== */
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


            /* ========================================================
            PRÉSTAMO DEL PERÍODO

            En esta versión usamos el dato ya obtenido por el
            servidor cuando cargó la acción.

            Si tu backend expone préstamos por movimiento,
            se puede reemplazar solamente esta función.
            ======================================================== */

            function obtenerPrestamosPeriodo(movimiento) {

                const prestamos =
                    SIMULADOR.prestamos.filter(
                        function (p) {

                            return (
                                p.periodo_id === movimiento.periodo_id
                            );

                        }
                    );

                return redondear(
                    prestamos.reduce(
                        function (total, p) {

                            return total + numero(p.monto);

                        },
                        0
                    )
                );
            }


            /* ========================================================
            CÁLCULO DE UN PERÍODO
            ======================================================== */

            function calcularPeriodo(
                movimientos,
                indice,
                saldoAnteriorCalculado) 
            {

                const m = movimientos[indice];
                const aporte = redondear(m.aporte);
                const cuota = redondear(m.cuota);
                const multaAnterior =
                    obtenerMultaAnterior(
                        movimientos,
                        indice
                    );
                const saldoAnterior = redondear(saldoAnteriorCalculado);
                const prestamos = obtenerPrestamosPeriodo(m);


                /*
                * BASE DEL INTERÉS
                *
                * El saldo de préstamo del período anterior
                * YA contiene las amortizaciones anteriores.
                *
                * La multa del período anterior se agrega
                * para calcular el interés del período actual.
                */

                const baseInteres = redondear(
                    saldoAnterior +
                    multaAnterior +
                    prestamos
                );


                /*
                * INTERÉS
                */

                const tasa =
                    numero(simTasa.value) / 100;

                const interes = redondear(
                    baseInteres * tasa
                );


                /*
                * CUOTA MÍNIMA
                *
                * Aporte + interés + multa anterior
                */

                const cuotaMinima = redondear(
                    aporte +
                    interes +
                    multaAnterior
                );


                /*
                * IMPORTE DISPONIBLE PARA AMORTIZAR
                */

                let amortizacion = redondear(
                    cuota -
                    aporte -
                    interes -
                    multaAnterior
                );


                /*
                * Nunca puede existir amortización negativa.
                */

                if (amortizacion < 0) {
                    amortizacion = 0;
                }


                /*
                * La amortización no puede superar
                * la deuda de capital.
                *
                * IMPORTANTE:
                *
                * La multa NO forma parte del capital.
                *
                * Por eso no hacemos:
                *
                * cuota - deuda_total
                *
                * sino que primero se descuenta
                * la multa y luego el capital.
                */

                const capitalDisponible = redondear(saldoAnterior + prestamos);


                if (amortizacion > capitalDisponible) {

                    amortizacion = capitalDisponible;

                }

                /*
                * SALDO DE CAPITAL
                */
                const saldo = redondear(capitalDisponible - amortizacion );

                /*
                * CONTROL
                */

                const totalAplicado = redondear(
                    aporte +
                    interes +
                    multaAnterior +
                    amortizacion
                );


                const correcto =
                    Math.abs(
                        totalAplicado - cuota
                    ) < 0.011
                    ||
                    (
                        saldo <= 0.01 &&
                        cuota >= cuotaMinima - 0.01
                    );


                return {

                    ...m,

                    aporte:aporte,
                    cuota:cuota,
                    multaAnterior:multaAnterior,
                    saldoAnterior:saldoAnterior,
                    prestamos:prestamos,
                    baseInteres:baseInteres,
                    cuotaMinima:cuotaMinima,
                    interes:interes,
                    amortizacion:amortizacion,
                    saldo:saldo,
                    correcto:correcto

                };

            }


            /* ========================================================
            RECALCULAR TODO EL SIMULADOR
            ======================================================== */

            function recalcularSimulador() {

                const movimientos =
                    obtenerMovimientosOrdenados();

                const resultados = [];

                let saldoAnterior = 0;

                for (
                    let i = 0;
                    i < movimientos.length;
                    i++
                ) {

                    const resultado =
                        calcularPeriodo(
                            movimientos,
                            i,
                            saldoAnterior
                        );

                    resultados.push(resultado);

                    saldoAnterior =
                        resultado.saldo;
                }

                resultados.forEach(
                    actualizarFila
                );
            }


            /* ========================================================
            CREAR FILA
            ======================================================== */

            function agregarFila(data) {

                const tr =
                    document.createElement("tr");

                tr.dataset.id =
                    data.id;


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
                            value="${numero(data.cuota)}"
                            data-id="${data.id}"
                        >

                    </td>
                    <td class="sim-cuota-minima text-primary fw-bold">

                        S/ ${dinero(data.cuotaMinima)}

                    </td>
                    <td class="sim-amortizacion text-primary fw-bold">

                        S/ ${dinero(data.amortizacion)}

                    </td>
                    <td class="sim-interes text-success fw-bold">
                        S/ ${dinero(data.interes)}
                    </td>
                    <td class="sim-saldo text-danger fw-bold">
                        S/ ${dinero(data.saldo)}
                    </td>
                    <td class="sim-prestamo">
                        S/ ${dinero(data.prestamos)}
                    </td>
                    <td class="sim-multa">
                        S/ ${dinero(data.multa)}
                    </td>
                    <td class="sim-sobre">
                        S/ ${dinero(data.sobre)}
                    </td>
                    <td class="sim-control">
                        <span class="badge bg-secondary">
                            ...
                        </span>
                    </td>
                `;

                tbodySimulador.appendChild(tr);
            }

            /* ========================================================
            ACTUALIZAR FILA
            ======================================================== */
            function actualizarFila(data) {

                const tr =
                    tbodySimulador.querySelector(
                        `tr[data-id="${data.id}"]`
                    );

                if (!tr) {
                    return;
                }

                /*
                * IMPORTANTE:
                *
                * NO hacemos:
                *
                * input.value = data.cuota
                *
                * porque eso destruiría lo que el usuario
                * está escribiendo.
                */

                tr.querySelector(
                    ".sim-cuota-minima"
                ).textContent =
                    "S/ " + dinero(
                        data.cuotaMinima
                    );

                tr.querySelector(
                    ".sim-amortizacion"
                ).textContent =
                    "S/ " + dinero(
                        data.amortizacion
                    );

                tr.querySelector(
                    ".sim-interes"
                ).textContent =
                    "S/ " + dinero(
                        data.interes
                    );

                tr.querySelector(
                    ".sim-saldo"
                ).textContent =
                    "S/ " + dinero(
                        data.saldo
                    );

                tr.querySelector(
                    ".sim-prestamo"
                ).textContent =
                    "S/ " + dinero(
                        data.prestamos
                    );

                tr.querySelector(
                    ".sim-multa"
                ).textContent =
                    "S/ " + dinero(
                        data.multa
                    );

                tr.querySelector(
                    ".sim-sobre"
                ).textContent =
                    "S/ " + dinero(
                        data.sobre
                    );

                const control =
                    tr.querySelector(
                        ".sim-control"
                    );

                if (data.correcto) {
                    control.innerHTML =
                        `<span class="badge bg-success">
                            OK
                        </span>`;

                } else {
                    control.innerHTML =
                        `<span class="badge bg-danger">
                            REVISAR
                        </span>`;

                }

            }


            /* ========================================================
            CARGAR SIMULADOR
            ======================================================== */

            function cargarSimulador() {

                tbodySimulador.innerHTML = "";


                const movimientos =
                    obtenerMovimientosOrdenados();


                /*
                * Primero creamos las filas.
                */

                movimientos.forEach(
                    function (m) {

                        agregarFila({

                            ...m,

                            cuotaMinima: 0,

                            amortizacion: 0,

                            interes: 0,

                            prestamos:
                                obtenerPrestamosPeriodo(m),

                            correcto: false

                        });

                    }
                );


                /*
                * Después calculamos.
                */

                recalcularSimulador();

            }


            /* ========================================================
            EDITAR CUOTA
            ======================================================== */

            $(document).on(
                "input",
                ".sim-cuota",
                function () {

                    const id =
                        parseInt(
                            this.dataset.id
                        );
            
                    /*
                    * Solamente actualizamos el modelo.
                    *
                    * NO tocamos el input.
                    */

                    const movimiento =
                        SIMULADOR.movimientos.find(
                            function (m) {

                                return m.id === id;

                            }
                        );


                    if (!movimiento) {
                        return;
                    }


                    movimiento.cuota =
                        numero(this.value);


                    /*
                    * Recalcular todos los períodos
                    * porque el cambio de un período
                    * afecta los siguientes.
                    */

                    recalcularSimulador();

                }
            );


            /* ========================================================
            BLUR
            ======================================================== */

            $(document).on(
                "blur",
                ".sim-cuota",
                function () {

                    if (this.value === "") {

                        this.value = "0";

                    }

                }
            );


            /* ========================================================
            CAMBIO DE TASA
            ======================================================== */

            $(simTasa).on(
                "input change",
                function () {

                    recalcularSimulador();

                }
            );


            /* ========================================================
            CAMBIO DE APORTE
            ======================================================== */
            $(simAporte).on(
                "input change",
                function () {
                    /*
                    * Si el usuario cambia el aporte
                    * solamente se utiliza como referencia
                    * para la cuota mínima.
                    */
                    SIMULADOR.movimientos.forEach(
                        function (m) {

                            m.aporte =
                                numero(
                                    simAporte.value
                                );

                        }
                    );

                    recalcularSimulador();

                }
            );

            /* ========================================================
            BOTÓN RECALCULAR
            ======================================================== */
            if (btnRecalcularSimulador) {

                btnRecalcularSimulador.addEventListener(
                    "click",
                    function () {

                        recalcularSimulador();

                    }
                );

            }

            /* ========================================================
            ABRIR
            ======================================================== */
            if (btnAbrirSimulador) {

                btnAbrirSimulador.addEventListener(
                    "click",
                    function () {

                        cargarSimulador();

                        modalSimulador.showModal();

                    }
                );

            }


            /* ========================================================
            CERRAR
            ======================================================== */
            function cerrarSimulador() {

                if (
                    modalSimulador &&
                    modalSimulador.open
                ) {

                    modalSimulador.close();

                }

            }

            if (btnCerrarSimulador) {

                btnCerrarSimulador.addEventListener(
                    "click",
                    cerrarSimulador
                );
            }

            if (btnCerrarSimulador2) {

                btnCerrarSimulador2.addEventListener(
                    "click",
                    cerrarSimulador
                );
            }

        })();

});
