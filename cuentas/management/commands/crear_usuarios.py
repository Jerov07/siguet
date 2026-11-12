from django.contrib.auth.hashers import make_password
from django.core.management.base import BaseCommand

from nucleo.models import Docente, Usuario

# Usuarios iniciales del prototipo. Cambiar las contraseñas antes de un despliegue real.
# (usuario, nombre completo, contraseña, perfil)
USUARIOS = [
    # ---- Administradores ----
    ('admin', 'Administrador SIGUET', 'Admin2026*', 'administrador'),
    ('Jero', 'Jero', '1808', 'administrador'),
    ('Manu', 'Manu', '1478', 'administrador'),
    ('Lizeth', 'Lizeth', '2589', 'administrador'),
    ('Jerom', 'Jerom', '3698', 'administrador'),

    # ---- Consultores (docentes que consultan horarios y salones) ----
    ('consulta', 'Usuario Consultor', 'Consulta2026*', 'consultor'),
    ('Rios', 'Rios', '123', 'consultor'),
    ('Ema', 'Ema', '456', 'consultor'),
    ('David', 'David', '789', 'consultor'),
    ('Camilo', 'Camilo', '147', 'consultor'),
    ('Andres', 'Andres', '258', 'consultor'),
    ('Miller', 'Miller', '369', 'consultor'),
    ('Alejo', 'Alejo', '159', 'consultor'),
    ('Max', 'Max', '357', 'consultor'),
]

# Docentes de prueba y el usuario con el que se vinculan.
# Las cédulas son INVENTADAS, solo para el prototipo.
# (usuario, cédula de prueba, nombre del docente)
DOCENTES = [
    ('Rios', '1000000001', 'Rios'),
    ('Ema', '1000000002', 'Ema'),
    ('David', '1000000003', 'David'),
    ('Camilo', '1000000004', 'Camilo'),
    ('Andres', '1000000005', 'Andres'),
    ('Miller', '1000000006', 'Miller'),
    ('Alejo', '1000000007', 'Alejo'),
    ('Max', '1000000008', 'Max'),
]


class Command(BaseCommand):
    help = 'Crea los usuarios iniciales de SIGUET y los docentes de prueba vinculados a ellos.'

    def handle(self, *args, **options):
        # 1. Usuarios
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

        # 2. Docentes de prueba, vinculados con su usuario
        for nombre_usuario, cedula, nombre_docente in DOCENTES:
            docente, creado = Docente.objects.get_or_create(
                identificacion=cedula, defaults={'nombre': nombre_docente})
            if creado:
                self.stdout.write(self.style.SUCCESS(f'Docente {nombre_docente} creado (cédula {cedula}).'))

            usuario = Usuario.objects.get(nombre_usuario=nombre_usuario)
            if usuario.docente_id is None:
                usuario.docente = docente
                usuario.save(update_fields=['docente'])
                self.stdout.write(self.style.SUCCESS(f'Usuario "{nombre_usuario}" vinculado con el docente {nombre_docente}.'))
