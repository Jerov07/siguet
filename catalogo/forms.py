from django import forms

from nucleo.models import Asignatura, Aula, Clase, Docente, DocenteAsignatura, FranjaHoraria, Grupo


class EstiloBootstrap:
    """Pone las clases de Bootstrap a todos los campos del formulario."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for campo in self.fields.values():
            widget = campo.widget
            if isinstance(widget, forms.CheckboxInput):
                widget.attrs['class'] = 'form-check-input'
            elif isinstance(widget, forms.CheckboxSelectMultiple):
                pass
            elif isinstance(widget, forms.Select):
                widget.attrs['class'] = 'form-select'
            else:
                widget.attrs['class'] = 'form-control'


class AsignaturaForm(EstiloBootstrap, forms.ModelForm):
    intensidad_horaria = forms.IntegerField(label='Horas semanales', min_value=1, max_value=20)

    class Meta:
        model = Asignatura
        fields = ['codigo', 'nombre', 'intensidad_horaria', 'tipo_aula_requerida']
        labels = {'codigo': 'Código', 'nombre': 'Nombre', 'tipo_aula_requerida': 'Tipo de aula requerida'}
        error_messages = {'codigo': {'unique': 'Ya existe una materia con ese código.'}}


MAXIMO_POR_GRUPO = 30   # cupo máximo de un grupo
MINIMO_POR_GRUPO = 10   # mínimo de estudiantes para abrir un grupo


def repartir(cantidad):
    """Reparte los estudiantes en bloques de 30. Ej.: 40 -> [30, 10]; 65 -> [30, 30, 5]."""
    partes = []
    while cantidad > 0:
        partes.append(min(cantidad, MAXIMO_POR_GRUPO))
        cantidad -= MAXIMO_POR_GRUPO
    return partes


def dividir_grupo(grupo):
    """Si el grupo pasa de 30, lo deja en 30 y crea grupos nuevos (G-301-B, G-301-C...)
    con los estudiantes que sobran y una copia de sus clases, para que tengan su propio espacio."""
    partes = repartir(grupo.cantidad_estudiantes)
    if len(partes) == 1:
        return []
    grupo.cantidad_estudiantes = partes[0]
    grupo.save(update_fields=['cantidad_estudiantes'])
    nuevos, letra = [], ord('B')
    for cantidad in partes[1:]:
        while Grupo.objects.filter(codigo=f'{grupo.codigo}-{chr(letra)}').exists():
            letra += 1
        nuevo = Grupo.objects.create(codigo=f'{grupo.codigo}-{chr(letra)}', programa=grupo.programa,
                                     semestre=grupo.semestre, cantidad_estudiantes=cantidad)
        for clase in Clase.objects.filter(grupo=grupo):
            Clase.objects.create(grupo=nuevo, asignatura=clase.asignatura, docente=clase.docente,
                                 sesiones_semanales=clase.sesiones_semanales)
        nuevos.append(nuevo)
        letra += 1
    return nuevos


class GrupoForm(EstiloBootstrap, forms.ModelForm):
    cantidad_estudiantes = forms.IntegerField(
        label='Cantidad de estudiantes', min_value=MINIMO_POR_GRUPO,
        help_text=f'Máximo {MAXIMO_POR_GRUPO} por grupo. Si se pasa, el sistema abre otro grupo con los que sobran '
                  f'(mínimo {MINIMO_POR_GRUPO}), con sus mismas clases y su propio espacio en el horario.',
        error_messages={'min_value': f'Un grupo debe tener mínimo {MINIMO_POR_GRUPO} estudiantes.'})
    semestre = forms.IntegerField(label='Semestre', min_value=1, max_value=12, required=False)

    class Meta:
        model = Grupo
        fields = ['codigo', 'programa', 'semestre', 'cantidad_estudiantes']
        labels = {'codigo': 'Código', 'programa': 'Programa'}
        error_messages = {'codigo': {'unique': 'Ya existe un grupo con ese código.'}}

    def clean_cantidad_estudiantes(self):
        cantidad = self.cleaned_data['cantidad_estudiantes']
        sobran = repartir(cantidad)[-1]
        if cantidad > MAXIMO_POR_GRUPO and sobran < MINIMO_POR_GRUPO:
            raise forms.ValidationError(
                f'Con {cantidad} estudiantes sobran {sobran} después de llenar grupos de {MAXIMO_POR_GRUPO}, '
                f'y para abrir otro grupo se necesitan mínimo {MINIMO_POR_GRUPO}.')
        return cantidad

    def dividir(self, grupo):
        return dividir_grupo(grupo)


class AulaForm(EstiloBootstrap, forms.ModelForm):
    capacidad = forms.IntegerField(label='Capacidad (estudiantes)', min_value=1)

    class Meta:
        model = Aula
        fields = ['codigo', 'ubicacion', 'capacidad', 'tipo']
        labels = {'codigo': 'Código', 'ubicacion': 'Ubicación', 'tipo': 'Tipo de aula'}
        error_messages = {'codigo': {'unique': 'Ya existe un aula con ese código.'}}


class FranjaForm(EstiloBootstrap, forms.ModelForm):
    class Meta:
        model = FranjaHoraria
        fields = ['dia_semana', 'hora_inicio', 'hora_fin']
        labels = {'dia_semana': 'Día', 'hora_inicio': 'Hora de inicio', 'hora_fin': 'Hora de fin'}
        widgets = {'hora_inicio': forms.TimeInput(attrs={'type': 'time'}, format='%H:%M'),
                   'hora_fin': forms.TimeInput(attrs={'type': 'time'}, format='%H:%M')}

    def clean(self):
        datos = super().clean()
        dia, inicio, fin = datos.get('dia_semana'), datos.get('hora_inicio'), datos.get('hora_fin')
        if inicio and fin:
            if fin <= inicio:
                raise forms.ValidationError('La hora de fin debe ser mayor que la hora de inicio.')
            cruce = (FranjaHoraria.objects.filter(dia_semana=dia, hora_inicio__lt=fin, hora_fin__gt=inicio)
                     .exclude(pk=self.instance.pk))
            if cruce.exists():
                raise forms.ValidationError('La franja se cruza con otra del mismo día.')
        return datos


class DocenteForm(EstiloBootstrap, forms.ModelForm):
    materias = forms.ModelMultipleChoiceField(
        label='Materias que puede dictar', queryset=Asignatura.objects.order_by('nombre'),
        required=False, widget=forms.CheckboxSelectMultiple)

    class Meta:
        model = Docente
        fields = ['identificacion', 'nombre', 'correo', 'activo', 'materias']
        labels = {'identificacion': 'Identificación (cédula)', 'nombre': 'Nombre completo',
                  'correo': 'Correo', 'activo': 'Activo'}
        error_messages = {'identificacion': {'unique': 'Ya existe un docente con esa identificación.'}}
        widgets = {'correo': forms.EmailInput()}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            self.fields['materias'].initial = list(
                DocenteAsignatura.objects.filter(docente=self.instance).values_list('asignatura_id', flat=True))

    def guardar_materias(self, docente):
        """Sincroniza la tabla docente_asignatura con las casillas marcadas."""
        nuevas = {a.id for a in self.cleaned_data['materias']}
        actuales = set(DocenteAsignatura.objects.filter(docente=docente).values_list('asignatura_id', flat=True))
        DocenteAsignatura.objects.filter(docente=docente, asignatura_id__in=actuales - nuevas).delete()
        for asignatura_id in nuevas - actuales:
            DocenteAsignatura.objects.create(docente=docente, asignatura_id=asignatura_id)


class ClaseForm(EstiloBootstrap, forms.ModelForm):
    sesiones_semanales = forms.IntegerField(
        label='Sesiones por semana', min_value=1, max_value=10,
        help_text='En cuántos bloques se divide la intensidad horaria. Ej.: 4 horas en 2 sesiones = bloques de 2 horas.')

    class Meta:
        model = Clase
        fields = ['grupo', 'asignatura', 'docente', 'sesiones_semanales']
        labels = {'grupo': 'Grupo', 'asignatura': 'Asignatura', 'docente': 'Docente'}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['grupo'].queryset = Grupo.objects.order_by('codigo')
        self.fields['asignatura'].queryset = Asignatura.objects.order_by('nombre')
        self.fields['docente'].queryset = Docente.objects.filter(activo=True).order_by('nombre')
        for nombre in ('grupo', 'asignatura', 'docente'):
            self.fields[nombre].empty_label = 'Seleccione...'
        self.fields['docente'].help_text = 'Solo aparecen los docentes que dictan la asignatura escogida.'

    def clean(self):
        datos = super().clean()
        grupo, asignatura, docente = datos.get('grupo'), datos.get('asignatura'), datos.get('docente')
        sesiones = datos.get('sesiones_semanales')
        if asignatura and docente and not DocenteAsignatura.objects.filter(docente=docente, asignatura=asignatura).exists():
            self.add_error('docente', 'Este docente no está registrado para dictar esa asignatura.')
        if asignatura and sesiones and asignatura.intensidad_horaria % sesiones != 0:
            self.add_error('sesiones_semanales',
                           f'{asignatura.intensidad_horaria} horas no se pueden dividir en {sesiones} sesiones iguales.')
        if grupo and asignatura and Clase.objects.filter(grupo=grupo, asignatura=asignatura).exclude(pk=self.instance.pk).exists():
            self.add_error('asignatura', 'Ese grupo ya tiene esa asignatura.')
        return datos
