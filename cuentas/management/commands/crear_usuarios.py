from django.contrib.auth.hashers import make_password
from django.core.management.base import BaseCommand

from nucleo.models import Usuario

# Usuarios iniciales del prototipo. Cambiar las contraseñas antes de un despliegue real.
USUARIOS = [
    ('admin', 'Administrador SIGUET', 'Admin2026*', 'administrador'),
    ('consulta', 'Usuario Consultor', 'Consulta2026*', 'consultor'),
]


class Command(BaseCommand):
    help = 'Crea los usuarios iniciales de SIGUET (un administrador y un consultor).'

    def handle(self, *args, **options):
        for nombre, nombre_completo, contrasena, perfil in USUARIOS:
            if Usuario.objects.filter(nombre_usuario=nombre).exists():
                self.stdout.write(f'El usuario "{nombre}" ya existe; no se modificó.')
                continue
            Usuario.objects.create(
                nombre_usuario=nombre,
                nombre_completo=nombre_completo,
                contrasena_hash=make_password(contrasena),  # contraseña cifrada (RNF-07)
                perfil=perfil,
            )
            self.stdout.write(self.style.SUCCESS(f'Usuario "{nombre}" creado ({perfil}).'))
