from django.contrib import messages
from django.contrib.auth.hashers import check_password, make_password
from django.shortcuts import render, redirect

from nucleo.models import Usuario

from .decoradores import requiere_perfil


def pagina_inicio(perfil):
    """A dónde va cada perfil después de iniciar sesión."""
    return 'dashboard' if perfil == 'administrador' else 'mis_horarios'


def iniciar_sesion(request):
    # Si ya inició sesión, no tiene sentido mostrarle el login otra vez
    if 'usuario_id' in request.session:
        return redirect(pagina_inicio(request.session.get('perfil')))

    if request.method == 'POST':
        nombre = request.POST.get('usuario', '')
        contrasena = request.POST.get('contrasena', '')

        # Solo usuarios activos (si se olvida activo=True, ocurre el BUG-01)
        usuario = Usuario.objects.filter(nombre_usuario=nombre, activo=True).first()

        if usuario and check_password(contrasena, usuario.contrasena_hash):
            # "Ponerle la manilla": guardar en la sesión quién es y su perfil
            request.session['usuario_id'] = usuario.id
            request.session['perfil'] = usuario.perfil
            request.session['nombre'] = usuario.nombre_completo
            return redirect(pagina_inicio(usuario.perfil))

        # El mismo mensaje si el usuario no existe o si la contraseña está mal
        messages.error(request, 'Usuario o contraseña incorrectos.')

    return render(request, 'cuentas/login.html')


def cerrar_sesion(request):
    # "Quitarle la manilla": borrar todo lo guardado en la sesión
    request.session.flush()
    return redirect('login')


@requiere_perfil('administrador', 'consultor')
def ajustes(request):
    """Ajustes de la cuenta: datos del usuario y cambio de contraseña."""
    usuario = Usuario.objects.select_related('docente').get(id=request.session['usuario_id'])

    if request.method == 'POST':
        actual = request.POST.get('actual', '')
        nueva = request.POST.get('nueva', '')
        confirmar = request.POST.get('confirmar', '')

        if not check_password(actual, usuario.contrasena_hash):
            messages.error(request, 'La contraseña actual no es correcta.')
        elif len(nueva) < 3:
            messages.error(request, 'La nueva contraseña debe tener al menos 3 caracteres.')
        elif nueva != confirmar:
            messages.error(request, 'La nueva contraseña y su confirmación no coinciden.')
        else:
            usuario.contrasena_hash = make_password(nueva)   # siempre cifrada (RNF-07)
            usuario.save(update_fields=['contrasena_hash'])
            messages.success(request, 'Contraseña actualizada correctamente.')
            return redirect('ajustes')

    plantilla = 'base_generar.html' if usuario.perfil == 'consultor' else 'base.html'
    return render(request, 'cuentas/ajustes.html', {'usuario': usuario, 'plantilla': plantilla})


# ================= Gestión de usuarios (solo administrador) =================
from django import forms
from django.db import IntegrityError
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.views.decorators.http import require_POST

from nucleo.models import Docente, PERFILES


class UsuarioForm(forms.ModelForm):
    contrasena = forms.CharField(label='Contraseña', required=False, widget=forms.PasswordInput(render_value=False),
                                 help_text='Al editar, déjela vacía para no cambiarla.')

    class Meta:
        model = Usuario
        fields = ['nombre_usuario', 'nombre_completo', 'perfil', 'docente', 'activo']
        labels = {'nombre_usuario': 'Usuario', 'nombre_completo': 'Nombre completo', 'perfil': 'Perfil',
                  'docente': 'Docente vinculado', 'activo': 'Activo'}
        error_messages = {'nombre_usuario': {'unique': 'Ya existe un usuario con ese nombre.'}}
        help_texts = {'docente': 'Solo para el perfil Docente: con quién se relaciona para ver «Mis Horarios».'}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['perfil'].widget = forms.Select(choices=PERFILES)
        self.fields['docente'].queryset = Docente.objects.order_by('nombre')
        self.fields['docente'].required = False
        for nombre, campo in self.fields.items():
            if nombre == 'activo':
                campo.widget.attrs['class'] = 'form-check-input'
            elif isinstance(campo.widget, forms.Select):
                campo.widget.attrs['class'] = 'form-select'
            else:
                campo.widget.attrs['class'] = 'form-control'

    def clean(self):
        datos = super().clean()
        if not self.instance.pk and len(datos.get('contrasena') or '') < 3:
            self.add_error('contrasena', 'La contraseña debe tener al menos 3 caracteres.')
        elif datos.get('contrasena') and len(datos['contrasena']) < 3:
            self.add_error('contrasena', 'La contraseña debe tener al menos 3 caracteres.')
        if datos.get('perfil') == 'administrador':
            datos['docente'] = None
        docente = datos.get('docente')
        if docente and Usuario.objects.filter(docente=docente).exclude(pk=self.instance.pk).exists():
            self.add_error('docente', 'Ese docente ya está vinculado a otro usuario.')
        return datos

    def save(self, commit=True):
        usuario = super().save(commit=False)
        if self.cleaned_data.get('contrasena'):
            usuario.contrasena_hash = make_password(self.cleaned_data['contrasena'])   # siempre cifrada (RNF-07)
        if commit:
            usuario.save()
        return usuario


