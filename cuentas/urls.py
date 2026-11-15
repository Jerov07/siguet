from django.urls import path

from . import views

urlpatterns = [
    path('login/', views.iniciar_sesion, name='login'),
    path('logout/', views.cerrar_sesion, name='logout'),
    path('ajustes/', views.ajustes, name='ajustes'),
    path('usuarios/', views.usuarios, name='usuarios'),
    path('usuarios/nuevo/', views.usuario_crear, name='usuario_crear'),
    path('usuarios/<int:id>/editar/', views.usuario_editar, name='usuario_editar'),
    path('usuarios/<int:id>/estado/', views.usuario_estado, name='usuario_estado'),
    path('usuarios/<int:id>/eliminar/', views.usuario_eliminar, name='usuario_eliminar'),
]
