"""Carga datos de DEMOSTRACIÓN para probar SIGUET: franjas, aulas, asignaturas,
grupos, qué dicta cada docente, su disponibilidad y las clases.

Se puede ejecutar varias veces: solo crea lo que falta. Usa los docentes de prueba
de crear_usuarios (Rios, Ema, David, Camilo, Andres, Miller, Alejo, Max).
"""
import datetime

from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.db import transaction

from nucleo.models import (Asignatura, Aula, Clase, Docente, DocenteAsignatura,
                           DisponibilidadDocente, FranjaHoraria, Grupo)

HORAS = [(7, 9), (9, 11), (11, 13), (14, 16)]
DIAS = range(1, 7)   # lunes a sábado

AULAS = [   # (código, ubicación, capacidad, tipo)
    ('Aula 101', 'Bloque A, piso 1', 40, 'convencional'),
    ('Aula 102', 'Bloque A, piso 1', 35, 'convencional'),
    ('Aula 204', 'Bloque A, piso 2', 45, 'convencional'),
    ('Lab 1', 'Bloque B, piso 1', 30, 'laboratorio'),
    ('Lab 3', 'Bloque B, piso 2', 30, 'sala_sistemas'),
    ('Auditorio', 'Bloque C', 80, 'convencional'),
]

ASIGNATURAS = [   # (código, nombre, horas semanales, tipo de aula)
    ('CAL1', 'Cálculo Diferencial', 4, 'convencional'),
    ('MAT2', 'Matemáticas II', 4, 'convencional'),
    ('FIS1', 'Física I', 4, 'convencional'),
    ('PRW1', 'Programación Web', 4, 'sala_sistemas'),
    ('PSI1', 'Psicología I', 2, 'convencional'),
    ('HIS1', 'Historia Moderna', 2, 'convencional'),
    ('QUI1', 'Química General', 2, 'laboratorio'),
    ('ING1', 'Inglés I', 2, 'convencional'),
    ('EST1', 'Estadística', 2, 'convencional'),
    ('BD1', 'Bases de Datos', 4, 'sala_sistemas'),
    ('BIO1', 'Biología', 2, 'convencional'),
    ('COM1', 'Comunicación Oral', 2, 'convencional'),
]

GRUPOS = [   # (código, programa, semestre, estudiantes)
    ('G-101', 'Ingeniería', 1, 30),
    ('G-102', 'Ingeniería', 1, 28),
    ('G-201', 'Ingeniería', 3, 25),
    ('G-301', 'Psicología', 1, 40),
]

# Qué materias dicta cada docente: exactamente 2 por profe (cédula -> códigos de asignatura)
DICTA = {
    '1000000001': ['CAL1', 'MAT2'],   # Rios
    '1000000002': ['FIS1', 'EST1'],   # Ema
    '1000000003': ['PRW1', 'BD1'],    # David
    '1000000004': ['PSI1', 'HIS1'],   # Camilo
    '1000000005': ['QUI1', 'BIO1'],   # Andres
    '1000000006': ['ING1', 'COM1'],   # Miller
    '1000000007': ['CAL1', 'MAT2'],   # Alejo
    '1000000008': ['FIS1', 'PRW1'],   # Max
}

# Clases: (grupo, asignatura, cédula del docente). Cada profe dicta sus 2 materias.
CLASES = [
    # G-101 Ingeniería, semestre 1 (30 estudiantes)
    ('G-101', 'CAL1', '1000000001'), ('G-101', 'FIS1', '1000000008'), ('G-101', 'PRW1', '1000000003'),
    ('G-101', 'ING1', '1000000006'), ('G-101', 'QUI1', '1000000005'),
    # G-102 Ingeniería, semestre 1 (28 estudiantes)
    ('G-102', 'CAL1', '1000000007'), ('G-102', 'MAT2', '1000000007'), ('G-102', 'FIS1', '1000000002'),
    ('G-102', 'PRW1', '1000000008'), ('G-102', 'BD1', '1000000003'), ('G-102', 'ING1', '1000000006'),
    # G-201 Ingeniería, semestre 3 (25 estudiantes)
    ('G-201', 'MAT2', '1000000001'), ('G-201', 'EST1', '1000000002'), ('G-201', 'PRW1', '1000000003'),
    ('G-201', 'HIS1', '1000000004'), ('G-201', 'QUI1', '1000000005'), ('G-201', 'COM1', '1000000006'),
    # G-301 Psicología, semestre 1 (40 estudiantes)
    ('G-301', 'PSI1', '1000000004'), ('G-301', 'HIS1', '1000000004'), ('G-301', 'BIO1', '1000000005'),
    ('G-301', 'ING1', '1000000006'),
    # Química para 40 estudiantes: ningún laboratorio tiene cupo -> conflicto de ejemplo
    ('G-301', 'QUI1', '1000000005'),
]