@requiere_perfil('administrador')
def usuarios(request):
    yo = request.session['usuario_id']
    filas = []
    for u in Usuario.objects.select_related('docente').order_by('perfil', 'nombre_usuario'):
        acciones = [{'texto': 'Editar', 'icono': 'bi-pencil', 'url': reverse('usuario_editar', args=[u.id])}]
        if u.id != yo:
            acciones.append({'texto': 'Desactivar' if u.activo else 'Activar', 'post': True,
                             'icono': 'bi-toggle-on' if u.activo else 'bi-toggle-off',
                             'url': reverse('usuario_estado', args=[u.id])})
            acciones.append({'texto': 'Eliminar', 'icono': 'bi-trash', 'post': True, 'clase': 'btn-outline-danger',
                             'url': reverse('usuario_eliminar', args=[u.id]),
                             'confirmar': f'¿Eliminar el usuario {u.nombre_usuario}?'})
        filas.append({'celdas': [u.nombre_usuario, u.nombre_completo, u.get_perfil_display(),
                                 u.docente.nombre if u.docente else '—',
                                 'Activo' if u.activo else 'Inactivo'],
                      'acciones': acciones})
    return render(request, 'crud/lista.html', {
        'titulo': 'Configuración · Usuarios', 'icono': 'bi-gear', 'filas': filas,
        'columnas': ['Usuario', 'Nombre', 'Perfil', 'Docente vinculado', 'Estado'],
        'url_crear': reverse('usuario_crear'),
        'botones_extra': [{'texto': 'Mi cuenta', 'icono': 'bi-person-circle', 'url': reverse('ajustes')}],
    })


def _formulario_usuario(request, usuario=None):
    form = UsuarioForm(request.POST or None, instance=usuario)
    if request.method == 'POST' and form.is_valid():
        if usuario and usuario.id == request.session['usuario_id'] and (
                not form.cleaned_data['activo'] or form.cleaned_data['perfil'] != 'administrador'):
            messages.error(request, 'No puede desactivarse ni quitarse el perfil de administrador a sí mismo.')
        else:
            try:
                form.save()
            except IntegrityError:
                messages.error(request, 'Ya existe un usuario con ese nombre.')
            else:
                messages.success(request, 'Usuario guardado correctamente.')
                return redirect('usuarios')
    return render(request, 'crud/formulario.html', {
        'form': form, 'titulo': 'Editar usuario' if usuario else 'Nuevo usuario', 'icono': 'bi-person-gear',
        'url_volver': reverse('usuarios'),
    })


@requiere_perfil('administrador')
def usuario_crear(request):
    return _formulario_usuario(request)


@requiere_perfil('administrador')
def usuario_editar(request, id):
    return _formulario_usuario(request, get_object_or_404(Usuario, pk=id))


@require_POST
@requiere_perfil('administrador')
def usuario_estado(request, id):
    usuario = get_object_or_404(Usuario, pk=id)
    if usuario.id == request.session['usuario_id']:
        messages.error(request, 'No puede desactivarse a sí mismo.')
    else:
        usuario.activo = not usuario.activo
        usuario.save(update_fields=['activo'])
        messages.success(request, f'Usuario {usuario.nombre_usuario} {"activado" if usuario.activo else "desactivado"}.')
    return redirect('usuarios')


@require_POST
@requiere_perfil('administrador')
def usuario_eliminar(request, id):
    usuario = get_object_or_404(Usuario, pk=id)
    if usuario.id == request.session['usuario_id']:
        messages.error(request, 'No puede eliminarse a sí mismo.')
    else:
        try:
            usuario.delete()
        except IntegrityError:
            messages.error(request, 'No se pudo eliminar: el usuario tiene registros asociados. Desactívelo en su lugar.')
        else:
            messages.success(request, 'Usuario eliminado.')
    return redirect('usuarios')
