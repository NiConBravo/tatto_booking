from contextlib import nullcontext
from django.db import models
from django.core.exceptions import ValidationError

class Artista(models.Model):
    """
    Representa un tatuador del estudio.
    Ya NO tiene tarifa_hora porque ahora usamos TarifaArtista.
    """
    nombre = models.CharField(max_length=100)
    especialidad = models.CharField(max_length=50)
    experiencia = models.PositiveSmallIntegerField(
        help_text="Años de experiencia como tatuador"
    )
    activo = models.BooleanField(default=True)
    
    class Meta:
        verbose_name = "Artista"
        verbose_name_plural = "Artistas"
        ordering = ['nombre']
    
    def __str__(self):
        return f"{self.nombre} - {self.especialidad}"

class TipoTrabajo(models.TextChoices):
    """
    Enum para tipos de tatuaje.
        Django convierte esto en un CharField con validación.
    """
    PEQUEÑO = 'PEQ', 'Pequeño (< 5cm)'
    MEDIANO = 'MED', 'Mediano (5-15)'
    GRANDE = 'GRA', 'Grande (> 15cm)'
    COBERTURA = 'COB', 'Cobertura/Corrección'
    SESION_COMPLETA = 'SES', 'Sesión completa (4+ horas)'

class TarifaArtista(models.Model):
    """
    Sistema de tarifas múltiples por artista.
        Un artista puede tener diferentes precios según el tipo de trabajo.
        Las tarifas tienen vigencia temporal para mantener historial.
        """
    artista = models.ForeignKey(
        max_length= 3, choices = TipoTrabajo.choices
    )

    # Precio fijo por trabajo (ej: 80€ por un tatuaje pequeño)
    precio_base = models.DecimalField(
        max_digits = 10,
        decimal_places = 2,
        help_text = "Precio base por este tipo de trabajo"
    )

    # Precio por hora (opcional, para trabajos grandes)
    precio_hora = models.DecimalField(
        max_digits= 10,
        decimal_places= 2,
        null = True, 
        blank= True,
        help_text = "Precio por hora adicional (opcional)"
    )

    #Vigencia temporal

    vigente_desde = models.DateField(
        auto_now_add= True,
        help_text = "Fecha desde la cual esta tarifa es válida"
    )
    vigente_hasta = models.DateField(
        null = True,
        blank = True,
        help_text= "Fecha hasta la cual esta tarifa es válida (NULL = actual)"
    )

    class Meta:
        verbose_name = "Tarifa de Artista"
        verbose_name_plural = "Tarifas de Artistas"
        ordering = ['-vigente_desde']  # Más recientes primero
        
        # CONSTRAINT CRÍTICO: No puede haber dos tarifas idénticas con la misma vigencia
        constraints = [
            models.UniqueConstraint(
                fields=['artista', 'tipo_trabajo', 'vigente_desde'],
                name='unique_tarifa_vigencia'
            )
        ]
    
    def __str__(self):
        return f"{self.artista.nombre} - {self.get_tipo_trabajo_display()} - €{self.precio_base}"
    
    def clean(self):
        """
        Validación custom: vigente_hasta debe ser posterior a vigente_desde
        """
        if self.vigente_hasta and self.vigente_desde:
            if self.vigente_hasta <= self.vigente_desde:
                raise ValidationError(
                    "La fecha de fin debe ser posterior a la fecha de inicio"
                )
class DiaSemana(models.IntegerChoices):
    """
    Enum para días de la semana.
        0 = Lunes, 6 = Domingo (estándar ISO)
    """
    LUNES = 0, 'Lunes'
    MARTES = 1, 'Martes'
    MIERCOLES = 2, 'Miércoles'
    JUEVES = 3, 'Jueves'
    VIERNES = 4, 'Viernes'
    SABADO = 5, 'Sábado'
    DOMINGO = 6, 'Domingo'

