-- ============================================================
-- SIGUET - Sistema de Asignación Automática de Aulas
--          y Horarios Académicos
-- Script de creación de la base de datos
-- Motor: PostgreSQL 14 o superior
-- ============================================================

-- Creación de la base de datos (ejecutar una sola vez,
-- conectado a la base "postgres"):
--
--   CREATE DATABASE siguet
--       WITH ENCODING 'UTF8'
--       LC_COLLATE = 'es_CO.UTF-8'
--       LC_CTYPE   = 'es_CO.UTF-8'
--       TEMPLATE   = template0;
--
-- Luego conectarse a ella y ejecutar el resto del script.


-- ============================================================
-- 0. EXTENSIONES
-- ============================================================
-- btree_gist permite la restricción EXCLUDE que impide franjas
-- solapadas en un mismo día (viene incluida con PostgreSQL).

CREATE EXTENSION IF NOT EXISTS btree_gist;


-- ============================================================
-- 1. USUARIOS Y ACCESO
-- ============================================================

CREATE TABLE usuario (
    id              SERIAL       PRIMARY KEY,
    nombre_usuario  VARCHAR(50)  NOT NULL UNIQUE,
    nombre_completo VARCHAR(120) NOT NULL,
    contrasena_hash VARCHAR(255) NOT NULL,
    perfil          VARCHAR(20)  NOT NULL,
    activo          BOOLEAN      NOT NULL DEFAULT TRUE,
    fecha_creacion  TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT ck_usuario_perfil
        CHECK (perfil IN ('administrador', 'consultor'))
);

COMMENT ON COLUMN usuario.contrasena_hash IS
    'Contraseña cifrada. Nunca se almacena en texto plano (RNF-07).';


-- ============================================================
-- 2. ENTIDADES BASE
-- ============================================================

-- ---------- Franjas horarias ----------
CREATE TABLE franja_horaria (
    id           SERIAL   PRIMARY KEY,
    dia_semana   SMALLINT NOT NULL,   -- 1 = lunes ... 7 = domingo
    hora_inicio  TIME     NOT NULL,
    hora_fin     TIME     NOT NULL,

    CONSTRAINT ck_franja_dia
        CHECK (dia_semana BETWEEN 1 AND 7),
    CONSTRAINT ck_franja_horas
        CHECK (hora_fin > hora_inicio),
    CONSTRAINT uq_franja
        UNIQUE (dia_semana, hora_inicio, hora_fin),

    -- Dos franjas del mismo día no pueden solaparse en el tiempo.
    -- Así, "misma franja" equivale a "mismo momento" y las reglas
    -- de no cruce de la tabla asignacion quedan completas.
    -- La fecha fija solo sirve para convertir TIME en un rango.
    CONSTRAINT ex_franja_sin_solape
        EXCLUDE USING gist (
            dia_semana WITH =,
            tsrange(DATE '2000-01-01' + hora_inicio,
                    DATE '2000-01-01' + hora_fin) WITH &&
        )
);


-- ---------- Aulas ----------
CREATE TABLE aula (
    id         SERIAL      PRIMARY KEY,
    codigo     VARCHAR(20) NOT NULL UNIQUE,
    ubicacion  VARCHAR(100),
    capacidad  INTEGER     NOT NULL,
    tipo       VARCHAR(20) NOT NULL DEFAULT 'convencional',

    CONSTRAINT ck_aula_capacidad
        CHECK (capacidad > 0),
    CONSTRAINT ck_aula_tipo
        CHECK (tipo IN ('convencional', 'laboratorio', 'sala_sistemas')),

    -- Necesaria para validar el tipo de aula desde la tabla asignacion
    CONSTRAINT uq_aula_id_tipo UNIQUE (id, tipo)
);


