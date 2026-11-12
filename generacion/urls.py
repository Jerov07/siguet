from django.urls import path

from . import views

urlpatterns = [
    path('', views.generar_horario, name='generar_horario'),
    path('restricciones/<int:id>/', views.cambiar_restriccion, name='cambiar_restriccion'),
    path('ejecutar/', views.ejecutar, name='ejecutar'),
    path('asignacion/<int:id>/opciones/', views.opciones_asignacion, name='opciones_asignacion'),
    path('asignacion/<int:id>/mover/', views.mover_asignacion, name='mover_asignacion'),
]
