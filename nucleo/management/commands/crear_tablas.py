"""Crea las tablas de SIGUET con el script bd/siguet_bd.sql, solo si todavía no existen.
Sirve para preparar la base de datos del servidor sin tener que abrir pgAdmin."""
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import connection


class Command(BaseCommand):
    help = 'Crea las tablas de SIGUET si la base está vacía.'

    def handle(self, *args, **opciones):
        if 'usuario' in connection.introspection.table_names():
            self.stdout.write('Las tablas de SIGUET ya existen: no se cambia nada.')
            return
        script = Path(settings.BASE_DIR, 'bd', 'siguet_bd.sql').read_text(encoding='utf-8')
        with connection.cursor() as cursor:
            cursor.execute(script)
        self.stdout.write(self.style.SUCCESS('Tablas de SIGUET creadas.'))