class Command(BaseCommand):
    help = 'Carga datos de demostración (franjas, aulas, asignaturas, grupos, disponibilidad y clases).'

    @transaction.atomic
    def handle(self, *args, **options):
        call_command('crear_usuarios', stdout=self.stdout)   # asegura los docentes de prueba

        franjas = []
        for dia in DIAS:
            for inicio, fin in HORAS:
                franja, _ = FranjaHoraria.objects.get_or_create(
                    dia_semana=dia, hora_inicio=datetime.time(inicio), hora_fin=datetime.time(fin))
                franjas.append(franja)

        for codigo, ubicacion, capacidad, tipo in AULAS:
            Aula.objects.get_or_create(codigo=codigo, defaults={'ubicacion': ubicacion, 'capacidad': capacidad, 'tipo': tipo})

        asignaturas = {}
        for codigo, nombre, horas, tipo in ASIGNATURAS:
            asignaturas[codigo], _ = Asignatura.objects.get_or_create(
                codigo=codigo, defaults={'nombre': nombre, 'intensidad_horaria': horas, 'tipo_aula_requerida': tipo})

        grupos = {}
        for codigo, programa, semestre, estudiantes in GRUPOS:
            grupos[codigo], _ = Grupo.objects.get_or_create(
                codigo=codigo, defaults={'programa': programa, 'semestre': semestre, 'cantidad_estudiantes': estudiantes})

        docentes = {d.identificacion: d for d in Docente.objects.filter(identificacion__in=DICTA)}
        for posicion, (cedula, codigos) in enumerate(sorted(DICTA.items())):
            docente = docentes[cedula]
            for codigo in codigos:
                DocenteAsignatura.objects.get_or_create(docente=docente, asignatura=asignaturas[codigo])
            # Disponibilidad: cada docente puede de lunes a viernes por la mañana y algunas tardes;
            # sus franjas preferidas son las de 7:00 a 11:00
            for franja in franjas:
                manana = franja.hora_inicio.hour < 13
                tarde_libre = franja.hora_inicio.hour == 14 and (franja.dia_semana + posicion) % 2 == 0
                if franja.dia_semana <= 5 and (manana or tarde_libre):
                    DisponibilidadDocente.objects.get_or_create(
                        docente=docente, franja=franja,
                        defaults={'preferida': franja.hora_inicio.hour < 11})

        nuevas = 0
        for grupo, asignatura, cedula in CLASES:
            if not Clase.objects.filter(grupo=grupos[grupo], asignatura=asignaturas[asignatura]).exists():
                horas = asignaturas[asignatura].intensidad_horaria
                Clase(grupo=grupos[grupo], asignatura=asignaturas[asignatura], docente=docentes[cedula],
                      sesiones_semanales=horas // 2).save()   # sesiones de 2 horas
                nuevas += 1

        self.stdout.write(self.style.SUCCESS(
            f'\nDatos de demostración listos: {len(franjas)} franjas, {len(AULAS)} aulas, '
            f'{len(ASIGNATURAS)} asignaturas, {len(GRUPOS)} grupos, {len(CLASES)} clases ({nuevas} nuevas).'))
        self.stdout.write('Ahora entre a "Generar Horario" y pulse "Iniciar Generación de Horario".')
