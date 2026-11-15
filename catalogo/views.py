import json

from django.contrib import messages
from django.db import IntegrityError, transaction
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from cuentas.decoradores import requiere_perfil
from generacion.completar import hay_pendientes
from nucleo.models import (Asignacion, Asignatura, Aula, Clase, Docente, DocenteAsignatura,
                           DisponibilidadDocente, FranjaHoraria, Grupo, DIAS_SEMANA)

from .forms import (MAXIMO_POR_GRUPO, MINIMO_POR_GRUPO, AsignaturaForm, AulaForm, ClaseForm, DocenteForm,
                    FranjaForm, GrupoForm, dividir_grupo, repartir)

SOLO_ADMIN = requiere_perfil('administrador')

# Mensajes claros para los errores de la base de datos (RNF-01)
ERRORES_BD = {
    'ex_franja_sin_solape': 'La franja se cruza con otra del mismo día.',
    'uq_clase_grupo_asignatura': 'Ese grupo ya tiene esa asignatura.',
    'fk_clase_docente_capacitado': 'No se puede quitar una materia que el docente tiene asignada en Clases. Cambie primero el docente de esa clase.',
}


def mensaje_error(error, accion='guardar'):
    nombre = getattr(getattr(error.__cause__, 'diag', None), 'constraint_name', None)
    return ERRORES_BD.get(nombre, f'No se pudo {accion} porque el registro está siendo usado por clases '
                                  f'o por el horario generado.')


def _horas(f):
    return f'{f.hora_inicio:%H:%M} - {f.hora_fin:%H:%M}'


# ----- Configuración de cada catálogo: modelo, formulario y columnas de la lista -----
CATALOGOS = {
    'asignaturas': {
        'modelo': Asignatura, 'form': AsignaturaForm, 'titulo': 'Materias', 'singular': 'materia',
        'icono': 'bi-book', 'orden': ['nombre'],
        'columnas': ['Código', 'Nombre', 'Horas semanales', 'Tipo de aula'],
        'fila': lambda o: [o.codigo, o.nombre, o.intensidad_horaria, o.get_tipo_aula_requerida_display()],
    },
    'docentes': {
        'modelo': Docente, 'form': DocenteForm, 'titulo': 'Docentes', 'singular': 'docente',
        'icono': 'bi-person', 'orden': ['nombre'],
        'columnas': ['Identificación', 'Nombre', 'Correo', 'Materias', 'Franjas disponibles', 'Estado'],
        'fila': lambda o: [o.identificacion, o.nombre, o.correo or '—',
                           ', '.join(DocenteAsignatura.objects.filter(docente=o)
                                     .values_list('asignatura__nombre', flat=True)) or '—',
                           DisponibilidadDocente.objects.filter(docente=o).count(),
                           'Activo' if o.activo else 'Inactivo'],
    },
    'grupos': {
        'modelo': Grupo, 'form': GrupoForm, 'titulo': 'Grupos Académicos', 'singular': 'grupo',
        'icono': 'bi-people', 'orden': ['codigo'],
        'columnas': ['Código', 'Programa', 'Semestre', 'Estudiantes'],
        'fila': lambda o: [o.codigo, o.programa or '—', o.semestre or '—',
                           f'{o.cantidad_estudiantes} (pasa de 30)' if o.cantidad_estudiantes > 30 else o.cantidad_estudiantes],
    },
    'aulas': {
        'modelo': Aula, 'form': AulaForm, 'titulo': 'Aulas y Espacios', 'singular': 'aula',
        'icono': 'bi-bank', 'orden': ['codigo'],
        'columnas': ['Código', 'Ubicación', 'Capacidad', 'Tipo'],
        'fila': lambda o: [o.codigo, o.ubicacion or '—', o.capacidad, o.get_tipo_display()],
    },
    'franjas': {
        'modelo': FranjaHoraria, 'form': FranjaForm, 'titulo': 'Franjas Horarias', 'singular': 'franja',
        'icono': 'bi-clock', 'orden': ['dia_semana', 'hora_inicio'],
        'columnas': ['Día', 'Horario', 'Duración'],
        'fila': lambda o: [o.get_dia_semana_display(), _horas(o),
                           f'{(o.hora_fin.hour * 60 + o.hora_fin.minute - o.hora_inicio.hour * 60 - o.hora_inicio.minute) / 60:g} h'],
    },
    'clases': {
        'modelo': Clase, 'form': ClaseForm, 'titulo': 'Clases', 'singular': 'clase',
        'icono': 'bi-easel', 'orden': ['grupo__codigo', 'asignatura__nombre'],
        'columnas': ['Grupo', 'Asignatura', 'Docente', 'Sesiones', 'Tipo de aula'],
        'fila': lambda o: [o.grupo.codigo, o.asignatura.nombre, o.docente.nombre,
                           f'{o.sesiones_semanales} × {o.asignatura.intensidad_horaria // o.sesiones_semanales} h',
                           o.asignatura.get_tipo_aula_requerida_display()],
    },
}


