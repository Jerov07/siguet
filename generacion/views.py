from django.core.paginator import Paginator
from django.db import DatabaseError, IntegrityError, transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_POST

from cuentas.decoradores import requiere_perfil
from nucleo.models import Asignacion, Conflicto, Ejecucion, RestriccionBlanda, Usuario, DIAS_SEMANA

from . import algoritmo, datos, guardado
from . import reglas_duras as duras

# Orden en que se muestran los interruptores (el mismo del mockup)
ORDEN_RESTRICCIONES = ['RB_VENTANAS', 'RB_CAMBIO_AULA', 'RB_EQUILIBRIO', 'RB_PREF_DOCENTE', 'RB_CONSECUTIVAS']

# Límite de tiempo del algoritmo en segundos (RNF-05). La pantalla lo muestra como 03:00 min.
LIMITE_SEGUNDOS = algoritmo.LIMITE_SEGUNDOS


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
    """Ejecuta el algoritmo con los datos de la base y guarda el resultado (función 6)."""
    lista_clases = datos.clases()
    if not lista_clases:
        return JsonResponse({'ok': False, 'mensaje': 'No hay clases registradas para generar el horario.'})

    resultado = algoritmo.generar(lista_clases, datos.franjas(), datos.aulas(),
                                  datos.disponibilidad(), datos.blandas_activas())
    try:
        guardado.guardar(resultado, request.session['usuario_id'])
    except DatabaseError:
        return JsonResponse({'ok': False, 'mensaje': 'No se pudo guardar el horario. Intente de nuevo.'})

    estados = {'completa': 'completo', 'parcial': 'parcial', 'fallida': 'fallido'}
    mensaje = (f'Horario {estados[resultado["estado"]]}: {resultado["clases_asignadas"]} de '
               f'{resultado["clases_totales"]} clases asignadas, {len(resultado["conflictos"])} conflicto(s).')
    return JsonResponse({'ok': resultado['estado'] != 'fallida', 'mensaje': mensaje})


# ================= Edición manual del horario (función 7) =================

def _asignacion_permitida(request, asignacion):
    """El administrador puede mover cualquier clase; el docente, solo las suyas."""
    if request.session.get('perfil') == 'administrador':
        return True
    usuario = Usuario.objects.get(id=request.session['usuario_id'])
    return usuario.docente_id is not None and usuario.docente_id == asignacion.docente_id


def _opciones(asignacion):
    """Espacios válidos para mover una sesión, sin contarla a ella misma como ocupada."""
    ocupacion = duras.Ocupacion()
    for a in Asignacion.objects.exclude(id=asignacion.id).values('aula_id', 'franja_id', 'docente_id', 'grupo_id'):
        ocupacion.agregar(a)
    clase = datos.clase_a_dict(asignacion.clase)
    validas = duras.opciones_validas(clase, datos.franjas(), datos.aulas(), ocupacion, datos.disponibilidad())
    # Se quita el espacio donde ya está la clase
    return [(f, a) for f, a in validas if not (f['id'] == asignacion.franja_id and a['id'] == asignacion.aula_id)]


@requiere_perfil('administrador', 'consultor')
def opciones_asignacion(request, id):
    asignacion = get_object_or_404(Asignacion.objects.select_related('clase__asignatura', 'clase__grupo',
                                                                     'clase__docente', 'franja', 'aula'), id=id)
    if not _asignacion_permitida(request, asignacion):
        return JsonResponse({'ok': False, 'mensaje': 'Solo puede modificar sus propias clases.'}, status=403)

    dias = dict(DIAS_SEMANA)
    agrupadas = {}
    for franja, aula in _opciones(asignacion):
        clave = franja['id']
        if clave not in agrupadas:
            agrupadas[clave] = {'franja_id': franja['id'], 'dia': dias[franja['dia']],
                                'hora': f'{franja["inicio"] // 60:02d}:{franja["inicio"] % 60:02d}-'
                                        f'{franja["fin"] // 60:02d}:{franja["fin"] % 60:02d}',
                                'aulas': []}
        agrupadas[clave]['aulas'].append({'id': aula['id'], 'codigo': aula['codigo'], 'capacidad': aula['capacidad']})

    f = asignacion.franja
    return JsonResponse({
        'ok': True,
        'actual': {'asignatura': asignacion.clase.asignatura.nombre, 'grupo': asignacion.clase.grupo.codigo,
                   'dia': dias[f.dia_semana], 'hora': f'{f.hora_inicio:%H:%M}-{f.hora_fin:%H:%M}',
                   'aula': asignacion.aula.codigo},
        'opciones': list(agrupadas.values()),
    })


@require_POST
@requiere_perfil('administrador', 'consultor')
def mover_asignacion(request, id):
    try:
        franja_id = int(request.POST.get('franja_id', ''))
        aula_id = int(request.POST.get('aula_id', ''))
    except ValueError:
        return JsonResponse({'ok': False, 'mensaje': 'Datos incompletos.'}, status=400)

    try:
        with transaction.atomic():
            # Candado: si dos docentes guardan al mismo tiempo, el segundo espera al primero
            # y luego vuelve a revisar. Así nunca quedan dos clases en el mismo salón y hora.
            guardado.bloquear_horario()
            asignacion = get_object_or_404(Asignacion.objects.select_related('clase__asignatura', 'clase__grupo',
                                                                             'clase__docente'), id=id)
            if not _asignacion_permitida(request, asignacion):
                return JsonResponse({'ok': False, 'mensaje': 'Solo puede modificar sus propias clases.'}, status=403)

            validas = {(f['id'], a['id']) for f, a in _opciones(asignacion)}
            if (franja_id, aula_id) not in validas:
                return JsonResponse({'ok': False, 'mensaje': 'Ese espacio ya no está disponible: otro docente lo '
                                     'acaba de tomar o no cumple las reglas. Escoja otra opción.'}, status=409)

            asignacion.franja_id = franja_id
            asignacion.aula_id = aula_id
            asignacion.save(update_fields=['franja', 'aula'])
    except IntegrityError:
        # Red de seguridad: las restricciones UNIQUE de la base lo impidieron
        return JsonResponse({'ok': False, 'mensaje': 'Ese espacio ya está ocupado. Escoja otra opción.'}, status=409)

    return JsonResponse({'ok': True, 'mensaje': 'Clase movida correctamente.'})