-- ---------- Asignaturas ----------
CREATE TABLE asignatura (
    id                  SERIAL       PRIMARY KEY,
    codigo              VARCHAR(20)  NOT NULL UNIQUE,
    nombre              VARCHAR(120) NOT NULL,
    intensidad_horaria  SMALLINT     NOT NULL,
    tipo_aula_requerida VARCHAR(20)  NOT NULL DEFAULT 'convencional',

    CONSTRAINT ck_asignatura_intensidad
        CHECK (intensidad_horaria > 0),
    CONSTRAINT ck_asignatura_tipo_aula
        CHECK (tipo_aula_requerida IN ('convencional', 'laboratorio', 'sala_sistemas')),

    -- Necesaria para copiar el tipo de aula requerido hacia clase
    CONSTRAINT uq_asignatura_id_tipo_aula UNIQUE (id, tipo_aula_requerida)
);

COMMENT ON COLUMN asignatura.intensidad_horaria IS
    'Horas semanales que debe dictarse la asignatura.';


-- ---------- Docentes ----------
CREATE TABLE docente (
    id             SERIAL       PRIMARY KEY,
    identificacion VARCHAR(20)  NOT NULL UNIQUE,
    nombre         VARCHAR(120) NOT NULL,
    correo         VARCHAR(120),
    activo         BOOLEAN      NOT NULL DEFAULT TRUE
);


-- ---------- Vínculo usuario - docente ----------
-- Permite que un usuario con perfil consultor (docente) vea "Mis horarios".
-- Se agrega aquí porque la tabla usuario se crea antes que docente.
-- UNIQUE: un docente tiene como máximo un usuario.
-- ON DELETE SET NULL: si se borra el docente, el usuario queda sin vínculo.
ALTER TABLE usuario
    ADD COLUMN docente_id INTEGER UNIQUE
        REFERENCES docente(id) ON DELETE SET NULL;


-- ---------- Grupos académicos ----------
CREATE TABLE grupo (
    id                   SERIAL      PRIMARY KEY,
    codigo               VARCHAR(20) NOT NULL UNIQUE,
    programa             VARCHAR(100),
    semestre             SMALLINT,
    cantidad_estudiantes INTEGER     NOT NULL,

    CONSTRAINT ck_grupo_cantidad
        CHECK (cantidad_estudiantes > 0)
);


-- ============================================================
-- 3. RELACIONES DE APOYO
-- ============================================================

-- ---------- Qué asignaturas puede dictar cada docente ----------
CREATE TABLE docente_asignatura (
    docente_id    INTEGER NOT NULL REFERENCES docente(id)    ON DELETE CASCADE,
    asignatura_id INTEGER NOT NULL REFERENCES asignatura(id) ON DELETE CASCADE,

    PRIMARY KEY (docente_id, asignatura_id)
);


-- ---------- En qué franjas puede dictar clase cada docente ----------
CREATE TABLE disponibilidad_docente (
    docente_id INTEGER NOT NULL REFERENCES docente(id)        ON DELETE CASCADE,
    franja_id  INTEGER NOT NULL REFERENCES franja_horaria(id) ON DELETE CASCADE,
    -- Si es TRUE, es una franja preferida del docente (RB_PREF_DOCENTE)
    preferida  BOOLEAN NOT NULL DEFAULT FALSE,

    PRIMARY KEY (docente_id, franja_id)
);


-- ============================================================
-- 4. CLASES A PROGRAMAR
-- ============================================================
-- Una clase es "este grupo ve esta asignatura con este docente".
-- Es lo que el algoritmo debe ubicar en un aula y una franja.