def _config(catalogo):
    if catalogo not in CATALOGOS:
        raise Http404
    return CATALOGOS[catalogo]


@SOLO_ADMIN
def lista(request, catalogo):
    cfg = _config(catalogo)
    objetos = cfg['modelo'].objects.order_by(*cfg['orden'])
    if catalogo == 'clases':
        objetos = objetos.select_related('grupo', 'asignatura', 'docente')

    filas = []
    for obj in objetos:
        acciones = [{'texto': 'Editar', 'icono': 'bi-pencil', 'url': reverse('catalogo_editar', args=[catalogo, obj.pk])}]
        if catalogo == 'docentes':
            acciones.append({'texto': 'Disponibilidad', 'icono': 'bi-calendar-week',
                             'url': reverse('disponibilidad', args=[obj.pk])})
        acciones.append({'texto': 'Eliminar', 'icono': 'bi-trash', 'post': True, 'clase': 'btn-outline-danger',
                         'url': reverse('catalogo_eliminar', args=[catalogo, obj.pk]),
                         'confirmar': f'¿Eliminar esta {cfg["singular"]}?' if cfg['singular'] in ('materia', 'franja', 'clase', 'aula') else f'¿Eliminar este {cfg["singular"]}?'})
        filas.append({'celdas': cfg['fila'](obj), 'acciones': acciones})

    botones = []
    if catalogo == 'grupos' and objetos.filter(cantidad_estudiantes__gt=MAXIMO_POR_GRUPO).exists():
        botones.append({'texto': f'Acomodar grupos de más de {MAXIMO_POR_GRUPO}', 'icono': 'bi-diagram-2',
                        'url': reverse('acomodar_grupos'), 'post': True})
    if catalogo == 'grupos' and hay_pendientes():
        botones.append({'texto': 'Asignar salón a los grupos sin horario', 'icono': 'bi-door-open',
                        'url': reverse('asignar_pendientes'), 'post': True, 'volver': request.path})
    return render(request, 'crud/lista.html', {
        'titulo': cfg['titulo'], 'icono': cfg['icono'], 'columnas': cfg['columnas'], 'filas': filas,
        'url_crear': reverse('catalogo_crear', args=[catalogo]), 'botones_extra': botones,
    })


@require_POST
@SOLO_ADMIN
def acomodar_grupos(request):
    """Un solo botón: divide todos los grupos de más de 30 estudiantes (los sobrantes, mínimo 10, forman otro grupo)."""
    creados, sin_acomodar = [], []
    with transaction.atomic():
        for grupo in Grupo.objects.filter(cantidad_estudiantes__gt=MAXIMO_POR_GRUPO).order_by('codigo'):
            if repartir(grupo.cantidad_estudiantes)[-1] < MINIMO_POR_GRUPO:
                sin_acomodar.append(grupo)
            else:
                creados += [(grupo, nuevo) for nuevo in dividir_grupo(grupo)]
    if creados:
        detalle = ', '.join(f'{nuevo.codigo} ({nuevo.cantidad_estudiantes} est.)' for _, nuevo in creados)
        messages.success(request, f'Se abrieron {len(creados)} grupo(s) nuevos con sus clases: {detalle}. '
                                  f'Ahora pulse «Asignar salón a los grupos sin horario».')
    for grupo in sin_acomodar:
        sobran = repartir(grupo.cantidad_estudiantes)[-1]
        messages.warning(request, f'{grupo.codigo} tiene {grupo.cantidad_estudiantes} estudiantes: sobran {sobran} y se '
                                  f'necesitan mínimo {MINIMO_POR_GRUPO} para abrir otro grupo. Ajuste la cantidad a mano.')
    if not creados and not sin_acomodar:
        messages.info(request, 'Todos los grupos ya tienen 30 estudiantes o menos.')
    return redirect('catalogo_lista', 'grupos')


def _formulario(request, catalogo, obj=None):
    cfg = _config(catalogo)
    form = cfg['form'](request.POST or None, instance=obj)

    if request.method == 'POST' and form.is_valid():
        try:
            with transaction.atomic():
                guardado = form.save()
                if catalogo == 'docentes':
                    form.guardar_materias(guardado)
                nuevos = form.dividir(guardado) if catalogo == 'grupos' else []
        except IntegrityError as error:
            messages.error(request, mensaje_error(error))
        else:
            messages.success(request, f'{cfg["singular"].capitalize()} guardada correctamente.'
                             if cfg['singular'] in ('materia', 'franja', 'clase', 'aula')
                             else f'{cfg["singular"].capitalize()} guardado correctamente.')
            for nuevo in nuevos:
                messages.info(request, f'El grupo pasaba de 30 estudiantes: se abrió el grupo {nuevo.codigo} con '
                                       f'{nuevo.cantidad_estudiantes} estudiantes y las mismas clases. '
                                       f'Pulse «Asignar salón a los grupos sin horario» para darle su espacio.')
            return redirect('catalogo_lista', catalogo)

    script = ''
    if catalogo == 'clases':
        # Para filtrar la lista de docentes según la asignatura escogida
        mapa = {}
        for docente_id, asignatura_id in DocenteAsignatura.objects.values_list('docente_id', 'asignatura_id'):
            mapa.setdefault(asignatura_id, []).append(docente_id)
        script = f'<script>const DOCENTES_POR_MATERIA = {json.dumps(mapa)};</script>' + SCRIPT_FILTRO_DOCENTES

    accion = 'Editar' if obj else 'Nueva' if cfg['singular'] in ('materia', 'franja', 'clase', 'aula') else 'Nuevo'
    return render(request, 'crud/formulario.html', {
        'form': form, 'titulo': f'{accion} {cfg["singular"]}', 'icono': cfg['icono'],
        'url_volver': reverse('catalogo_lista', args=[catalogo]), 'script_extra': script,
    })


