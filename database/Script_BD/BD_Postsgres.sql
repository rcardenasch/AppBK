CREATE TABLE configuracion(

    id SERIAL PRIMARY KEY,

    aporte_minimo NUMERIC(12,2),

    sobre_por_accion NUMERIC(12,2),

    interes_mensual NUMERIC(5,2),

    metodo_distribucion VARCHAR(20)
);

CREATE TABLE fondo_utilidades(

    id SERIAL PRIMARY KEY,

    periodo_id INT REFERENCES periodos(id),

    intereses NUMERIC(12,2),

    multas NUMERIC(12,2),

    sobres NUMERIC(12,2),

    total NUMERIC(12,2),

    fecha_registro TIMESTAMP DEFAULT NOW()
);

ALTER TABLE solicitudes_prestamo
ADD COLUMN acciones INT DEFAULT 0;

ALTER TABLE solicitudes_prestamo
ADD COLUMN aportes_acumulados NUMERIC(12,2) DEFAULT 0;

ALTER TABLE solicitudes_prestamo
ADD COLUMN antiguedad_meses INT DEFAULT 0;

ALTER TABLE solicitudes_prestamo
ADD COLUMN observacion TEXT;

ALTER TABLE fondo_utilidades
ADD CONSTRAINT uk_fondo_periodo
UNIQUE(periodo_id);

-- 
CREATE TABLE roles (

    id SERIAL PRIMARY KEY,

    nombre VARCHAR(50) NOT NULL UNIQUE,

    descripcion VARCHAR(200),

    estado BOOLEAN DEFAULT TRUE
);

CREATE TABLE permisos (

    id SERIAL PRIMARY KEY,

    modulo VARCHAR(50),

    accion VARCHAR(50),

    descripcion VARCHAR(150)
);

CREATE TABLE roles_permisos(

    rol_id INT REFERENCES roles(id),

    permiso_id INT REFERENCES permisos(id),

    PRIMARY KEY(rol_id,permiso_id)
);

CREATE TABLE usuarios(

    id SERIAL PRIMARY KEY,

    rol_id INT REFERENCES roles(id),

    nombres VARCHAR(150) NOT NULL,

    usuario VARCHAR(50) UNIQUE NOT NULL,

    correo VARCHAR(120),

    password_hash VARCHAR(255) NOT NULL,

    ultimo_acceso TIMESTAMP,

    estado BOOLEAN DEFAULT TRUE,

    fecha_registro TIMESTAMP DEFAULT NOW()
);

-- agregar columnas a Socios:
ALTER TABLE socios
ADD COLUMN documento VARCHAR(20),
ADD COLUMN telefono VARCHAR(20),
ADD COLUMN fecha_ingreso DATE DEFAULT CURRENT_DATE;

-- agregar columnas a movimientos
ALTER TABLE movimientos
ADD COLUMN prestamo_id INT REFERENCES prestamos(id);

-- nueva tabla acciones:
DROP TABLE acciones;

CREATE TABLE acciones(

    id SERIAL PRIMARY KEY,

    socio_id INT REFERENCES socios(id),

    numero_accion VARCHAR(20),

    valor NUMERIC(12,2),

    estado VARCHAR(20) DEFAULT 'ACTIVA',

    fecha_registro DATE DEFAULT CURRENT_DATE

);

-- modificamos en prestamos:
ALTER TABLE prestamos
ADD COLUMN accion_id INT REFERENCES acciones(id);

-- modificamos movimientos.
ALTER TABLE movimientos
ADD COLUMN accion_id INT REFERENCES acciones(id);

-- ALTER TABLE prestamos
ALTER TABLE solicitudes_prestamo
    ADD COLUMN periodo_id INTEGER NOT NULL,
    ADD COLUMN accion_id INTEGER NOT NULL,
   
    ADD CONSTRAINT fk_periodo FOREIGN KEY (periodo_id) REFERENCES periodos(id),
    ADD CONSTRAINT fk_accion FOREIGN KEY (accion_id) REFERENCES acciones(id);
--
ALTER TABLE solicitudes_prestamo
ADD CONSTRAINT fk_solicitud_accion
FOREIGN KEY (accion_id)
REFERENCES acciones(id);
--
ALTER TABLE solicitudes_prestamo
    ADD COLUMN monto_aprobado NUMERIC(12,2)
--
ALTER TABLE solicitudes_prestamo 
    ALTER COLUMN prioridad TYPE integer USING prioridad::integer;	

--
ALTER TABLE prestamos
ADD COLUMN cuota_minima NUMERIC(12,2);

