
// CAMBIO AQUÍ: Cambiamos window.load por el ready de jQuery para sincronizar los tiempos

$(function(){
    //---------------------------------------------------
    // 1. Modelo en memory
    //---------------------------------------------------
    const asistencias = {};

    //---------------------------------------------------
    // 2. Extracción limpia de la API (Sin constructores)
    //---------------------------------------------------
    // Usar la 'd' minúscula nativa de jQuery (.dataTable().api()) garantiza
    // extraer la instancia ya existente del base.html sin intentar recrearla.
    const table = $.fn.dataTable.isDataTable('#tablaAsistencias')
    ? $('#tablaAsistencias').DataTable()
    : null;

if (!table){
    console.error("La tabla no fue inicializada.");
    return;
}


    //---------------------------------------------------
    // 3. Inicializar el modelo con todas las páginas
    //---------------------------------------------------
    $(table.rows().nodes()).each(function () {

        const grupo = this.querySelector(".estado");

        if (grupo) {

            asistencias[grupo.dataset.socio] = {

                socio_id: Number(grupo.dataset.socio),
                acciones: Number(grupo.dataset.acciones),
                estado: "ASISTIO",
                observacion: ""

            };

        }

    });

    //---------------------------------------------------
    // 4. Delegación de eventos adaptada a DataTables
    //---------------------------------------------------
    // Botones de estado
    $('#tablaAsistencias tbody').on('click', '.estado-btn', function () {

        const grupo = this.closest(".estado");

        $(grupo)
            .find(".estado-btn")
            .removeClass("active");

        $(this)
            .addClass("active");

        actualizarFila(grupo);

    });


    // Observaciones
    $('#tablaAsistencias tbody').on("input", ".observacion", function () {

        const fila = this.closest("tr");
        const grupo = fila.querySelector(".estado");
        const socioId = Number(grupo.dataset.socio);
        if(asistencias[socioId]){
            asistencias[socioId].observacion=this.value;
        }

    });

    
    function actualizarFila(grupo) {
        // Convertimos elementos a jQuery para interactuar de forma segura con DataTables
        const $grupo = $(grupo);
        const $fila = $grupo.closest("tr");

        const socioId = parseInt($grupo.attr("data-socio"));
        const acciones = parseInt($grupo.attr("data-acciones"));

        // Buscar el botón que tiene la clase active actualmente
        const $activo = $grupo.find(".estado-btn.active");
        const estado = $activo.length ? $activo.attr("data-estado") : "ASISTIO";

        // Leer el cuadro de observaciones de forma segura
        const observacion = $fila.find(".observacion").val() || "";

        let multa = 0;
        switch (estado) {
            case "TARDANZA":
                multa = acciones * MULTA_TARDANZA;
                break;
            case "FALTA":
                multa = acciones * MULTA_FALTA;
                break;
        }

        // Guardar los datos limpios en la memoria
        asistencias[socioId] = {
            socio_id: socioId,
            acciones: acciones,
            estado: estado,
            observacion: observacion
        };

        // CORRECCIÓN AQUÍ: Manejo del badge visual con métodos puros de jQuery
        const $badge = $fila.find(".multa");
        if ($badge.length) {
            $badge.html("S/" + multa.toFixed(2));

            if (multa > 0) {
                $badge.addClass("bg-danger").removeClass("bg-success");
            } else {
                $badge.addClass("bg-success").removeClass("bg-danger");
            }
        }

        actualizarResumen();
    }


    //---------------------------------------------------
    // 5. Acción Masiva: Marcar todos Asistió
    //---------------------------------------------------
    document.getElementById("btnTodos").onclick = () => {
        // Recorremos todas las filas (visibles y ocultas) de la tabla mediante la API
        table.$(".estado").each(function () {
            const grupo = this;
            $(grupo).find(".estado-btn").removeClass("active");
            $(grupo).find('[data-estado="ASISTIO"]').addClass("active");
            actualizarFila(grupo);
        });
    };


    function actualizarResumen() {
        let asistio = 0;
        let tarde = 0;
        let falta = 0;
        let multas = 0;

        Object.values(asistencias).forEach(a => {
            switch (a.estado) {
                case "ASISTIO":
                    asistio++;
                    break;
                case "TARDANZA":
                    tarde++;
                    multas += a.acciones * MULTA_TARDANZA;
                    break;
                case "FALTA":
                    falta++;
                    multas += a.acciones * MULTA_FALTA;
                    break;
            }
        });

        document.getElementById("cAsistio").innerHTML = asistio;
        document.getElementById("cTarde").innerHTML = tarde;
        document.getElementById("cFalta").innerHTML = falta;
        document.getElementById("cMultas").innerHTML = "S/" + multas.toFixed(2);
    }


    //---------------------------------------------------
    // 6. Procesos de Guardado y Modales
    //---------------------------------------------------
    const confirmarGuardar = (callback) => {
        const modal = document.getElementById("modalGuardar");
        document.getElementById("modalGuardarTexto").innerHTML =
            "¿Desea guardar la asistencia de la reunión?<br><br><b>Esta acción generará automáticamente las multas correspondientes.</b>";
        modal.showModal();

        document.getElementById("btnConfirmarGuardar").onclick = () => {
            modal.close();
            callback();
        };

        document.getElementById("btnCancelarGuardar").onclick = () => {
            modal.close();
        };
    };

    document.getElementById("btnGuardar").onclick = () => {
        confirmarGuardar(() => {
            const periodoId = document.getElementById("btnGuardar").dataset.periodo;

            fetch("/asistencias/guardar", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json"
                },
                body: JSON.stringify({
                    periodo_id: periodoId,
                    asistencias: Object.values(asistencias)
                })
            })
                .then(r => r.json())
                .then(resp => {
                    mostrarResultado(
                        resp.ok,
                        `
                    <h5>${resp.mensaje}</h5>
                    <hr>
                    <b>Asistencias registradas:</b> ${resp.registrados}<br>
                    <b>Tardanzas:</b> ${resp.tardanzas}<br>
                    <b>Inasistencias:</b> ${resp.faltas}<br>
                    <b>Total multas:</b>
                    <span class="text-danger">
                        S/${Number(resp.multas).toFixed(2)}
                    </span>
                    `
                    );
                });
        });
    };

    function mostrarResultado(ok, mensaje) {
        const modal = document.getElementById("modalResultado");
        document.getElementById("resultadoTexto").innerHTML = mensaje;
        const header = document.getElementById("resultadoHeader");

        if (ok) {
            header.className = "card-header bg-success text-white";
        } else {
            header.className = "card-header bg-danger text-white";
        }

        modal.showModal();

        document.getElementById("btnCerrarResultado").onclick = () => {
            modal.close();
            if (ok) {
                location.reload();
            }
        };
    }

    // En lugar de document.getElementById("btnTodos").click(); usa esto al final del archivo:
    if (document.getElementById("btnTodos")) {
        document.getElementById("btnTodos").click();
    }

});
