from django.db import models

PERFILES = [
    ('administrador', 'Administrador'),
    ('consultor', 'Consultor'),
]

TIPOS_AULA = [
    ('convencional', 'Convencional'),
    ('laboratorio', 'Laboratorio'),
    ('sala_sistemas', 'Sala de sistemas'),
]

ESTADOS_EJECUCION = [
    ('completa', 'Completa'),
    ('parcial', 'Parcial'),
    ('fallida', 'Fallida'),
]

DIAS_SEMANA = [
    (1, 'Lunes'),
    (2, 'Martes'),
    (3, 'Miércoles'),
    (4, 'Jueves'),
    (5, 'Viernes'),
    (6, 'Sábado'),
    (7, 'Domingo'),
]

class Usuario(models.Model):
    nombre_usuario = models.CharField(unique=True, max_length=50)
    nombre_completo = models.CharField(max_length=120)
    contrasena_hash = models.CharField(max_length=255)
    perfil = models.CharField(max_length=20, choices=PERFILES)
    activo = models.BooleanField(default=True)
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    class Meta:
        managed = False
        db_table = 'usuario'


class FranjaHoraria(models.Model):
    dia_semana = models.SmallIntegerField(choices=DIAS_SEMANA)
    hora_inicio = models.TimeField()
    hora_fin = models.TimeField()

    class Meta:
        managed = False
        db_table = 'franja_horaria'
        unique_together = (('dia_semana', 'hora_inicio', 'hora_fin'),)


class Aula(models.Model):
    codigo = models.CharField(unique=True, max_length=20)
    ubicacion = models.CharField(max_length=100, blank=True, null=True)
    capacidad = models.IntegerField()
    tipo = models.CharField(max_length=20, default='convencional', choices=TIPOS_AULA)

    class Meta:
        managed = False
        db_table = 'aula'
        unique_together = (('id', 'tipo'),)


class Asignatura(models.Model):
    codigo = models.CharField(unique=True, max_length=20)
    nombre = models.CharField(max_length=120)
    intensidad_horaria = models.SmallIntegerField()
    tipo_aula_requerida = models.CharField(max_length=20, default='convencional', choices=TIPOS_AULA)

    class Meta:
        managed = False
        db_table = 'asignatura'
        unique_together = (('id', 'tipo_aula_requerida'),)


class Docente(models.Model):
    identificacion = models.CharField(unique=True, max_length=20)
    nombre = models.CharField(max_length=120)
    correo = models.CharField(max_length=120, blank=True, null=True)
    activo = models.BooleanField(default=True)

    class Meta:
        managed = False
        db_table = 'docente'


class Grupo(models.Model):
    codigo = models.CharField(unique=True, max_length=20)
    programa = models.CharField(max_length=100, blank=True, null=True)
    semestre = models.SmallIntegerField(blank=True, null=True)
    cantidad_estudiantes = models.IntegerField()

    class Meta:
        managed = False
        db_table = 'grupo'


class DocenteAsignatura(models.Model):
    pk = models.CompositePrimaryKey('docente_id', 'asignatura_id')
    docente = models.ForeignKey(Docente, models.DO_NOTHING)
    asignatura = models.ForeignKey(Asignatura, models.DO_NOTHING)

    class Meta:
        managed = False
        db_table = 'docente_asignatura'


class DisponibilidadDocente(models.Model):
    pk = models.CompositePrimaryKey('docente_id', 'franja_id')
    docente = models.ForeignKey(Docente, models.DO_NOTHING)
    franja = models.ForeignKey(FranjaHoraria, models.DO_NOTHING)
    preferida = models.BooleanField(default=False)

    class Meta:
        managed = False
        db_table = 'disponibilidad_docente'


class Clase(models.Model):
    grupo = models.ForeignKey(Grupo, models.DO_NOTHING)
    asignatura = models.ForeignKey(Asignatura, models.DO_NOTHING)
    docente = models.ForeignKey(Docente, models.DO_NOTHING)
    sesiones_semanales = models.SmallIntegerField(default=1)
    tipo_aula = models.CharField(max_length=20, editable=False)

    class Meta:
        managed = False
        db_table = 'clase'
        unique_together = (('id', 'tipo_aula'), ('grupo', 'asignatura'), ('id', 'docente', 'grupo'),)

    def save(self, *args, **kwargs):
        self.tipo_aula = self.asignatura.tipo_aula_requerida
        super().save(*args, **kwargs)


class RestriccionBlanda(models.Model):
    codigo = models.CharField(unique=True, max_length=30)
    nombre = models.CharField(max_length=120)
    descripcion = models.TextField(blank=True, null=True)
    activa = models.BooleanField(default=True)
    peso = models.SmallIntegerField(default=1)

    class Meta:
        managed = False
        db_table = 'restriccion_blanda'


class Ejecucion(models.Model):
    fecha = models.DateTimeField(auto_now_add=True)
    usuario = models.ForeignKey(Usuario, models.DO_NOTHING, blank=True, null=True)
    estado = models.CharField(max_length=20, choices=ESTADOS_EJECUCION)
    clases_totales = models.IntegerField(default=0)
    clases_asignadas = models.IntegerField(default=0)

    class Meta:
        managed = False
        db_table = 'ejecucion'


class Asignacion(models.Model):
    ejecucion = models.ForeignKey(Ejecucion, models.DO_NOTHING)
    clase = models.ForeignKey(Clase, models.DO_NOTHING)
    aula = models.ForeignKey(Aula, models.DO_NOTHING)
    franja = models.ForeignKey(FranjaHoraria, models.DO_NOTHING)
    docente = models.ForeignKey(Docente, models.DO_NOTHING)
    grupo = models.ForeignKey(Grupo, models.DO_NOTHING)
    tipo_aula = models.CharField(max_length=20)

    class Meta:
        managed = False
        db_table = 'asignacion'
        unique_together = (('aula', 'franja'), ('docente', 'franja'), ('grupo', 'franja'),)


class Conflicto(models.Model):
    ejecucion = models.ForeignKey(Ejecucion, models.DO_NOTHING)
    clase = models.ForeignKey(Clase, models.DO_NOTHING)
    restriccion = models.CharField(max_length=60)
    descripcion = models.TextField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'conflicto'

