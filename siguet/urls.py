from django.urls import path, include

urlpatterns = [
    path('cuentas/', include('cuentas.urls')),
    path('generacion/', include('generacion.urls')),
    path('', include('consultas.urls')),
]
