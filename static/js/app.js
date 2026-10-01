function mostrarProcesando(boton, texto = "Procesando...") {
    if (!boton) return;

    // Guardamos el contenido original
    boton.dataset.originalHtml = boton.innerHTML;
    boton.dataset.originalDisabled = boton.disabled;

    boton.disabled = true;

    boton.innerHTML = `
        <span class="spinner-border spinner-border-sm me-1"
              role="status"
              aria-hidden="true"></span>
        ${texto}
    `;
}

function restaurarBoton(boton) {
    if (!boton) return;

    boton.disabled = false;

    if (boton.dataset.originalHtml) {
        boton.innerHTML = boton.dataset.originalHtml;
    }
}