CREATE TABLE clase (
    id                 SERIAL   PRIMARY KEY,
    grupo_id           INTEGER  NOT NULL REFERENCES grupo(id),
    asignatura_id      INTEGER  NOT NULL REFERENCES asignatura(id),
    docente_id         INTEGER  NOT NULL,
    sesiones_semanales SMALLINT NOT NULL DEFAULT 1,
    -- Copiado desde asignatura.tipo_aula_requerida
    tipo_aula          VARCHAR(20) NOT NULL,

    CONSTRAINT ck_clase_sesiones
        CHECK (sesiones_semanales > 0),

    -- El tipo copiado debe ser realmente el que requiere la asignatura
    CONSTRAINT fk_clase_tipo_aula_requerida
        FOREIGN KEY (asignatura_id, tipo_aula)
        REFERENCES asignatura (id, tipo_aula_requerida)
        ON UPDATE CASCADE,

    -- Necesaria para validar el tipo de aula desde la tabla asignacion
    CONSTRAINT uq_clase_id_tipo_aula
        UNIQUE (id, tipo_aula),

    -- Un grupo no puede ver dos veces la misma asignatura
    CONSTRAINT uq_clase_grupo_asignatura
        UNIQUE (grupo_id, asignatura_id),

    -- El docente debe estar registrado como capacitado para la asignatura
    CONSTRAINT fk_clase_docente_capacitado
        FOREIGN KEY (docente_id, asignatura_id)
        REFERENCES docente_asignatura (docente_id, asignatura_id),

    -- Necesaria para validar coherencia desde la tabla asignacion
    CONSTRAINT uq_clase_id_docente_grupo
        UNIQUE (id, docente_id, grupo_id)
);

COMMENT ON COLUMN clase.sesiones_semanales IS
    'En cuántos bloques se divide la intensidad horaria de la asignatura.';

COMMENT ON COLUMN clase.tipo_aula IS
    'Copia de asignatura.tipo_aula_requerida. La aplicación la llena al crear la clase; la llave foránea garantiza que coincida.';


-- ============================================================
-- 5. RESTRICCIONES BLANDAS CONFIGURABLES
-- ============================================================
-- Las restricciones duras NO se almacenan aquí: son fijas y
-- están implementadas en el algoritmo y en este esquema (RN-12).

CREATE TABLE restriccion_blanda (
    id          SERIAL       PRIMARY KEY,
    codigo      VARCHAR(30)  NOT NULL UNIQUE,
    nombre      VARCHAR(120) NOT NULL,
    descripcion TEXT,
    activa      BOOLEAN      NOT NULL DEFAULT TRUE,
    peso        SMALLINT     NOT NULL DEFAULT 1,

    CONSTRAINT ck_restriccion_peso
        CHECK (peso BETWEEN 1 AND 5)
);


-- ============================================================
-- 6. RESULTADO DE LA GENERACIÓN
-- ============================================================

-- ---------- Ejecución del algoritmo ----------
-- Conserva únicamente la última ejecución (RN-16).
CREATE TABLE ejecucion (
    id              SERIAL      PRIMARY KEY,
    fecha           TIMESTAMP   NOT NULL DEFAULT CURRENT_TIMESTAMP,
    usuario_id      INTEGER     REFERENCES usuario(id),
    estado          VARCHAR(20) NOT NULL,
    clases_totales  INTEGER     NOT NULL DEFAULT 0,
    clases_asignadas INTEGER    NOT NULL DEFAULT 0,

    CONSTRAINT ck_ejecucion_estado
        CHECK (estado IN ('completa', 'parcial', 'fallida'))
);


-- ---------- Asignaciones (tabla central) ----------
CREATE TABLE asignacion (
    id          SERIAL  PRIMARY KEY,
    ejecucion_id INTEGER NOT NULL REFERENCES ejecucion(id) ON DELETE CASCADE,
    clase_id    INTEGER NOT NULL REFERENCES clase(id),
    aula_id     INTEGER NOT NULL REFERENCES aula(id),
    franja_id   INTEGER NOT NULL REFERENCES franja_horaria(id),

    -- Copiados desde clase para poder imponer las reglas de unicidad
    docente_id  INTEGER NOT NULL,
    grupo_id    INTEGER NOT NULL,
    -- Copiado desde clase (y debe coincidir con el aula)
    -- para validar el tipo de espacio
    tipo_aula   VARCHAR(20) NOT NULL,

    -- RN-07: un aula no puede tener dos clases en la misma franja
    CONSTRAINT uq_asignacion_aula_franja
        UNIQUE (aula_id, franja_id),

    -- RN-05: un docente no puede estar en dos clases en la misma franja
    CONSTRAINT uq_asignacion_docente_franja
        UNIQUE (docente_id, franja_id),

    -- RN-06: un grupo no puede tener dos clases en la misma franja
    CONSTRAINT uq_asignacion_grupo_franja
        UNIQUE (grupo_id, franja_id),

    -- El docente y el grupo copiados deben coincidir con los de la clase
    CONSTRAINT fk_asignacion_clase_coherente
        FOREIGN KEY (clase_id, docente_id, grupo_id)
        REFERENCES clase (id, docente_id, grupo_id),

    -- RN-09: la franja debe pertenecer a la disponibilidad del docente
    CONSTRAINT fk_asignacion_disponibilidad
        FOREIGN KEY (docente_id, franja_id)
        REFERENCES disponibilidad_docente (docente_id, franja_id),

    -- El tipo copiado debe ser realmente el del aula asignada
    CONSTRAINT fk_asignacion_tipo_aula
        FOREIGN KEY (aula_id, tipo_aula)
        REFERENCES aula (id, tipo),

    -- ...y también el que requiere la clase. Con las dos llaves,
    -- el aula asignada siempre es del tipo que pide la asignatura.
    CONSTRAINT fk_asignacion_tipo_requerido
        FOREIGN KEY (clase_id, tipo_aula)
        REFERENCES clase (id, tipo_aula)
);