class DisponibilidadArtista(models.Model):
    """
    Define los horarios de trabajo de cada artista por día de semana.
    Ejemplo: Carlos trabaja Lunes-Viernes de 10:00 a 18:00.
    """
    Artista = models.ForeignKey(
        Artista,
        ond_delete = models.CASCADE,
        related_name= 'disponibilidades'
    )
    dia_semana = models.IntegerField(
        choices = DiaSemana.choices,
        help_text= "Día de la semana (0=Lunes, 6=Domingo)"
    )

    class Meta:
        verbose_name = "Disponibilidad de Artista"
        verbose_name_plural = "Disponibilidades de Artistas"
        ordering = ['artista', 'dia_semana', 'hora_inicio']
    
    def __str__(self):
        return f"{self.artista.nombre} - {self.get_dia_semana_display()} {self.hora_inicio}-{self.hora_fin}"

    def clean(self):
        """
        Validaciones:
        1. hora_fin debe ser posterior a hora_inicio
        2. No puede solapar con otra disponibilidad del mismo artista el mismo día
        """
        #Validación 1
        if self.hora_fin <= self.hora_inicio:
            raise ValidationError("La hora de fin debe ser posterior a la de inicio")
        
        # Validación 2: Detectar solapamiento
        overlapping = DisponibilidadArtista.objects.filter(
            artista= self.artista,
            dia_semana = self.dia_semana,
            activo = True
        ).exclude(pk = self.pk) # Excluir el registro actual si es edición

        for disp in overlapping:
            # Solapan si: (nueva_inicio < existente_fin) AND (nueva_fin > existente_inicio)
            if self.hora_inicio < disp.hora_fin and self.hora_fin > disp.hora_inicio:
                raise ValidationError(
                    f"Este horario solapa con {disp.hora_inicio}-{disp.hora_fin}"
                )
class Cliente(models.Model):
    nombre = models.Charfield(max_length = 100)
    email = models.EmailField(unique= True)
    telefono = models.Charfield(max_length = 15, blank = True, null = True)
    fecha_nac = models.DateField(verbose_name= "Fecha de nacimiento")
    creado_en = models.DateTimeField(auto_now_add = True)

    class Meta:
        verbose_name = "Cliente"
        verbose_name_plural = "Clientes"
        ordering = ['-creado_en']
    
    def __str__(self):
        return f"{self.nombre} ({self.email})"

    @property
    def edad(self):
        from datetime import date
        today = date.today()
        return today.year - self.fecha_nac.year - (
            (today.month, today.day) < (self.fecha_nac.month, self.fecha_nac.day)
        )

