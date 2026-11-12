from django.db.models import Count
from django.shortcuts import render

from cuentas.decoradores import requiere_perfil
from nucleo.models import (Asignacion, Asignatura, Aula, Conflicto, Docente,
                           Ejecucion, FranjaHoraria, Grupo, Usuario, DIAS_SEMANA)

AMBOS = ('administrador', 'consultor')

# Colores de las tarjetas del horario semanal (uno por asignatura)
COLORES = ['#3b7ddd', '#d9534f', '#5cb85c', '#f0ad4e', '#8e6bd6', '#17a2b8', '#e83e8c', '#6c757d']


def _porcentaje(parte, total):
    return round(parte * 100 / total) if total else 0


@requiere_perfil(*AMBOS)
def dashboard(request):
    total_aulas = Aula.objects.count()
    ultima = Ejecucion.objects.first()   # solo se guarda la última ejecución

    # Ocupación promedio por día: asignaciones del día / (franjas del día x aulas)
    franjas_por_dia = dict(FranjaHoraria.objects.values_list('dia_semana').annotate(n=Count('id')))
    asig_por_dia = dict(Asignacion.objects.values_list('franja__dia_semana').annotate(n=Count('id')))
    nombres_dias = dict(DIAS_SEMANA)
    ocupacion_dias = [
        {'dia': nombres_dias[dia],
         'porcentaje': _porcentaje(asig_por_dia.get(dia, 0), franjas_por_dia[dia] * total_aulas)}
        for dia in sorted(franjas_por_dia)
    ]

    # Aulas más utilizadas: asignaciones del aula / total de franjas
    total_franjas = FranjaHoraria.objects.count()
    aulas_top = [
        {'codigo': fila['aula__codigo'], 'porcentaje': _porcentaje(fila['n'], total_franjas)}
        for fila in Asignacion.objects.values('aula__codigo').annotate(n=Count('id')).order_by('-n')[:3]
    ]

    return render(request, 'consultas/dashboard.html', {
        'total_materias': Asignatura.objects.count(),
        'total_docentes': Docente.objects.filter(activo=True).count(),
        'total_aulas': total_aulas,
        'ultima_ejecucion': ultima,
        'total_conflictos': Conflicto.objects.count(),
        'ocupacion_dias': ocupacion_dias,
        'aulas_top': aulas_top,
        'hay_asignaciones': Asignacion.objects.exists(),
    })


def _cuadricula(filtro):
    """Arma la cuadrícula semanal (filas = horas, columnas = días) con las asignaciones filtradas.

    filtro: diccionario para .filter(), por ejemplo {'grupo_id': 3} o {'docente_id': 5}.
    """
    asignaciones = (Asignacion.objects
                    .select_related('clase__asignatura', 'docente', 'aula', 'grupo', 'franja')
                    .filter(**filtro))

    # Columnas: lunes a sábado (y domingo solo si hay franjas ese día)
    hay_domingo = FranjaHoraria.objects.filter(dia_semana=7).exists()
    dias = [d for d in DIAS_SEMANA if d[0] <= 6 or hay_domingo]

    # Filas: cada rango de horas distinto (07:00-09:00, 09:00-11:00, ...)
    horas = sorted(set(FranjaHoraria.objects.values_list('hora_inicio', 'hora_fin')))

    celdas = {}
    for a in asignaciones:
        clave = (a.franja.dia_semana, a.franja.hora_inicio, a.franja.hora_fin)
        a.color = COLORES[a.clase.asignatura_id % len(COLORES)]
        celdas.setdefault(clave, []).append(a)

    filas = [
        {'hora': f'{inicio:%H:%M}-{fin:%H:%M}',
         'celdas': [celdas.get((num, inicio, fin), []) for num, _ in dias]}
        for inicio, fin in horas
    ]
    return dias, filas


@requiere_perfil(*AMBOS)
def horario(request):
    """Vista semanal del horario, filtrada por grupo, docente o aula (función 8)."""
    vista = request.GET.get('vista', 'grupo')
    if vista not in ('grupo', 'docente', 'aula'):
        vista = 'grupo'

    opciones = {
        'grupo': [(g.id, g.codigo) for g in Grupo.objects.order_by('codigo')],
        'docente': [(d.id, d.nombre) for d in Docente.objects.order_by('nombre')],
        'aula': [(a.id, a.codigo) for a in Aula.objects.order_by('codigo')],
    }[vista]

    # Elemento escogido: el que viene en la dirección o, si no, el primero de la lista
    seleccionado = request.GET.get('id')
    if not seleccionado and opciones:
        seleccionado = str(opciones[0][0])

    if seleccionado:
        dias, filas = _cuadricula({f'{vista}_id': seleccionado})
    else:
        dias, filas = _cuadricula({'id__in': []})

    return render(request, 'consultas/horario.html', {
        'vista': vista,
        'opciones': opciones,
        'seleccionado': seleccionado,
        'dias': dias,
        'filas': filas,
    })


@requiere_perfil('consultor')
def mis_horarios(request):
    """Horario del docente que inició sesión (usa el vínculo usuario.docente_id)."""
    usuario = Usuario.objects.select_related('docente').get(id=request.session['usuario_id'])
    docente = usuario.docente

    dias, filas = _cuadricula({'docente_id': docente.id} if docente else {'id__in': []})
    total_clases = sum(len(celda) for fila in filas for celda in fila['celdas'])

    return render(request, 'consultas/mis_horarios.html', {
        'docente': docente,
        'dias': dias,
        'filas': filas,
        'total_clases': total_clases,
    })


@requiere_perfil(*AMBOS)
def asignaturas(request):
    """Materias registradas y en cuántos grupos se dictan (solo consulta)."""
    lista = (Asignatura.objects.annotate(grupos=Count('clase', distinct=True))
             .order_by('nombre'))
    return render(request, 'consultas/asignaturas.html', {'asignaturas': lista})


@requiere_perfil(*AMBOS)
def aulas(request):
    """Aulas con su capacidad, tipo y ocupación (solo consulta)."""
    total_franjas = FranjaHoraria.objects.count()
    lista = Aula.objects.annotate(usos=Count('asignacion')).order_by('codigo')
    for aula in lista:
        aula.ocupacion = _porcentaje(aula.usos, total_franjas)
    return render(request, 'consultas/aulas.html', {'aulas': lista})


@requiere_perfil(*AMBOS)
def reportes(request):
    """Conflictos, materias no programadas y ocupación de aulas (función 9)."""
    total_franjas = FranjaHoraria.objects.count()
    ocupacion = Aula.objects.annotate(usos=Count('asignacion')).order_by('-usos', 'codigo')
    for aula in ocupacion:
        aula.ocupacion = _porcentaje(aula.usos, total_franjas)

    conflictos = (Conflicto.objects
                  .select_related('clase__asignatura', 'clase__grupo', 'clase__docente')
                  .order_by('clase__asignatura__nombre'))

    return render(request, 'consultas/reportes.html', {
        'ultima_ejecucion': Ejecucion.objects.first(),
        'conflictos': conflictos,
        'ocupacion': ocupacion,
    })
