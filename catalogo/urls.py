from django.urls import path

from . import views

urlpatterns = [
    path('grupos/acomodar/', views.acomodar_grupos, name='acomodar_grupos'),
    path('docentes/<int:id>/disponibilidad/', views.disponibilidad, name='disponibilidad'),
    path('<str:catalogo>/', views.lista, name='catalogo_lista'),
    path('<str:catalogo>/nuevo/', views.crear, name='catalogo_crear'),
    path('<str:catalogo>/<int:id>/editar/', views.editar, name='catalogo_editar'),
    path('<str:catalogo>/<int:id>/eliminar/', views.eliminar, name='catalogo_eliminar'),
]