class Reserva(models.Model):
    """
    Representa una cita agendada.
        Vincula cliente, artista y TARIFA APLICADA para trazabilidad.
    """
    PENDIENTE = 'PENDIENTE'
    CONFIRMADA = 'CONFIRMADA'
    COMPLETADA = 'COMPLETADA'
    CANCELADA = 'CANCELADA'

    ESTADO_CHOICES = [
        (PENDIENTE, 'Pendiente'),
        (CONFIRMADA, 'Confirmada'),
        (COMPLETADA, 'Completada'),
        (CANCELADA, 'Cancelada'),
    ]

    # Relaciones
    cliente = models.ForeignKey(
        Cliente,
        on_delete= models.PROTECT,
        related_name='reservas'
    )
    artista = models.ForeignKey(
        Artista,
        on_delete= models.PROTECT,
        related_name= 'reservas'
    )
    # Tipo de trabajo (debe coincidir con la tarifa aplicada)
    tipo_trabajo = models.CharField(
        max_length = 3,
        choices = TipoTrabajo.choices
    )

    # ¡CLAVE! Guarda QUÉ tarifa se usó para calcular el precio
        # Si la tarifa cambia después, esta reserva conserva el precio original
    tarifa_aplicada = models.ForeignKey(
        TarifaArtista,
        on_delete= models.Protect, # NO eliminar tarifas usadas en reservas
        null = True, # Permitir NULL temporalmente al crear
        blank = True,
        related_name = 'reservas'
    )

    # FECHA Y HORA
    fecha = models.DateField()
    hora_inicio = models.TimeField()
    duracion_horas= models.DecimalField(max_digits=3, decimal_places=1)

    #Descripción
    descripcion = models.TextField(blank=True)

    # PRECIO FINAL calculado
    precio_final = models.DecimalField(
        max_digits= 10,
        decimal_places = 2,
        help_text = 'Precio total calculado según tarifa aplicada'
    )

    #Estado
    estado = models.CharField(
        max_length= 20,
        choices = ESTADO_CHOICES,
        default = PENDIENTE
    )

    #TIMESTAMPS

    creada_en = models.DateTimeField(auto_now_add=True)
    actualizada_en = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Reserva"
        verbose_name_plural = "Reservas"
        ordering = ['fecha', 'hora_inicio']
        indexes = [
            models.Index(fields=['fecha', 'artista']),
            models.Index(fields=['estado']),
        ]
    def __str__(self):
        """
            Validaciones complejas:
            1. Cliente debe ser mayor de 18
            2. Artista debe estar disponible ese día y hora
            3. No debe solapar con otra reserva del mismo artista
            4. tipo_trabajo debe coincidir con tarifa_aplicada
        """
        #Validación 1: Edad
        if self.cliente and self.cliente.edad < 18:
            raise ValidationError("El cliente debe ser mayor de 18 años")
        #Validación 2: Disponibilidad del artista
        if self.fecha and self.hora_inicio and self.artista:
            dia_semana = self.fecha.weekday() #0= Lunes, 6= Domingo
            disponibilidades = DisponibilidadArtista.objects.filter(
                artista=self.artista,
                dia_semana=dia_semana,
                activo=True
            )
            #Calcular hora_fin de la reserva
            from datetime import datetime, timedelta
            hora_fin_reserva = (
                datetime.combine(self.fecha, self.hora_inicio) + 
                timedelta(hours=float(self.duracion_horas))
            ).time()

            #Verificar que esté dentro de alguna disponibilidad
            dentro_de_horario = False
            for disp in disponibilidades:
                if disp.hora_inicio <= self.hora_inicio and disp.hora_fin >= hora_fin_reserva:
                    dentro_de_horario= True
                    break
            if not dentro_de_horario:
                raise ValidationError(
                    f"{self.artista.nombre} no está disponible en este horario"
                )
        #Validación 3: No solapar con otras reservas
        if self.fecha and self.hora_inicio and self.artista:
            from datetime import datetime, timedelta

            hora_fin = (
                datetime.combine(self.fecha, self.hora_inicio) +
                timedelta(hours=float(self.duracion_horas))
            ).time()

            # Buscar reservas del mismo artista el mismo día
            reservas_existentes = Reserva.objects.filter(
                artista=self.artista,
                fecha=self.artista,
                estado__in=[Reserva.PENDIENTE, Reserva.CONFIRMADA]
            ).exclude(pk=self.pk)

            for reserva in reservas_existentes:
                # Calcular hora_fin de la reserva existente
                hora_fin_existente = (
                    datetime.combine(reserva.fecha, reserva.hora_inicio) + 
                    timedelta(hours=float(reserva.duracion_horas))
                ).time()
                #Detectar solapamiento
                if self.hora_inicio < hora_fin_existente and hora_fin > reserva.hora_inicio:
                    raise ValidationError(f"El artista ya tiene una reserva de {reserva.hora_inicio} a {hora_fin_existente}")
        #Validación 4: Coherencia tarifa-tipo
        if self.artista_aplicada and self.tipo_trabajo:
            if self.tarifa_aplicada.tipo_trabajo != self.tipo_trabajo:
                raise ValidationError(
                    "El tipo de trabajo no coincide con la tarifa aplicada"
                )
    def calcular_precio (self):
        """
            Calcula el precio final según la tarifa aplicada.
            Usa precio_base + (precio_hora * duracion) si aplica.
        """
        if not self.tarifa_aplicada:
            return 0
        precio = self.artista_aplica.precio_base
        
        if self.tarifa_aplicada.precio_hora:
            precio += self.tarifa_aplicada.precio_hora * float(self.duracion_horas)
        return precio
    def save(self, *args, **kwargs):
        """
            Override de save para:
            1. Buscar la tarifa vigente si no se especificó
            2. Calcular precio_final automáticamente
            3. Validar todo antes de guardar
        """
        # Si no ha tarifa asignada, buscar la vigente
        if not self.tarifa_aplicada and self.artista and self.tipo_trabajo and self.fecha:
            tarifa_vigente = TarifaArtista.objects.filter(
                artista = self.artista,
                tipo_trabajo= self.tipo_trabajo,
                vigente_desde__lte=self.fecha
            ).filter(
                models.Qmodels.Q(vigente_hasta__gte=self.fecha) | models.Q(vigente_hasta__isnull=True)
            ).first()

            if tarifa_vigente:
                self.tarifa_aplicada = tarifa_vigente
            else:
                raise ValidationError(
                    f"No existe tarifa vigente para {self.get_tipo_trabajo_display()} "
                    f"del artista {self.artista.nombre} en la fecha {self.fecha}"
                )
        # Calcular precio si no se especificó
        if not self.precio_final or self.precio_final == 0:
            self.precio_final = self.calcular_precio()
        # Validar todo
        self.full_clean()
        super().save(*args, **kwargs)
