from django.urls import path
from nucleo import views

urlpatterns = [
    path('restricciones/', views.lista_restricciones),
]