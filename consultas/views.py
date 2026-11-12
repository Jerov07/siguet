from django.db.models import Count
from django.shortcuts import render

from cuentas.decoradores import requiere_perfil
from nucleo.models import (Asignacion, Asignatura, Aula, Conflicto, Docente,
                           Ejecucion, FranjaHoraria, DIAS_SEMANA)


@requiere_perfil('administrador', 'consultor')
def dashboard(request):
    total_aulas = Aula.objects.count()
    ultima = Ejecucion.objects.first()   # solo se guarda la última ejecución

    # ---- Ocupación promedio por día: asignaciones del día / (franjas del día x aulas)
    franjas_por_dia = dict(FranjaHoraria.objects.values_list('dia_semana').annotate(n=Count('id')))
    asig_por_dia = dict(Asignacion.objects.values_list('franja__dia_semana').annotate(n=Count('id')))
    nombres_dias = dict(DIAS_SEMANA)
    ocupacion_dias = []
    for dia in sorted(franjas_por_dia):
        capacidad = franjas_por_dia[dia] * total_aulas
        porcentaje = round(asig_por_dia.get(dia, 0) * 100 / capacidad) if capacidad else 0
        ocupacion_dias.append({'dia': nombres_dias[dia], 'porcentaje': porcentaje})

    # ---- Aulas más utilizadas: asignaciones del aula / total de franjas
    total_franjas = FranjaHoraria.objects.count()
    aulas_top = []
    for fila in (Asignacion.objects.values('aula__codigo')
                 .annotate(n=Count('id')).order_by('-n')[:3]):
        porcentaje = round(fila['n'] * 100 / total_franjas) if total_franjas else 0
        aulas_top.append({'codigo': fila['aula__codigo'], 'porcentaje': porcentaje})

    datos = {
        'total_materias': Asignatura.objects.count(),
        'total_docentes': Docente.objects.filter(activo=True).count(),
        'total_aulas': total_aulas,
        'ultima_ejecucion': ultima,
        'total_conflictos': Conflicto.objects.count(),
        'ocupacion_dias': ocupacion_dias,
        'aulas_top': aulas_top,
        'hay_asignaciones': Asignacion.objects.exists(),
    }
    return render(request, 'consultas/dashboard.html', datos)
