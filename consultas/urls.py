from django.urls import path

from . import views

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('consultas/horario/', views.horario, name='horario'),
    path('consultas/mis-horarios/', views.mis_horarios, name='mis_horarios'),
    path('consultas/asignaturas/', views.asignaturas, name='consulta_asignaturas'),
    path('consultas/aulas/', views.aulas, name='consulta_aulas'),
    path('consultas/reportes/', views.reportes, name='reportes'),
]
