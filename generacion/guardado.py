"""Guarda el resultado del algoritmo en una sola transacción (RNF-11)."""
from django.db import connection, transaction

from nucleo.models import Asignacion, Conflicto, Ejecucion


def bloquear_horario():
    """Candado: mientras alguien genera o mueve una clase, los demás esperan su turno.
    Así dos personas nunca escriben el horario al mismo tiempo."""
    if connection.vendor == 'postgresql':
        with connection.cursor() as cursor:
            cursor.execute('SELECT pg_advisory_xact_lock(1001)')


def guardar(resultado, usuario_id):
    with transaction.atomic():
        bloquear_horario()
        # Cada ejecución reemplaza la anterior (RN-16): primero se borra, después se inserta
        Asignacion.objects.all().delete()
        Conflicto.objects.all().delete()
        Ejecucion.objects.all().delete()

        ejecucion = Ejecucion.objects.create(
            usuario_id=usuario_id, estado=resultado['estado'],
            clases_totales=resultado['clases_totales'], clases_asignadas=resultado['clases_asignadas'])
        Asignacion.objects.bulk_create([Asignacion(ejecucion=ejecucion, **a) for a in resultado['asignaciones']])
        Conflicto.objects.bulk_create([Conflicto(ejecucion=ejecucion, **c) for c in resultado['conflictos']])
    return ejecucion
