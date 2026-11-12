"""Restricciones duras de SIGUET (RNF-19).

Estas reglas son OBLIGATORIAS y no se pueden desactivar. Las usan:
  - el algoritmo de generación (algoritmo.py), y
  - la edición manual del horario (views.py: opciones_asignacion y mover_asignacion).

Trabajan con diccionarios sencillos para no depender de la base de datos
(así se pueden probar solas):
  clase   = {'id', 'docente_id', 'grupo_id', 'tipo_aula', 'estudiantes', 'horas_sesion', ...}
  franja  = {'id', 'dia', 'inicio', 'fin', 'horas'}       # inicio y fin en minutos desde las 00:00
  aula    = {'id', 'codigo', 'tipo', 'capacidad'}
  disponibilidad = {docente_id: {franja_id: preferida}}
"""


class Ocupacion:
    """Lleva la cuenta de qué aula, docente y grupo están ocupados en cada franja."""

    def __init__(self):
        self.aulas = set()      # {(aula_id, franja_id)}
        self.docentes = set()   # {(docente_id, franja_id)}
        self.grupos = set()     # {(grupo_id, franja_id)}

    def agregar(self, asignacion):
        self.aulas.add((asignacion['aula_id'], asignacion['franja_id']))
        self.docentes.add((asignacion['docente_id'], asignacion['franja_id']))
        self.grupos.add((asignacion['grupo_id'], asignacion['franja_id']))


# ---------- Las 7 reglas duras ----------

def aula_libre(ocupacion, aula_id, franja_id):
    """RN-07: un aula no puede tener dos clases en la misma franja."""
    return (aula_id, franja_id) not in ocupacion.aulas


def docente_libre(ocupacion, docente_id, franja_id):
    """RN-05: un docente no puede estar en dos clases en la misma franja."""
    return (docente_id, franja_id) not in ocupacion.docentes


def grupo_libre(ocupacion, grupo_id, franja_id):
    """RN-06: un grupo no puede tener dos clases en la misma franja."""
    return (grupo_id, franja_id) not in ocupacion.grupos


def docente_disponible(disponibilidad, docente_id, franja_id):
    """RN-09: la franja debe estar en la disponibilidad registrada del docente."""
    return franja_id in disponibilidad.get(docente_id, {})


def tipo_correcto(aula, clase):
    """El aula debe ser del tipo que requiere la asignatura."""
    return aula['tipo'] == clase['tipo_aula']


def capacidad_suficiente(aula, clase):
    """El aula debe tener cupo para todos los estudiantes del grupo (solo lo valida el código)."""
    return aula['capacidad'] >= clase['estudiantes']


def duracion_correcta(franja, clase):
    """La franja debe durar lo mismo que una sesión: intensidad horaria / sesiones semanales."""
    return abs(franja['horas'] - clase['horas_sesion']) < 0.01


# ---------- Funciones que combinan las reglas ----------

def opciones_validas(clase, franjas, aulas, ocupacion, disponibilidad):
    """Todas las combinaciones (franja, aula) donde se puede poner una sesión de la clase
    sin romper ninguna regla dura."""
    opciones = []
    for franja in franjas:
        if not (duracion_correcta(franja, clase)
                and docente_disponible(disponibilidad, clase['docente_id'], franja['id'])
                and docente_libre(ocupacion, clase['docente_id'], franja['id'])
                and grupo_libre(ocupacion, clase['grupo_id'], franja['id'])):
            continue
        for aula in aulas:
            if (tipo_correcto(aula, clase)
                    and capacidad_suficiente(aula, clase)
                    and aula_libre(ocupacion, aula['id'], franja['id'])):
                opciones.append((franja, aula))
    return opciones


def causa_conflicto(clase, franjas, aulas, ocupacion, disponibilidad):
    """Explica por qué una clase no se pudo ubicar: la primera regla que deja cero opciones."""
    aulas_tipo = [a for a in aulas if tipo_correcto(a, clase)]
    if not aulas_tipo:
        return 'No hay aulas del tipo requerido'
    if not [a for a in aulas_tipo if capacidad_suficiente(a, clase)]:
        return 'Ninguna aula tiene capacidad para el grupo'
    franjas_docente = [f for f in franjas if duracion_correcta(f, clase)
                       and docente_disponible(disponibilidad, clase['docente_id'], f['id'])]
    if not franjas_docente:
        return 'Docente sin disponibilidad en franjas de la duración'
    return 'Todas las franjas posibles están ocupadas'
