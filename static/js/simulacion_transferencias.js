document.addEventListener("DOMContentLoaded", () => {

    "use strict";

    console.log(
        "Simulación de transferencias iniciada"
    );

    // =========================================================
    // DATOS
    // =========================================================

    const DATA =
        window.DISTRIBUCION_DATA || {};

    const periodoId =
        Number(DATA.periodoId || 0);

    const fondoTotal =
        Number(DATA.fondo || 0);

    let socios =
        Array.isArray(DATA.socios)
            ? DATA.socios.map(s => ({
                socioId: Number(s.socio_id),
                nombre: s.nombre || "",
                prestamos:
                    Array.isArray(s.prestamos)
                        ? s.prestamos
                        : [],
                totalAprobado:
                    Number(s.total_aprobado || 0),
                fondoPropio:
                    Number(s.cuota_propia || 0),
                propioAplicado:
                    Number(s.propio_aplicado || 0),
                necesidad:
                    Number(s.necesidad || 0),
                excedente:
                    Number(s.excedente || 0),
                recibido: 0,
                enviado: 0
            }))
            : [];

    let transferencias = [];

    let estrategiaActual = null;


    console.log(
        "Socios:",
        socios
    );


    // =========================================================
    // UTILIDADES
    // =========================================================

    function numero(valor) {

        const n = Number(valor);

        return Number.isFinite(n)
            ? n
            : 0;

    }


    function redondear(valor) {

        return Math.round(
            (numero(valor) + Number.EPSILON) * 100
        ) / 100;

    }


    function dinero(valor) {

        return numero(valor).toLocaleString(
            "es-PE",
            {
                minimumFractionDigits: 2,
                maximumFractionDigits: 2
            }
        );

    }


    function dineroS(valor) {

        return `S/ ${dinero(valor)}`;

    }


    function escapeHtml(texto) {

        const div =
            document.createElement("div");

        div.textContent =
            texto ?? "";

        return div.innerHTML;

    }


    // =========================================================
    // PREPARAR ESTADO
    // =========================================================

    function prepararEstado() {

        socios.forEach(socio => {

            socio.recibido = 0;

            socio.enviado = 0;

        });

        transferencias.forEach(t => {

            const origen =
                socios.find(
                    s =>
                        s.socioId ===
                        Number(t.socioOrigenId)
                );

            const destino =
                socios.find(
                    s =>
                        s.socioId ===
                        Number(t.socioDestinoId)
                );

            if (!origen || !destino)
                return;

            origen.enviado =
                redondear(
                    origen.enviado +
                    t.monto
                );

            destino.recibido =
                redondear(
                    destino.recibido +
                    t.monto
                );

        });

        socios.forEach(socio => {

            socio.necesidad =
                Math.max(
                    0,
                    redondear(
                        socio.totalAprobado
                        -
                        socio.propioAplicado
                        -
                        socio.recibido
                    )
                );

            socio.excedente =
                Math.max(
                    0,
                    redondear(
                        socio.fondoPropio
                        -
                        socio.propioAplicado
                        -
                        socio.enviado
                    )
                );

        });

    }


    // =========================================================
    // AGREGAR TRANSFERENCIA
    // =========================================================
    function agregarTransferencia(origen, destino, monto) {

        monto = redondear(monto);

        if (monto <= 0)
            return;

        if (origen.socioId === destino.socioId)
            return;

        const existente = transferencias.find(
            t =>
                t.socioOrigenId === origen.socioId &&
                t.socioDestinoId === destino.socioId
        );

        if (existente) {

            existente.monto = redondear(
                existente.monto + monto
            );

            return;
        }

        transferencias.push({

            socioOrigenId:
                origen.socioId,

            socioOrigen:
                origen.nombre,

            socioDestinoId:
                destino.socioId,

            socioDestino:
                destino.nombre,

            monto:
                monto
        });
    }


    // =========================================================
    // OPTIMIZAR TRANSFERENCIAS
    // =========================================================

    function optimizarTransferencias() {

        console.log(
            "Optimizando transferencias..."
        );

        transferencias = [];

        estrategiaActual =
            "Optimización automática";


        prepararEstado();


        // =====================================================
        // FUENTES
        // Socios que tienen excedente
        // =====================================================

        const fuentes =
            socios
                .filter(
                    s =>
                        s.excedente > 0
                )
                .sort(
                    (a, b) =>
                        b.excedente -
                        a.excedente
                );


        // =====================================================
        // NECESIDADES
        // Socios que necesitan dinero
        // =====================================================

        const necesidades =
            socios
                .filter(
                    s =>
                        s.necesidad > 0
                )
                .sort(
                    (a, b) =>
                        b.necesidad -
                        a.necesidad
                );


        console.log(
            "Fuentes:",
            fuentes
        );

        console.log(
            "Necesidades:",
            necesidades
        );


        // =====================================================
        // ALGORITMO
        // =====================================================

        for (
            const destino of necesidades
        ) {

            if (
                destino.necesidad <= 0
            )
                continue;


            for (
                const origen of fuentes
            ) {

                if (
                    origen.excedente <= 0
                )
                    continue;

                if (
                    origen.socioId ===
                    destino.socioId
                )
                    continue;

                if (
                    destino.necesidad <= 0
                )
                    break;


                const monto =
                    redondear(
                        Math.min(
                            origen.excedente,
                            destino.necesidad
                        )
                    );


                if (monto <= 0)
                    continue;


                agregarTransferencia(
                    origen,
                    destino,
                    monto
                );


                origen.excedente =
                    redondear(
                        origen.excedente -
                        monto
                    );


                destino.necesidad =
                    redondear(
                        destino.necesidad -
                        monto
                    );

            }

        }


        console.log(
            "Transferencias generadas:",
            transferencias
        );


        actualizarInterfaz();

    }


    // =========================================================
    // LIMPIAR
    // =========================================================

    function limpiar() {

        console.log(
            "Limpiando simulación..."
        );

        transferencias = [];

        estrategiaActual = null;

        prepararEstado();

        actualizarInterfaz();

    }


    // =========================================================
    // RENDER SOCIOS
    // =========================================================

    function renderSocios() {

        socios.forEach(socio => {

            const fila =
                document.querySelector(
                    `tr[data-socio="${socio.socioId}"]`
                );

            if (!fila)
                return;


            const necesidad =
                socio.necesidad;

            const excedente =
                socio.excedente;


            const faltante =
                fila.querySelector(
                    ".faltante"
                );

            if (faltante) {

                if (necesidad > 0) {

                    faltante.innerHTML =
                        `<span class="badge bg-danger">
                            ${dineroS(necesidad)}
                        </span>`;

                }
                else {

                    faltante.innerHTML =
                        `<span class="badge bg-success">
                            Completo
                        </span>`;

                }

            }


            const excedenteElemento =
                fila.querySelector(
                    ".excedente"
                );

            if (excedenteElemento) {

                if (excedente > 0) {

                    excedenteElemento.innerHTML =
                        `<span class="badge bg-info text-dark">
                            ${dineroS(excedente)}
                        </span>`;

                }
                else {

                    excedenteElemento.textContent =
                        "S/ 0.00";

                }

            }


            const estado =
                fila.querySelector(
                    ".estado"
                );

            if (!estado)
                return;


            if (necesidad > 0) {

                estado.innerHTML =
                    `<span class="badge bg-danger">
                        NECESITA
                    </span>`;

            }
            else if (excedente > 0) {

                estado.innerHTML =
                    `<span class="badge bg-info text-dark">
                        PUEDE TRANSFERIR
                    </span>`;

            }
            else {

                estado.innerHTML =
                    `<span class="badge bg-success">
                        COMPLETO
                    </span>`;

            }

        });

    }


    // =========================================================
    // RENDER TRANSFERENCIAS
    // =========================================================

    function renderTransferencias() {

        const contenedor =
            document.getElementById(
                "contenedorTransferencias"
            );

        if (!contenedor)
            return;


        const cantidad =
            document.getElementById(
                "cantidadTransferencias"
            );

        const total =
            document.getElementById(
                "sumaTotalTransferencias"
            );


        const montoTotal =
            transferencias.reduce(
                (sum, t) =>
                    sum +
                    numero(t.monto),
                0
            );


        if (cantidad) {

            cantidad.textContent =
                transferencias.length;

        }


        if (total) {

            total.textContent =
                dineroS(montoTotal);

        }


        if (
            transferencias.length === 0
        ) {

            contenedor.innerHTML = `

                <div class="text-center text-muted py-5">

                    <i class="bi bi-info-circle fs-3"></i>

                    <div class="mt-2">

                        No existen transferencias propuestas.

                    </div>

                </div>

            `;

            return;

        }


        let html = `

            <table class="table table-hover mb-0">

                <thead class="table-light">

                    <tr>

                        <th style="width:60px">
                            #
                        </th>

                        <th>
                            Socio que transfiere
                        </th>

                        <th>
                            Socio que recibe
                        </th>

                        <th class="text-end">
                            Monto
                        </th>

                    </tr>

                </thead>

                <tbody>

        `;


        transferencias.forEach(
            (t, index) => {

                html += `

                    <tr>

                        <td>
                            ${index + 1}
                        </td>

                        <td>

                            <i class="bi bi-person-up text-danger me-1"></i>

                            <strong>
                                ${escapeHtml(t.socioOrigen)}
                            </strong>

                        </td>

                        <td>

                            <i class="bi bi-person-down text-success me-1"></i>

                            <strong>
                                ${escapeHtml(t.socioDestino)}
                            </strong>

                        </td>

                        <td class="text-end">

                            <strong class="text-primary">
                                ${dineroS(t.monto)}
                            </strong>

                        </td>

                    </tr>

                `;

            }
        );


        html += `

                </tbody>

            </table>

        `;


        contenedor.innerHTML =
            html;

    }


    // =========================================================
    // RESUMEN
    // =========================================================

    function actualizarResumen() {

        const total =
            transferencias.reduce(
                (sum, t) =>
                    sum +
                    numero(t.monto),
                0
            );


        const elemento =
            document.getElementById(
                "totalTransferencias"
            );

        if (elemento) {

            elemento.textContent =
                transferencias.length;

        }


        const saldo =
            Math.max(
                0,
                redondear(
                    fondoTotal -
                    total
                )
            );


        const saldoElemento =
            document.getElementById(
                "saldoRestante"
            );

        if (saldoElemento) {

            saldoElemento.textContent =
                dineroS(saldo);

        }

    }


    // =========================================================
    // ACTUALIZAR TODO
    // =========================================================

    function actualizarInterfaz() {

        prepararEstado();

        renderSocios();

        renderTransferencias();

        actualizarResumen();

    }


    // =========================================================
    // VALIDAR
    // =========================================================

    function validarSimulacion() {

        prepararEstado();


        const faltante =
            socios.reduce(
                (sum, socio) =>
                    sum +
                    Math.max(
                        0,
                        socio.necesidad
                    ),
                0
            );


        if (faltante > 0) {

            return {

                ok: false,

                mensaje:
                    `Todavía falta financiar ` +
                    `${dineroS(faltante)}.`

            };

        }


        return {

            ok: true,

            mensaje:
                "La distribución es válida."

        };

    }

    // =========================================================
    // DATOS PARA SERVIDOR
    // =========================================================

    function obtenerDatosSimulacion() {

        prepararEstado();

        return {

            periodo_id:
                periodoId,
            transferencias:
                transferencias.map(t => ({

                    socio_origen_id:
                        Number(t.socioOrigenId),

                    socio_destino_id:
                        Number(t.socioDestinoId),

                    monto:
                        redondear(t.monto)

                })),

            socios:
                socios.map(s => ({

                    socio_id:
                        s.socioId,

                    total_aprobado:
                        redondear(
                            s.totalAprobado
                        ),

                    propio:
                        redondear(
                            s.propioAplicado
                        ),

                    recibido:
                        redondear(
                            s.recibido
                        ),

                    necesidad:
                        redondear(
                            s.necesidad
                        ),

                    excedente:
                        redondear(
                            s.excedente
                        )

                })),

            estrategia:
                estrategiaActual

        };

    }

    // =========================================================
    // BOTÓN OPTIMIZAR
    // =========================================================

    const btnOptimizar =
        document.getElementById(
            "btnOptimizar"
        );


    if (btnOptimizar) {

        btnOptimizar.addEventListener(
            "click",
            optimizarTransferencias
        );

    }


    // =========================================================
    // BOTÓN LIMPIAR
    // =========================================================

    const btnLimpiar =
        document.getElementById(
            "btnLimpiar"
        );


    if (btnLimpiar) {

        btnLimpiar.addEventListener(
            "click",
            limpiar
        );

    }

    // =========================================================
    // CONFIRMAR
    // =========================================================

    const btnConfirmar =
        document.getElementById(
            "btnConfirmarDistribucion"
        );


    if (btnConfirmar) {

        btnConfirmar.addEventListener(
            "click",
            async () => {

                const validacion =
                    validarSimulacion();


                if (!validacion.ok) {

                    alert(
                        validacion.mensaje
                    );

                    return;

                }


                if (
                    transferencias.length === 0
                ) {

                    alert(
                        "No existen transferencias para confirmar."
                    );

                    return;

                }


                if (
                    !confirm(
                        "¿Desea confirmar la distribución?"
                    )
                )
                    return;


                const datos =
                    obtenerDatosSimulacion();


                try {

                    btnConfirmar.disabled =
                        true;

                    const textoOriginal =
                        btnConfirmar.innerHTML;


                    btnConfirmar.innerHTML = `

                        <span
                            class="spinner-border spinner-border-sm me-1">
                        </span>

                        Procesando...

                    `;


                    const response =
                        await fetch(
                            `/distribucion/transferencias/confirmar/${periodoId}`,
                            {

                                method: "POST",

                                headers: {

                                    "Content-Type":
                                        "application/json"

                                },

                                body:
                                    JSON.stringify(
                                        datos
                                    )

                            }
                        );


                    const data =
                        await response.json();


                    if (
                        !response.ok ||
                        !data.ok
                    ) {

                        throw new Error(
                            data.mensaje ||
                            "No se pudo confirmar."
                        );

                    }


                    alert(
                        data.mensaje ||
                        "Distribución confirmada correctamente."
                    );

                    window.location.href =
                        `/distribucion/${periodoId}`;

                }
                catch (error) {

                    console.error(error);

                    alert(
                        error.message ||
                        "Error al confirmar distribución."
                    );

                }
                finally {

                    btnConfirmar.disabled =
                        false;

                    btnConfirmar.innerHTML =
                        `<i class="bi bi-check-circle"></i>
                         Confirmar distribución`;

                }

            }
        );

    }


    // =========================================================
    // INICIALIZAR
    // =========================================================

    actualizarInterfaz();

});