"""Algoritmo de generación del horario (función 6).

Recibe listas y diccionarios y devuelve asignaciones y conflictos.
No usa la base de datos: eso lo hacen datos.py (leer) y guardado.py (guardar).
"""
import time

from . import reglas_duras as duras
from .reglas_blandas import penalizacion

LIMITE_SEGUNDOS = 180   # RNF-05: límite de tiempo (03:00 min)


def _conflicto(clase, restriccion, descripcion=''):
    return {'clase_id': clase['id'], 'restriccion': restriccion[:60], 'descripcion': descripcion}


def generar(clases, franjas, aulas, disponibilidad, blandas, limite_segundos=LIMITE_SEGUNDOS):
    inicio = time.monotonic()
    ocupacion = duras.Ocupacion()
    franja_por_id = {f['id']: f for f in franjas}
    asignaciones, conflictos = [], []
    clases_completas = 0

    # Primero las clases más difíciles de ubicar: menos franjas posibles y grupos más grandes
    def dificultad(clase):
        posibles = sum(1 for f in franjas if duras.duracion_correcta(f, clase)
                       and duras.docente_disponible(disponibilidad, clase['docente_id'], f['id']))
        return (posibles, -clase['estudiantes'], clase['id'])

    for clase in sorted(clases, key=dificultad):
        if not clase['docente_activo']:
            conflictos.append(_conflicto(clase, 'El docente está inactivo'))
            continue

        ubicadas = 0
        for numero in range(1, clase['sesiones'] + 1):
            if time.monotonic() - inicio > limite_segundos:
                conflictos.append(_conflicto(clase, 'Se alcanzó el tiempo límite'))
                break

            opciones = duras.opciones_validas(clase, franjas, aulas, ocupacion, disponibilidad)
            if not opciones:
                causa = duras.causa_conflicto(clase, franjas, aulas, ocupacion, disponibilidad)
                conflictos.append(_conflicto(clase, causa, f'Sesión {numero} de {clase["sesiones"]} sin ubicar'))
                break

            # La opción con menor penalización; en empate, el día y la hora más tempranos
            franja, aula = min(opciones, key=lambda o: (
                penalizacion(clase, o[0], o[1], asignaciones, franja_por_id, disponibilidad, blandas),
                o[0]['dia'], o[0]['inicio'], o[1]['codigo']))

            nueva = {'clase_id': clase['id'], 'aula_id': aula['id'], 'franja_id': franja['id'],
                     'docente_id': clase['docente_id'], 'grupo_id': clase['grupo_id'],
                     'tipo_aula': clase['tipo_aula']}
            asignaciones.append(nueva)
            ocupacion.agregar(nueva)
            ubicadas += 1

        if ubicadas == clase['sesiones']:
            clases_completas += 1

    if clases and clases_completas == len(clases):
        estado = 'completa'
    elif asignaciones:
        estado = 'parcial'
    else:
        estado = 'fallida'

    return {
        'estado': estado,
        'asignaciones': asignaciones,
        'conflictos': conflictos,
        'clases_totales': len(clases),
        'clases_asignadas': clases_completas,
    }
