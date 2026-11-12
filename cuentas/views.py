from django.contrib import messages
from django.contrib.auth.hashers import check_password
from django.shortcuts import render, redirect

from nucleo.models import Usuario


def iniciar_sesion(request):
    # Si ya inició sesión, no tiene sentido mostrarle el login otra vez
    if 'usuario_id' in request.session:
        return redirect('dashboard')

    if request.method == 'POST':
        nombre = request.POST.get('usuario', '')
        contrasena = request.POST.get('contrasena', '')

        # Solo usuarios activos (si se olvida activo=True, ocurre el BUG-01)
        usuario = Usuario.objects.filter(nombre_usuario=nombre, activo=True).first()

        if usuario and check_password(contrasena, usuario.contrasena_hash):
            # "Ponerle la manilla": guardar en la sesión quién es y su perfil
            request.session['usuario_id'] = usuario.id
            request.session['perfil'] = usuario.perfil
            request.session['perfil_nombre'] = usuario.get_perfil_display()   # 'Administrador' o 'Docente'
            request.session['nombre'] = usuario.nombre_completo
            return redirect('dashboard')

        # El mismo mensaje si el usuario no existe o si la contraseña está mal
        messages.error(request, 'Usuario o contraseña incorrectos.')

    return render(request, 'cuentas/login.html')


def cerrar_sesion(request):
    # "Quitarle la manilla": borrar todo lo guardado en la sesión
    request.session.flush()
    return redirect('login')