--
ALTER TABLE prestamos
ADD COLUMN saldo_interes NUMERIC(12,2);

--
ALTER TABLE periodos
ADD COLUMN saldo_caja NUMERIC(12,2);

--
ALTER TABLE prestamos
ADD COLUMN periodo_id int;

-- estado de solicitudes_prestamo
PENDIENTE
      │
      ├────────────┐
      │            │
      ▼            ▼
APROBADA      ANULADA  CANCELADA
      │
      ▼
ATENDIDA

-- AGREGAMOS NUEVA TABLA DE ASISTENCIAS

CREATE TABLE asistencias
(
    id                  SERIAL PRIMARY KEY,

    periodo_id          INTEGER NOT NULL,
    socio_id            INTEGER NOT NULL,
    usuario_id          INTEGER NOT NULL,

    estado              VARCHAR(20) NOT NULL,

    acciones            INTEGER NOT NULL,

    multa               NUMERIC(12,2) NOT NULL DEFAULT 0,

    observacion         VARCHAR(100),

    fecha_registro      TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_asistencia_periodo
        FOREIGN KEY (periodo_id)
        REFERENCES periodos(id),

    CONSTRAINT fk_asistencia_socio
        FOREIGN KEY (socio_id)
        REFERENCES socios(id),

    CONSTRAINT fk_asistencia_usuario
        FOREIGN KEY (usuario_id)
        REFERENCES usuarios(id),

    CONSTRAINT uq_asistencia_periodo_socio
        UNIQUE(periodo_id, socio_id),

    CONSTRAINT ck_estado_asistencia
        CHECK (
            estado IN (
                'ASISTIO',
                'TARDANZA',
                'FALTA',
                'PERMISO'
            )
        )
);

-- agregar columnas a configuracion:
ALTER TABLE configuracion
ADD COLUMN multa_tardanza NUMERIC(12,2);

ALTER TABLE configuracion
ADD COLUMN multa_falta NUMERIC(12,2);

ALTER TABLE configuracion
ADD COLUMN estado BOOLEAN;

-- agregar columna a movimientos:
ALTER TABLE movimientos
ADD COLUMN asistencia_id int REFERENCES asistencias(id);

-- Fujo de trabajo BK
RegistroMensualService
        │
        │ determina cuota mínima
        ▼
PrestamoService.calcular_cuota_minima()
        │
        │ cuota_pagada
        ▼
MovimientoService.registrar_movimiento()
        │
        ▼
PrestamoService.calcular_pago()
        │
        ├── InteresService.calcular_interes()
        ├── calcula amortización
        ├── calcula nuevo saldo
        └── calcula saldo_interes
--
   PERÍODO
                       │
                       ▼
              ┌─────────────────┐
              │   PRE-BALANCE   │
              └────────┬────────┘
                       │
                       ▼
              FONDO DISPONIBLE
                       │
                       ▼
              ┌─────────────────┐
              │   SIMULACIÓN    │
              │   PRÉSTAMOS     │
              └────────┬────────┘
                       │
                       ▼
              APROBAR PRÉSTAMOS
                       │
                       ▼
              REGISTRAR PRÉSTAMO
                       │
                       ▼
          ┌────────────────────────┐
          │ GENERAR MOVIMIENTOS    │
          │ MENSUALES              │
          └───────────┬────────────┘
                      │
                      ▼
               REVISAR TODO
                      │
                      ▼
             ┌────────────────┐
             │ CERRAR PERÍODO │
             └────────────────┘
-- Se crea tabla casa chica para cuando se cree nueva accion 
--el aporte sume 1.7 por accion por ejemplo 
-- asi se puede registrar otro ingreso tb
--
-- Tabla: caja_chica
CREATE TABLE caja_chica (
    id SERIAL PRIMARY KEY,
    nombre VARCHAR(100) DEFAULT 'Caja chica',
    saldo_inicial NUMERIC(12, 2) DEFAULT 0.00,
    saldo_actual NUMERIC(12, 2) DEFAULT 0.00,
    activo BOOLEAN DEFAULT TRUE
);

