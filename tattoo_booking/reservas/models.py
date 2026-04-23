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
