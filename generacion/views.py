from django.core.paginator import Paginator
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_POST

from cuentas.decoradores import requiere_perfil
from nucleo.models import Asignacion, Conflicto, Ejecucion, RestriccionBlanda

# Orden en que se muestran los interruptores (el mismo del mockup)
ORDEN_RESTRICCIONES = ['RB_VENTANAS', 'RB_CAMBIO_AULA', 'RB_EQUILIBRIO', 'RB_PREF_DOCENTE', 'RB_CONSECUTIVAS']

# Límite de tiempo del algoritmo en segundos (RNF-05). La pantalla lo muestra como 03:00 min.
LIMITE_SEGUNDOS = 180


@requiere_perfil('administrador', 'consultor')
def generar_horario(request):
    """Pantalla 'Generar Horario': restricciones blandas, control de ejecución y log."""
    ultima = Ejecucion.objects.first()

    # Log: cada asignación es 'Validado' y cada conflicto es 'Pendiente'
    log = []
    if ultima:
        for a in (Asignacion.objects.filter(ejecucion=ultima)
                  .select_related('clase__asignatura', 'grupo')):
            log.append({'asignatura': a.clase.asignatura.nombre, 'grupo': a.grupo.codigo,
                        'conflicto': 'Sin conflicto', 'estado': 'Validado'})
        for c in (Conflicto.objects.filter(ejecucion=ultima)
                  .select_related('clase__asignatura', 'clase__grupo')):
            log.append({'asignatura': c.clase.asignatura.nombre, 'grupo': c.clase.grupo.codigo,
                        'conflicto': c.restriccion, 'estado': 'Pendiente'})

    pagina = Paginator(log, 5).get_page(request.GET.get('pagina'))

    return render(request, 'generacion/generar.html', {
        'restricciones': sorted(
            RestriccionBlanda.objects.all(),
            key=lambda r: ORDEN_RESTRICCIONES.index(r.codigo) if r.codigo in ORDEN_RESTRICCIONES else 99),
        'limite_segundos': LIMITE_SEGUNDOS,
        'pagina': pagina,
        'total_log': len(log),
    })


@require_POST
@requiere_perfil('administrador', 'consultor')
def cambiar_restriccion(request, id):
    """Activa o desactiva una restricción blanda. La llama el JavaScript del interruptor."""
    restriccion = get_object_or_404(RestriccionBlanda, id=id)
    restriccion.activa = request.POST.get('activa') == 'true'
    restriccion.save(update_fields=['activa'])
    return JsonResponse({'ok': True, 'activa': restriccion.activa})


@require_POST
@requiere_perfil('administrador', 'consultor')
def ejecutar(request):
    """Ejecuta el algoritmo de generación. Se implementa en el siguiente paso."""
    return JsonResponse({
        'ok': False,
        'mensaje': 'El algoritmo de generación todavía no está implementado.',
    })