-- Tabla: movimientos_caja_chica
CREATE TABLE movimientos_caja_chica (
    id SERIAL PRIMARY KEY,
    caja_id INTEGER NOT NULL,
    periodo_id INTEGER NOT NULL,
    tipo VARCHAR(20) NOT NULL,
    concepto VARCHAR(200),
    monto NUMERIC(12, 2) NOT NULL,
    fecha TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    observacion TEXT,
    
    -- Restricciones de llave foránea (Foreign Keys)
    CONSTRAINT fk_movimientos_caja_chica_caja 
        FOREIGN KEY (caja_id) REFERENCES caja_chica(id) 
        ON DELETE CASCADE,
        
    CONSTRAINT fk_movimientos_caja_chica_periodo 
        FOREIGN KEY (periodo_id) REFERENCES periodos(id)
        
    -- Opcional: Validación para los tipos de movimiento
    -- CONSTRAINT chk_tipo_movimiento CHECK (tipo IN ('INGRESO', 'EGRESO', 'AJUSTE'))
);
-- Transferencias:
CREATE TABLE transferencias (
    id SERIAL PRIMARY KEY,
    periodo_id INTEGER NOT NULL,
    socio_origen_id INTEGER NOT NULL,
    socio_destino_id INTEGER NOT NULL,
    monto NUMERIC(12, 2) NOT NULL,
    estado VARCHAR(20) NOT NULL DEFAULT 'CONFIRMADA',
    fecha_transferencia TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
    usuario_id INTEGER NOT NULL,
    observacion VARCHAR(500),
    
    -- Restricciones de Llaves Foráneas (Foreign Keys)
    CONSTRAINT fk_periodos FOREIGN KEY (periodo_id) REFERENCES periodos(id),
    CONSTRAINT fk_socio_origen FOREIGN KEY (socio_origen_id) REFERENCES socios(id),
    CONSTRAINT fk_socio_destino FOREIGN KEY (socio_destino_id) REFERENCES socios(id),
    CONSTRAINT fk_usuario FOREIGN KEY (usuario_id) REFERENCES usuarios(id)
);

-- Índices explícitos (index=True)
CREATE INDEX idx_transferencias_periodo_id ON transferencias(periodo_id);
CREATE INDEX idx_transferencias_socio_origen_id ON transferencias(socio_origen_id);
CREATE INDEX idx_transferencias_socio_destino_id ON transferencias(socio_destino_id);
--
-- aecuacion para accesos:
-- 1. Agregar la columna socio_id a la tabla usuarios
ALTER TABLE usuarios 
ADD COLUMN socio_id INTEGER NULL;

-- 2. Crear la restricción de clave foránea (Foreign Key) hacia la tabla socios
ALTER TABLE usuarios 
ADD CONSTRAINT fk_usuarios_socios
FOREIGN KEY (socio_id) REFERENCES socios(id)
ON DELETE SET NULL;
--
-- Aplica esta restricción para que un socio no pueda ser asignado a múltiples usuarios
-- relacion 1:1
ALTER TABLE usuarios 
ADD CONSTRAINT uq_usuarios_socio_id UNIQUE (socio_id);
--
CREATE UNIQUE INDEX IF NOT EXISTS
ux_usuarios_socio_id
ON usuarios(socio_id)
WHERE socio_id IS NOT NULL;
--
ALTER TABLE usuarios
ADD COLUMN debe_cambiar_password BOOLEAN NOT NULL DEFAULT TRUE;
--
select * from periodos;
select * from caja_chica;
select * from movimientos_caja_chica;
--
select * from roles;
select * from usuarios;
select * from permisos;
select * from roles_permisos;


select * from periodos;
select * from socios;
SELECT * FROM acciones;
select * from acciones;
select * from fondo_utilidades;

select * from configuracion;
select * from prestamos where socio_id=2  order by 1 desc; 
select * from movimientos where socio_id=4 order by 1 desc; 

select * from prestamos order by 1 desc;

select * from solicitudes_prestamo; 
select * from transferencias;

select * from acciones WHERE SOCIO_ID=15;
SELECT * FROM movimientos WHERE SOCIO_ID=15;

SELECT * FROM prestamos where prestamos.accion_id=27;
select * from acciones;
SELECT SUM(APORTE),SUM(AMORTIZACION) FROM movimientos;

SELECT * from socios order by 2 asc;
SELECT * FROM movimientos order by movimientos.socio_id, movimientos.periodo_id;
select * from prestamos order by socio_id;
select * from solicitudes_prestamo;
select * from fondo_utilidades;
select * from distribucion_utilidades;

select * from periodos;
select * from configuracion;
select * from asistencias;
select * from solicitudes_prestamo;

select * from usuarios;
select * from permisos;
select * from roles;
select * from roles_permisos;

INSERT INTO permisos
(modulo, accion, descripcion)
VALUES
--('roles', 'listar', 'Visualizar roles y permisos'),
--('roles', 'crear', 'Crear nuevos roles'),
--('roles', 'editar', 'Editar y activar/desactivar roles'),
--('roles', 'eliminar', 'Eliminar roles sin usuarios'),
--('roles', 'permisos', 'Administrar permisos de los roles');

