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

