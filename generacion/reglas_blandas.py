"""Restricciones blandas: preferencias que el algoritmo INTENTA cumplir.

Cada restricción activa suma (peso x penalización) a una opción. El algoritmo
escoge la opción con menor penalización total. Los códigos son los de la tabla
restriccion_blanda; 'blandas' es {codigo: peso} solo con las restricciones activas.
"""


def _hueco(franja, otras):
    """Horas vacías entre esta franja y la clase más cercana del mismo día."""
    if not otras:
        return 0
    distancia = min(max(0, o['inicio'] - franja['fin'], franja['inicio'] - o['fin']) for o in otras)
    return distancia / 60


def _seguidas(franja, otras):
    """Cuántas clases quedan pegadas a esta (justo antes o justo después)."""
    return sum(1 for o in otras if o['fin'] == franja['inicio'] or o['inicio'] == franja['fin'])


def penalizacion(clase, franja, aula, asignaciones, franja_por_id, disponibilidad, blandas):
    total = 0
    del_dia = [a for a in asignaciones if franja_por_id[a['franja_id']]['dia'] == franja['dia']]
    grupo_dia = [franja_por_id[a['franja_id']] for a in del_dia if a['grupo_id'] == clase['grupo_id']]
    docente_dia = [franja_por_id[a['franja_id']] for a in del_dia if a['docente_id'] == clase['docente_id']]

    # Regla interna: dos sesiones de la misma clase no deberían caer el mismo día
    if any(a['clase_id'] == clase['id'] for a in del_dia):
        total += 100

    if 'RB_VENTANAS' in blandas:        # Evitar huecos prolongados
        total += blandas['RB_VENTANAS'] * (_hueco(franja, grupo_dia) + _hueco(franja, docente_dia))

    if 'RB_EQUILIBRIO' in blandas:      # Equilibrar carga semanal
        total += blandas['RB_EQUILIBRIO'] * len(grupo_dia)

    if 'RB_PREF_DOCENTE' in blandas:    # Priorizar profesores preferidos
        preferida = disponibilidad.get(clase['docente_id'], {}).get(franja['id'], False)
        if not preferida:
            total += blandas['RB_PREF_DOCENTE']

    if 'RB_CAMBIO_AULA' in blandas:     # Minimizar cambios de aula
        aulas_grupo = [a['aula_id'] for a in asignaciones if a['grupo_id'] == clase['grupo_id']]
        if aulas_grupo:
            mas_usada = max(set(aulas_grupo), key=aulas_grupo.count)
            if aula['id'] != mas_usada:
                total += blandas['RB_CAMBIO_AULA']

    if 'RB_CONSECUTIVAS' in blandas:    # Evitar clases consecutivas excesivas (más de 2 seguidas)
        if _seguidas(franja, grupo_dia) >= 2 or _seguidas(franja, docente_dia) >= 2:
            total += blandas['RB_CONSECUTIVAS']

    return total