('usuarios', 'listar', 'Visualizar usuarios'),
('usuarios', 'crear', 'Crear nuevos usuarios'),
('usuarios', 'editar', 'Editar y activar/desactivar usuarios'),
('usuarios', 'eliminar', 'Eliminar usuarios sin roles'),

('socios', 'listar', 'Visualizar socios'),
('socios', 'crear', 'Crear nuevos socios'),
('socios', 'editar', 'Editar y activar/desactivar socios'),
('socios', 'eliminar', 'Eliminar socios sin movimientos'),

('acciones', 'listar', 'Visualizar acciones'),
('acciones', 'crear', 'Crear nuevos acciones'),
('acciones', 'editar', 'Editar y activar/desactivar acciones'),
('acciones', 'eliminar', 'Eliminar acciones sin movimientos'),

('prestamos', 'listar', 'Visualizar prestamos'),
('prestamos', 'crear', 'Crear nuevos prestamos'),
('prestamos', 'editar', 'Editar y activar/desactivar prestamos'),
('prestamos', 'eliminar', 'Eliminar prestamos'),

('movimientos', 'listar', 'Visualizar movimientos'),
('movimientos', 'crear', 'Crear nuevos movimientos'),
('movimientos', 'editar', 'Editar y activar/desactivar movimientos'),
('movimientos', 'eliminar', 'Eliminar movimientos sin prestamos'),

('solicitudes', 'listar', 'Visualizar solicitudes'),
('solicitudes', 'crear', 'Crear nuevos solicitudes'),
('solicitudes', 'editar', 'Editar y activar/desactivar solicitudes'),
('solicitudes', 'eliminar', 'Eliminar solicitudes'),

('asistencia', 'listar', 'Visualizar asistencias'),
('asistencia', 'crear', 'Crear nueva asistencia'),

('distribucion', 'simular', 'Generar simulación de la distribucion'),
('distribucion', 'generar', 'Crear nuevos prestamos aprobados'),
('distribucion', 'revertir', 'Revertir y activar/desactivar distribucion'),

('transferencia', 'simular', 'Generar simulación de la transferencia'),
('transferencia', 'confirmar', 'Crear nuevos prestamos aprobados'),

('configuracion', 'listar', 'Visualizar configuracion'),
('configuracion', 'crear', 'Crear nueva configuracion'),
('configuracion', 'editar', 'Editar y activar/desactivar configuracion'),
('configuracion', 'eliminar', 'Eliminar configuracion'),

('periodo', 'listar', 'Visualizar periodo'),
('periodo', 'crear', 'Crear nueva periodo'),
('periodo', 'editar', 'Editar y activar/desactivar periodo'),
('periodo', 'eliminar', 'Eliminar periodo'),
('periodo', 'generar movimientos masivos','Generar movimientos masivos de todos los socios para el periodo'),
('periodo', 'cierre', 'Crear cierre del periodo');

--
alter table configuracion
add column multa_no_transferir NUMERIC(12,2);

-- luego dar en roles_permisos al administrador a todos estos permisos
select * from configuracion
select * from usuarios
select * from roles
select * from permisos;
select * from roles_permisos
select * from periodos
select * from fondo_utilidades
select * from caja_chica
select * from movimientos_caja_chica
select * from prestamos where socio_id=5
select * from solicitudes_prestamo order by id asc;
select * from acciones where socio_id=15 order by id asc
SELECT * FROM socios
SELECT * FROM movimientos m
where m.socio_id=4 order by m.socio_id, m.periodo_id;
where m.id=489 --and m.periodo_id=14 

select * from solicitudes_prestamo
select * from prestamos where socio_id=13  order by saldo_actual desc;
select * from asistencias;
select * from transferencias;

select socios.nombres,movimientos.sobre FROM movimientos 
inner join socios on socios.id=movimientos.socio_id
where sobre>0 order by movimientos.socio_id;

-- suma de aportes socios,
-- capacida prestamo BK sum(cuota_pagada)
select movimientos.periodo_id,
sum(aporte)aporte,sum(amortizacion)amortizacion
,sum(interes)interes,sum(sobre) sobre
,(sum(cuota_pagada)+sum(sobre)) capacidad
,sum(cuota_pagada)cuota_pagada
,sum(sobre)sobre,sum(saldo_prestamo) saldo_prestamo
,sum(multa)multa,(sum(cuota_pagada)+sum(sobre))Cancelar_periodo
from movimientos
inner join socios on socios.id=movimientos.socio_id
group by movimientos.periodo_id order by 1  
;
