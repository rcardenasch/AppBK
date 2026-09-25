document.addEventListener("DOMContentLoaded", () => {
    const fondoDisponible =
        parseFloat(
            document
                .getElementById("saldo_restante")
                .dataset
                .fondo
        );

    // =====================================================
    // DATATABLE
    // =====================================================

    const tabla = $('.datatable').DataTable();

    // =====================================================
    // OBTENER TODAS LAS FILAS
    //
    // IMPORTANTE:
    // DataTables permite acceder a todas las filas aunque
    // estén en otra página.
    // =====================================================

    const filas = () => {

        return tabla
            .rows()
            .nodes()
            .toArray();

    };

    
const confirmarEstrategia = (nombre, callback) => {
  const modal = document.getElementById('modalConfirmar');
  const titulo = document.getElementById('modalTitulo');
  const btnConfirmar = document.getElementById('btnConfirmar');
  const btnCancelar = document.getElementById('btnCancelar');

  titulo.textContent = `¿Desea aplicar la estrategia '${nombre}'?`;
  modal.showModal(); // Abre el modal de forma nativa

  btnConfirmar.onclick = () => {
    modal.close();
    callback();
  };

  btnCancelar.onclick = () => modal.close();
};

// Modal confirmación para generar préstamos

const confirmarGenerar = (periodoTexto,callback) => {
  const modal = document.getElementById('modalConfirmarGenerar');
  const titulo = document.getElementById('modalTituloGenerar');
  const btnConfirmar = document.getElementById('btnConfirmarGenerar');
  const btnCancelar = document.getElementById('btnCancelarGenerar');

  

  titulo.textContent = `¿Desea generar préstamos para el período ${periodoTexto}?`;
  modal.showModal(); // Abre el modal de forma nativa

  btnConfirmar.onclick = () => {
    modal.close();
    callback();
  };

  btnCancelar.onclick = () => modal.close();
};



// Modal confirmación para revertir distribución
const confirmarRevertir = (periodoTexto, callback) => {

    const modal = document.getElementById("modalRevertir");
    const titulo = document.getElementById('modalTituloRevertir');

    titulo.textContent = `Revertir`;
    document.getElementById("mensajeRevertir").innerHTML =

        `¿Desea revertir la distribución de préstamos del período <strong>${periodoTexto}</strong>?`;

    modal.showModal();

    document.getElementById("btnConfirmarRevertir").onclick = () => {

        modal.close();

        callback();

    };

    document.getElementById("btnCancelarRevertir").onclick = () => {

        modal.close();

    };

};

//---------------------------------------------------
// Cerrar Periodo - Confirmar
//---------------------------------------------------

const confirmarCerrarPeriodo = (periodoId, periodoTexto, callback) => {

    const modal = document.getElementById("modalCerrarPeriodo");

    document.getElementById("modalTituloCerrar").innerHTML =
        `¿Desea cerrar definitivamente el período <b>${periodoTexto}</b>?`;

    document.getElementById("btnConfirmarCerrar").onclick = () => {

        modal.close();

        callback();

    };

    document.getElementById("btnCancelarCerrar").onclick = () => {

        modal.close();

    };

    modal.showModal();

};

//---------------------------------------------------
// Habilitar / Deshabilitar estrategias
//---------------------------------------------------

const botonesEstrategia = [

    "btnTodo",
    "btnProrratear",
    "btnScore",
    "btnPrioridad",
    "btnGenerar"

];

const haySolicitudes = filas().length > 0;

botonesEstrategia.forEach(id => {

    const boton = document.getElementById(id);

    if (!boton) return;

    boton.disabled = !haySolicitudes;

    if (!haySolicitudes) {

        boton.title = "No existen solicitudes pendientes para este período.";

    }

});

    
    //---------------------------------------------------
    // Obtiene el solicitado
    //---------------------------------------------------

    
    function solicitado(tr){

        return Number(

            tr.querySelector(".solicitado")
                .dataset
                .solicitado

        );

    }

    //---------------------------------------------------
    // Input asignado
    //---------------------------------------------------

    function input(tr){

        return tr.querySelector(".asignado");

    }

    //---------------------------------------------------
    // Actualizar saldo
    //---------------------------------------------------

    function actualizarSaldo(){

        let total = 0;

        todosLosInputs().forEach(i => {

            total += Number(i.value) || 0;

        });

        let saldo =
            fondoDisponible - total;

        document
            .getElementById("saldo_restante")
            .innerHTML =
                "S/ " +
                saldo.toLocaleString(
                    "es-PE",
                    {
                        minimumFractionDigits: 2,
                        maximumFractionDigits: 2
                    }
                );
    }

    //---------------------------------------------------
    // Reiniciar
    //---------------------------------------------------

    function limpiar(){

        todosLosInputs().forEach(i => {

            i.value = "0.00";

        });

        actualizarSaldo();
    }

    // =====================================================
    // OBTENER TODOS LOS INPUTS DE ASIGNACIÓN
    // =====================================================

    function todosLosInputs() {

        return tabla
            .rows()
            .nodes()
            .toArray()
            .map(tr => tr.querySelector(".asignado"))
            .filter(input => input !== null);

    }

    //---------------------------------------------------
    // ASIGNAR TODO
    //---------------------------------------------------

 document
    .getElementById("btnTodo")
    .onclick=()=>{

    confirmarEstrategia(
        "Asignar Todo",

        ()=>{

            limpiar();

            let saldo=fondoDisponible;

            filas().forEach(tr=>{

                let s=solicitado(tr);

                let asignar=Math.min(s,saldo);

                input(tr).value=asignar.toFixed(2);

                saldo-=asignar;

            });

            actualizarSaldo();

        }

    );

};

    
    //---------------------------------------------------
    // PRORRATEAR
    //---------------------------------------------------

document
.getElementById("btnProrratear")
.onclick = () => {

    confirmarEstrategia(

        "Prorratear",

        () => {

            limpiar();

            let totalSolicitado = 0;

            filas().forEach(f => {

                totalSolicitado += solicitado(f);

            });

            if (totalSolicitado <= 0)
                return;

            let factor = fondoDisponible / totalSolicitado;

            let saldo = fondoDisponible;

            filas().forEach(f => {

                let monto = solicitado(f);

                let asignado = Math.min(
                    monto,
                    monto * factor
                );

                // Redondear a favor del socio
                asignado = Math.ceil(asignado);

                // Nunca entregar más de lo solicitado
                asignado = Math.min(asignado, monto);

                // Nunca superar el saldo disponible
                asignado = Math.min(asignado, saldo);

                // Mostrar con dos decimales
                input(f).value = asignado.toFixed(2);

                saldo -= asignado;

            });

            actualizarSaldo();

        }

    );

};
    //---------------------------------------------------
    // PRIORIZAR SCORE
    //---------------------------------------------------

   document
    .getElementById("btnScore")
    .onclick=()=>{

    confirmarEstrategia(
        "Priorizar Score",

        ()=>{

            limpiar();

            let saldo=fondoDisponible;

            let orden=filas().sort(

                (a,b)=>

                parseFloat(b.cells[2].innerText)
                -
                parseFloat(a.cells[2].innerText)

            );

            orden.forEach(f=>{

                let monto=solicitado(f);

                let asignado=Math.min(
                    monto,
                    saldo
                );

                input(f).value=asignado.toFixed(2);

                saldo-=asignado;

            });

            actualizarSaldo();

        }

    );

};

    //---------------------------------------------------
    // PRIORIDAD + SCORE
    //---------------------------------------------------

  document
    .getElementById("btnPrioridad")
    .onclick=()=>{

    confirmarEstrategia(
        "Prioridad + Score",

        ()=>{

            limpiar();

            let saldo=fondoDisponible;
            let orden=filas().sort((a,b)=>{

                let pa=parseInt(a.cells[3].innerText);
                let pb=parseInt(b.cells[3].innerText);

                if(pb!==pa)
                    return pb-pa;

                let sa=parseFloat(a.cells[2].innerText);
                let sb=parseFloat(b.cells[2].innerText);

                return sb-sa;

            });

            orden.forEach(f=>{

                let monto=solicitado(f);
                let asignado=Math.min(
                    monto,
                    saldo
                );

                input(f).value=asignado.toFixed(2);

                saldo-=asignado;

            });

            actualizarSaldo();

        }

    );

};

    // =====================================================
    // EDICIÓN MANUAL
    // =====================================================

    $('.datatable tbody').on(
        'input',
        '.asignado',
        function () {

            const max =
                parseFloat(
                    this.max
                );

            let valor =
                Number(this.value) || 0;

            if (valor > max) {

                valor = max;

            }

            if (valor < 0) {

                valor = 0;

            }

            this.value =
                valor.toFixed(2);

            actualizarSaldo();

        }
    );

//---------------------------------------------------
// Generar préstamos
//---------------------------------------------------

document
.getElementById("btnGenerar")
.onclick = () => {

    const periodoId =
        document.getElementById("btnGenerar").dataset.periodoId;

    const periodoTexto =
        document.getElementById("btnGenerar").dataset.periodoTexto;

    confirmarGenerar(periodoTexto, () => {

        const solicitudes = [];

        todosLosInputs().forEach(i => {

            const monto =
                parseFloat(i.value) || 0;

            if (monto > 0) {

                solicitudes.push({
                    id: parseInt(
                        i.dataset.id
                    ),
                    asignado: monto
                });

            }

        });

        fetch(`/distribucion/generar/${periodoId}`, {

            method: "POST",

            headers: {
                "Content-Type": "application/json"
            },

            body: JSON.stringify({
                solicitudes: solicitudes
            })

        })
        .then(r => r.json())
        .then(data => {

            console.log(data);

            if (data.ok) {

                alert(data.mensaje);
                location.reload();

            } else {

                alert(data.mensaje);

            }

        });

    });

};
        

// boton para revertir distribución
document
.getElementById("btnRevertir")
.onclick = () => {

    const periodoId =
        document.getElementById("btnRevertir").dataset.periodoId;

    const periodoTexto =
        document.getElementById("btnRevertir").dataset.periodoTexto;

    confirmarRevertir(

        periodoTexto,

        () => {

            fetch(

                `/distribucion/revertir/${periodoId}`,

                {
                    method: "POST"

                }

            )
            .then(r => r.json())

            .then(data => {

                if(data.ok){

                    alert(data.mensaje);
                    location.reload();

                }

                else{

                    alert(data.mensaje);

                }

            });

        }

    );

};

// Cerrar periodo AJAX
document
.getElementById("btnCerrarPeriodo")
.onclick = () => {

    const periodoId =
        document.getElementById("btnCerrarPeriodo").dataset.periodoId;

    const periodoTexto =
        document.getElementById("btnCerrarPeriodo").dataset.periodoTexto;

    confirmarCerrarPeriodo(

        periodoId,
        periodoTexto,

        () => {

            fetch(`/periodos/cerrar/${periodoId}`, {

                method: "POST"

            })

            .then(r => r.json())

            .then(resp => {

                if(resp.ok){

                    alert(resp.mensaje);

                    location.reload();

                }else{

                    alert(resp.mensaje);

                }

            });

        }

    );

};



});