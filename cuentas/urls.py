from django.urls import path

from . import views

urlpatterns = [
    path('login/', views.iniciar_sesion, name='login'),
    path('logout/', views.cerrar_sesion, name='logout'),
    path('ajustes/', views.ajustes, name='ajustes'),
]
