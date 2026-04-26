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
    nombre = models.Charfield(max_lenght = 100)
    email = models.EmailField(unique= True)
    telefono = models.Charfield(max_lenght = 15, blank = True, null = True)
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
        return toda.ear - self.fecha_nac.year - (
            (today.month, today.day) < (self.fecha_nac.month, self.fecha_nac.day)
        )

class Reserva(models.Model):
    