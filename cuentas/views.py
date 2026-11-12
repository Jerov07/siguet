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