-- ---------- Conflictos detectados ----------
CREATE TABLE conflicto (
    id           SERIAL      PRIMARY KEY,
    ejecucion_id INTEGER     NOT NULL REFERENCES ejecucion(id) ON DELETE CASCADE,
    clase_id     INTEGER     NOT NULL REFERENCES clase(id),
    restriccion  VARCHAR(60) NOT NULL,
    descripcion  TEXT
);

COMMENT ON COLUMN conflicto.restriccion IS
    'Restricción dura que impidió la asignación (RN-14, REQ-35).';


-- ============================================================
-- 7. ÍNDICES DE APOYO PARA LAS CONSULTAS
-- ============================================================

CREATE INDEX idx_asignacion_grupo   ON asignacion (grupo_id);
CREATE INDEX idx_asignacion_docente ON asignacion (docente_id);
CREATE INDEX idx_asignacion_aula    ON asignacion (aula_id);
CREATE INDEX idx_asignacion_franja  ON asignacion (franja_id);
CREATE INDEX idx_clase_grupo        ON clase (grupo_id);


-- ============================================================
-- 8. DATOS INICIALES DE LAS RESTRICCIONES BLANDAS
-- ============================================================

INSERT INTO restriccion_blanda (codigo, nombre, descripcion, activa, peso) VALUES
 ('RB_VENTANAS',    'Evitar huecos prolongados',
  'Evitar espacios vacíos largos entre clases de un mismo grupo o docente.', TRUE,  4),
 ('RB_PREF_DOCENTE','Priorizar profesores preferidos',
  'Procurar asignar al docente en sus franjas preferidas.',                  TRUE,  3),
 ('RB_EQUILIBRIO',  'Equilibrar carga semanal',
  'Evitar concentrar la carga de un grupo en pocos días.',                   FALSE, 2),
 ('RB_CONSECUTIVAS','Evitar clases consecutivas excesivas',
  'Limitar el número de bloques seguidos de un docente o grupo.',            FALSE, 2),
 ('RB_CAMBIO_AULA', 'Minimizar cambios de aula',
  'Procurar que un grupo permanezca en la misma aula.',                      FALSE, 1);


-- ============================================================
-- 9. CONSULTA DE EJEMPLO: HORARIO DE UN GRUPO
-- ============================================================
--
-- SELECT f.dia_semana, f.hora_inicio, f.hora_fin,
--        a.nombre AS asignatura, d.nombre AS docente, au.codigo AS aula
--   FROM asignacion asg
--   JOIN clase          c  ON c.id  = asg.clase_id
--   JOIN asignatura     a  ON a.id  = c.asignatura_id
--   JOIN docente        d  ON d.id  = asg.docente_id
--   JOIN aula           au ON au.id = asg.aula_id
--   JOIN franja_horaria f  ON f.id  = asg.franja_id
--  WHERE asg.grupo_id = 1
--  ORDER BY f.dia_semana, f.hora_inicio;
