from django.core.management.base import BaseCommand, CommandError

from nucleo.models import Docente, Usuario


class Command(BaseCommand):
    help = 'Vincula un usuario con un docente para que vea "Mis horarios". Uso: vincular_docente <usuario> <identificacion_docente>'

    def add_arguments(self, parser):
        parser.add_argument('usuario', help='Nombre de usuario, por ejemplo: Max')
        parser.add_argument('identificacion', help='Identificación (cédula) del docente')

    def handle(self, *args, **opciones):
        try:
            usuario = Usuario.objects.get(nombre_usuario=opciones['usuario'])
        except Usuario.DoesNotExist:
            raise CommandError(f'No existe el usuario "{opciones["usuario"]}".')
        try:
            docente = Docente.objects.get(identificacion=opciones['identificacion'])
        except Docente.DoesNotExist:
            raise CommandError(f'No existe un docente con identificación {opciones["identificacion"]}.')

        otro = Usuario.objects.filter(docente=docente).exclude(id=usuario.id).first()
        if otro:
            raise CommandError(f'El docente {docente.nombre} ya está vinculado al usuario "{otro.nombre_usuario}".')

        usuario.docente = docente
        usuario.save(update_fields=['docente'])
        self.stdout.write(self.style.SUCCESS(f'Usuario "{usuario.nombre_usuario}" vinculado con el docente {docente.nombre}.'))
