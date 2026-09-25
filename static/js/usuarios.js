//====================================================
// USUARIOS.JS
// Sistema Banquito Familiar
//====================================================

document.addEventListener("DOMContentLoaded", function () {

    inicializarDataTable();

    eventosNuevoUsuario();

    eventosEditarUsuario();

    eventosResetPassword();

    eventosConfirmacion();

});

//====================================================
// DATATABLE
//====================================================

function inicializarDataTable() {

    if ($("#tablaUsuarios").length) {

        $("#tablaUsuarios").DataTable({

            responsive: true,

            autoWidth: false,

            pageLength: 10,

            language: {

                url: "//cdn.datatables.net/plug-ins/1.13.8/i18n/es-ES.json"

            }

        });

    }

}

//====================================================
// MOSTRAR / OCULTAR PASSWORD
//====================================================

function eventosNuevoUsuario() {

    const btn = document.getElementById("mostrarPassword");

    if (!btn) return;

    btn.addEventListener("click", function () {

        let pass = document.getElementById("password");

        if (pass.type === "password") {

            pass.type = "text";

            btn.innerHTML = '<i class="bi bi-eye-slash"></i>';

        }

        else {

            pass.type = "password";

            btn.innerHTML = '<i class="bi bi-eye"></i>';

        }

    });

}

//====================================================
// VALIDAR PASSWORD
//====================================================

const confirmar = document.getElementById("confirmar");

if (confirmar) {

    confirmar.addEventListener("keyup", function () {

        let p1 = document.getElementById("password").value;

        let p2 = confirmar.value;

        let error = document.getElementById("passwordError");

        if (p1 !== p2) {

            error.innerHTML =

                "Las contraseñas no coinciden.";

        }

        else {

            error.innerHTML = "";

        }

    });

}

//====================================================
// EDITAR USUARIO
//====================================================

function eventosEditarUsuario() {

    document.querySelectorAll(".editar").forEach(function (boton) {

        boton.addEventListener("click", function () {

            let id = this.dataset.id;

            fetch("/usuarios/editar/" + id)

                .then(res => res.json())

                .then(data => {

                    if (!data.success) {

                        Swal.fire(

                            "Error",

                            data.mensaje,

                            "error"

                        );

                        return;

                    }

                    document.getElementById(

                        "edit_nombres"

                    ).value = data.nombres;

                    document.getElementById(

                        "edit_usuario"

                    ).value = data.usuario;

                    document.getElementById(

                        "edit_correo"

                    ).value = data.correo;

                    document.getElementById(

                        "edit_rol"

                    ).value = data.rol_id;

                    document.getElementById(

                        "edit_estado"

                    ).value = data.estado ? 1 : 0;

                    document.getElementById(

                        "formEditar"

                    ).action =

                        "/usuarios/actualizar/" + id;

                    let modal = new bootstrap.Modal(

                        document.getElementById(

                            "modalEditar"

                        )

                    );

                    modal.show();

                });

        });

    });

}

//====================================================
// RESET PASSWORD
//====================================================

function eventosResetPassword() {

    document.querySelectorAll(".password").forEach(function (boton) {

        boton.addEventListener("click", function () {

            let id = this.dataset.id;

            document.getElementById(

                "formPassword"

            ).action =

                "/usuarios/reset/" + id;

            let modal = new bootstrap.Modal(

                document.getElementById(

                    "modalPassword"

                )

            );

            modal.show();

        });

    });

}

//====================================================
// VALIDAR PASSWORD RESET
//====================================================

const confirmarPassword =

document.getElementById(

    "confirmarPassword"

);

if (confirmarPassword) {

    confirmarPassword.addEventListener(

        "keyup",

        function () {

            let p1 =

                document.getElementById(

                    "nuevaPassword"

                ).value;

            let p2 =

                confirmarPassword.value;

            let div =

                document.getElementById(

                    "errorPassword"

                );

            if (p1 !== p2) {

                div.innerHTML =

                    "Las contraseñas no coinciden.";

            }

            else {

                div.innerHTML = "";

            }

        }

    );

}

//====================================================
// CONFIRMAR ELIMINAR
//====================================================

function eventosConfirmacion() {

    document.querySelectorAll(

        ".btn-danger"

    ).forEach(function (boton) {

        boton.addEventListener(

            "click",

            function (e) {

                e.preventDefault();

                let form =

                    this.closest("form");

                Swal.fire({

                    title: "¿Desactivar usuario?",

                    text: "Podrá volver a activarse posteriormente.",

                    icon: "warning",

                    showCancelButton: true,

                    confirmButtonText: "Sí",

                    cancelButtonText: "Cancelar"

                })

                .then((result)=>{

                    if(result.isConfirmed){

                        form.submit();

                    }

                });

            }

        );

    });

}

//====================================================
// TOAST MENSAJES
//====================================================

function toast(titulo, texto, icono) {

    Swal.fire({

        toast: true,

        position: "top-end",

        timer: 3000,

        timerProgressBar: true,

        showConfirmButton: false,

        title: titulo,

        text: texto,

        icon: icono

    });

}