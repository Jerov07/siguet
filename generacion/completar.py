"""Asignar salón y hora solo a las clases que no tienen (por ejemplo, las de un grupo nuevo),
sin tocar el horario que ya existe ni los cambios manuales."""
from collections import Counter

from django.db import transaction

from nucleo.models import Asignacion, Clase, Conflicto, Ejecucion

from . import algoritmo, datos
from .guardado import bloquear_horario

CAMPOS = ('clase_id', 'aula_id', 'franja_id', 'docente_id', 'grupo_id', 'tipo_aula')


def _pendientes(existentes):
    """Clases a las que les faltan sesiones por ubicar (con cuántas les faltan)."""
    hechas = Counter(a['clase_id'] for a in existentes)
    pendientes = []
    for clase in datos.clases():
        faltan = clase['sesiones'] - hechas[clase['id']]
        if faltan > 0:
            pendientes.append(dict(clase, sesiones=faltan))
    return pendientes


def hay_pendientes():
    if not Ejecucion.objects.exists():
        return False
    return bool(_pendientes(list(Asignacion.objects.values(*CAMPOS))))


def asignar_pendientes():
    """Devuelve None si nunca se ha generado el horario; si no, cuántas clases se ubicaron y cuáles no."""
    with transaction.atomic():
        bloquear_horario()   # nadie más escribe el horario mientras tanto
        ejecucion = Ejecucion.objects.order_by('-id').first()
        if ejecucion is None:
            return None

        existentes = list(Asignacion.objects.values(*CAMPOS))
        pendientes = _pendientes(existentes)
        if not pendientes:
            return {'ubicadas': 0, 'sin_ubicar': 0, 'pendientes': 0}

        resultado = algoritmo.generar(pendientes, datos.franjas(), datos.aulas(),
                                      datos.disponibilidad(), datos.blandas_activas(), previas=existentes)

        Asignacion.objects.bulk_create([Asignacion(ejecucion=ejecucion, **a) for a in resultado['asignaciones']])
        Conflicto.objects.filter(clase_id__in=[c['id'] for c in pendientes]).delete()
        Conflicto.objects.bulk_create([Conflicto(ejecucion=ejecucion, **c) for c in resultado['conflictos']])

        # Actualizar el resumen de la ejecución (estado del dashboard y reportes)
        sesiones = Counter(Asignacion.objects.values_list('clase_id', flat=True))
        clases = list(Clase.objects.values_list('id', 'sesiones_semanales'))
        completas = sum(1 for clase_id, total in clases if sesiones[clase_id] >= total)
        ejecucion.clases_totales = len(clases)
        ejecucion.clases_asignadas = completas
        ejecucion.estado = 'completa' if completas == len(clases) else 'parcial'
        ejecucion.save(update_fields=['clases_totales', 'clases_asignadas', 'estado'])

    return {'ubicadas': resultado['clases_asignadas'],
            'sin_ubicar': len(pendientes) - resultado['clases_asignadas'],
            'pendientes': len(pendientes)}