SCRIPT_FILTRO_DOCENTES = '''
<script>
  // Muestra en la lista de docentes solo los que dictan la asignatura escogida
  const listaAsignatura = document.getElementById('id_asignatura');
  const listaDocente = document.getElementById('id_docente');
  function filtrarDocentes() {
    const permitidos = DOCENTES_POR_MATERIA[listaAsignatura.value] || [];
    Array.from(listaDocente.options).forEach(function (opcion) {
      if (!opcion.value) { return; }
      const visible = permitidos.includes(Number(opcion.value));
      opcion.hidden = !visible;
      if (!visible && opcion.selected) { listaDocente.value = ''; }
    });
  }
  listaAsignatura.addEventListener('change', filtrarDocentes);
  filtrarDocentes();
</script>
'''


@SOLO_ADMIN
def crear(request, catalogo):
    return _formulario(request, catalogo)


@SOLO_ADMIN
def editar(request, catalogo, id):
    obj = get_object_or_404(_config(catalogo)['modelo'], pk=id)
    return _formulario(request, catalogo, obj)


@require_POST
@SOLO_ADMIN
def eliminar(request, catalogo, id):
    cfg = _config(catalogo)
    obj = get_object_or_404(cfg['modelo'], pk=id)
    try:
        with transaction.atomic():
            obj.delete()
    except IntegrityError as error:
        messages.error(request, mensaje_error(error, 'eliminar'))
    else:
        messages.success(request, 'Registro eliminado.')
    return redirect('catalogo_lista', catalogo)


@SOLO_ADMIN
def disponibilidad(request, id):
    """Cuadrícula día x franja para marcar cuándo puede dictar el docente y cuándo prefiere (función 4)."""
    docente = get_object_or_404(Docente, pk=id)
    franjas = list(FranjaHoraria.objects.order_by('dia_semana', 'hora_inicio'))
    actuales = dict(DisponibilidadDocente.objects.filter(docente=docente).values_list('franja_id', 'preferida'))

    if request.method == 'POST':
        nuevas = {}
        for f in franjas:
            valor = request.POST.get(f'franja_{f.id}', 'no')
            if valor in ('si', 'preferida'):
                nuevas[f.id] = valor == 'preferida'
        quitar = set(actuales) - set(nuevas)
        ocupadas = set(Asignacion.objects.filter(docente=docente, franja_id__in=quitar).values_list('franja_id', flat=True))
        if ocupadas:
            nombres = ', '.join(f'{f.get_dia_semana_display()} {_horas(f)}' for f in franjas if f.id in ocupadas)
            messages.error(request, f'No se puede quitar {nombres}: el docente tiene clase asignada ahí. '
                                    f'Mueva la clase o vuelva a generar el horario primero.')
        else:
            with transaction.atomic():
                DisponibilidadDocente.objects.filter(docente=docente, franja_id__in=quitar).delete()
                for franja_id, preferida in nuevas.items():
                    if franja_id in actuales:
                        if actuales[franja_id] != preferida:
                            DisponibilidadDocente.objects.filter(docente=docente, franja_id=franja_id).update(preferida=preferida)
                    else:
                        DisponibilidadDocente.objects.create(docente=docente, franja_id=franja_id, preferida=preferida)
            messages.success(request, 'Disponibilidad guardada.')
            return redirect('catalogo_lista', 'docentes')

    # Armar la cuadrícula: filas = rangos de hora, columnas = días con franjas
    dias = [d for d in DIAS_SEMANA if any(f.dia_semana == d[0] for f in franjas)]
    horas = sorted({(f.hora_inicio, f.hora_fin) for f in franjas})
    por_clave = {(f.dia_semana, f.hora_inicio, f.hora_fin): f for f in franjas}
    filas = []
    for inicio, fin in horas:
        celdas = []
        for numero, _ in dias:
            f = por_clave.get((numero, inicio, fin))
            estado = None if not f else ('preferida' if actuales.get(f.id) else 'si' if f.id in actuales else 'no')
            celdas.append({'franja': f, 'estado': estado})
        filas.append({'hora': f'{inicio:%H:%M}-{fin:%H:%M}', 'celdas': celdas})

    return render(request, 'catalogo/disponibilidad.html', {'docente': docente, 'dias': dias, 'filas': filas})
