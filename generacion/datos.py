"""Lee de la base de datos lo que necesitan el algoritmo y la edición manual,
y lo convierte en listas y diccionarios sencillos."""
from nucleo.models import Aula, Clase, DisponibilidadDocente, FranjaHoraria, RestriccionBlanda


def _minutos(hora):
    return hora.hour * 60 + hora.minute


def franjas():
    return [{'id': f.id, 'dia': f.dia_semana, 'inicio': _minutos(f.hora_inicio), 'fin': _minutos(f.hora_fin),
             'horas': (_minutos(f.hora_fin) - _minutos(f.hora_inicio)) / 60}
            for f in FranjaHoraria.objects.order_by('dia_semana', 'hora_inicio')]


def aulas():
    return [{'id': a.id, 'codigo': a.codigo, 'tipo': a.tipo, 'capacidad': a.capacidad}
            for a in Aula.objects.order_by('codigo')]


def clase_a_dict(c):
    return {'id': c.id, 'docente_id': c.docente_id, 'grupo_id': c.grupo_id, 'tipo_aula': c.tipo_aula,
            'estudiantes': c.grupo.cantidad_estudiantes, 'sesiones': c.sesiones_semanales,
            'horas_sesion': c.asignatura.intensidad_horaria / c.sesiones_semanales,
            'docente_activo': c.docente.activo}


def clases():
    return [clase_a_dict(c) for c in Clase.objects.select_related('asignatura', 'grupo', 'docente')]


def disponibilidad():
    resultado = {}
    for docente_id, franja_id, preferida in DisponibilidadDocente.objects.values_list('docente_id', 'franja_id', 'preferida'):
        resultado.setdefault(docente_id, {})[franja_id] = preferida
    return resultado


def blandas_activas():
    return dict(RestriccionBlanda.objects.filter(activa=True).values_list('codigo', 'peso'))
