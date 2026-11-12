from .models import Conflicto


def avisos(request):
    """Datos que necesitan todas las pantallas: el número de la campana de avisos.

    La campana cuenta los conflictos pendientes de la última generación.
    """
    if 'usuario_id' not in request.session:
        return {}
    return {'total_avisos': Conflicto.objects.count()}
