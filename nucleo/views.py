from django.shortcuts import render

# Create your views here.

from .models import RestriccionBlanda


def lista_restricciones(request):
    restricciones = RestriccionBlanda.objects.all()
    return render(request, 'nucleo/restricciones.html', {'restricciones': restricciones})