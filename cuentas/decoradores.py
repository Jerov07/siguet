from functools import wraps

from django.http import HttpResponseForbidden
from django.shortcuts import redirect


def requiere_perfil(*perfiles):
    """Protege una vista: exige sesión iniciada y uno de los perfiles indicados.

    Uso:
        @requiere_perfil('administrador')                 -> solo administrador
        @requiere_perfil('administrador', 'consultor')    -> ambos perfiles
    """
    def decorador(vista):
        @wraps(vista)
        def envoltura(request, *args, **kwargs):
            # 1. ¿Tiene manilla? Si no inició sesión, va al login
            if 'usuario_id' not in request.session:
                return redirect('login')
            # 2. ¿Su manilla deja entrar aquí? Si no, acceso denegado (RNF-08)
            if request.session.get('perfil') not in perfiles:
                return HttpResponseForbidden('No tiene permiso para esta acción.')
            # 3. Todo bien: se ejecuta la vista normal
            return vista(request, *args, **kwargs)
        return envoltura
    return decorador
