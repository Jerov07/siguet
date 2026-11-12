from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.db import connection, transaction

# Nombres de las restricciones blandas, iguales a los del mockup
NOMBRES_MOCKUP = {
    'RB_VENTANAS': 'Evitar huecos prolongados',
    'RB_PREF_DOCENTE': 'Priorizar profesores preferidos',
    'RB_EQUILIBRIO': 'Equilibrar carga semanal',
    'RB_CAMBIO_AULA': 'Minimizar cambios de aula',
}


def existe_columna(cursor, tabla, columna):
    cursor.execute(
        """SELECT 1 FROM information_schema.columns
           WHERE table_schema = 'public' AND table_name = %s AND column_name = %s""",
        [tabla, columna])
    return cursor.fetchone() is not None


class Command(BaseCommand):
    help = ('Aplica a la base los cambios pendientes de SIGUET (columnas nuevas y nombres) '
            'y crea los usuarios y docentes de prueba. Se puede ejecutar varias veces sin dañar nada.')

    def handle(self, *args, **options):
        with transaction.atomic(), connection.cursor() as cursor:
            # 1. Franjas preferidas del docente
            if not existe_columna(cursor, 'disponibilidad_docente', 'preferida'):
                cursor.execute('ALTER TABLE disponibilidad_docente '
                               'ADD COLUMN preferida BOOLEAN NOT NULL DEFAULT FALSE')
                self.stdout.write(self.style.SUCCESS('Columna disponibilidad_docente.preferida agregada.'))
            else:
                self.stdout.write('La columna disponibilidad_docente.preferida ya existe.')

            # 2. Vínculo usuario - docente (para "Mis horarios")
            if not existe_columna(cursor, 'usuario', 'docente_id'):
                cursor.execute('ALTER TABLE usuario ADD COLUMN docente_id INTEGER UNIQUE '
                               'REFERENCES docente(id) ON DELETE SET NULL')
                self.stdout.write(self.style.SUCCESS('Columna usuario.docente_id agregada.'))
            else:
                self.stdout.write('La columna usuario.docente_id ya existe.')

            # 3. Nombres de las restricciones blandas como en el mockup
            for codigo, nombre in NOMBRES_MOCKUP.items():
                cursor.execute('UPDATE restriccion_blanda SET nombre = %s WHERE codigo = %s AND nombre <> %s',
                               [nombre, codigo, nombre])
                if cursor.rowcount:
                    self.stdout.write(self.style.SUCCESS(f'Restricción {codigo} renombrada a "{nombre}".'))
            self.stdout.write('Nombres de las restricciones blandas al día.')

        # 4. Usuarios y docentes de prueba
        call_command('crear_usuarios', stdout=self.stdout)

        self.stdout.write(self.style.SUCCESS('\nListo: la base de datos está actualizada.'))
