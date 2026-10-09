"""MindConnect - Modelo de datos (19 tablas)."""
from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.db.models import F, Q

from .campos import TextoCifrado

User = settings.AUTH_USER_MODEL


# ---------------------------------------------------------------- usuarios
class Usuario(AbstractUser):
    """Tabla única de usuarios: paciente, profesional o administrador (RF-01, RF-03)."""

    class Rol(models.TextChoices):
        PACIENTE = "paciente", "Paciente"
        PROFESIONAL = "profesional", "Profesional"
        ADMIN = "admin", "Administrador"

    email = models.EmailField(unique=True)
    rol = models.CharField(max_length=12, choices=Rol.choices, default=Rol.PACIENTE)
    fecha_registro = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "usuario"
        verbose_name_plural = "usuarios"
        constraints = [
            models.CheckConstraint(condition=Q(rol__in=["paciente", "profesional", "admin"]), name="usuario_rol_valido")
        ]

    def __str__(self):
        return self.get_full_name() or self.username


class Consentimiento(models.Model):
    """Aceptación de términos y tratamiento de datos, con versión y fecha (RF-01, RNF-02)."""

    class Tipo(models.TextChoices):
        TERMINOS = "terminos", "Términos y condiciones"
        PRIVACIDAD = "privacidad", "Política de privacidad"
        DATOS_SENSIBLES = "datos_sensibles", "Tratamiento de datos sensibles"

    usuario = models.ForeignKey(User, on_delete=models.CASCADE, related_name="consentimientos")
    tipo = models.CharField(max_length=20, choices=Tipo.choices)
    version = models.CharField(max_length=10)
    fecha = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name_plural = "consentimientos"
        constraints = [models.UniqueConstraint(fields=["usuario", "tipo", "version"], name="consentimiento_unico")]


class Profesional(models.Model):
    """Especialización 1:1 de Usuario: id_usuario es PK y FK a la vez (RF-02)."""

    class EstadoVerificacion(models.TextChoices):
        PENDIENTE = "pendiente", "Pendiente"
        APROBADO = "aprobado", "Aprobado"
        RECHAZADO = "rechazado", "Rechazado"

    usuario = models.OneToOneField(User, on_delete=models.CASCADE, primary_key=True, related_name="perfil_profesional")
    especialidad = models.CharField(max_length=100)
    cedula_profesional = models.CharField(max_length=30, unique=True)
    tarifa_sesion = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    biografia = models.TextField(blank=True)
    estado_verificacion = models.CharField(max_length=10, choices=EstadoVerificacion.choices, default=EstadoVerificacion.PENDIENTE)
    fecha_verificacion = models.DateTimeField(null=True, blank=True)
    admin_verificador = models.ForeignKey(
        User, null=True, blank=True, on_delete=models.SET_NULL, related_name="profesionales_verificados"
    )
    documento_soporte = models.FileField(upload_to="documentos_profesionales/", blank=True)

    class Meta:
        verbose_name_plural = "profesionales"

    @property
    def verificado(self):
        return self.estado_verificacion == self.EstadoVerificacion.APROBADO

    def __str__(self):
        return f"{self.usuario} - {self.especialidad}"


class Disponibilidad(models.Model):
    """Calendario de disponibilidad semanal del profesional (RF-06)."""

    class Dia(models.IntegerChoices):
        LUNES = 0, "Lunes"
        MARTES = 1, "Martes"
        MIERCOLES = 2, "Miércoles"
        JUEVES = 3, "Jueves"
        VIERNES = 4, "Viernes"
        SABADO = 5, "Sábado"
        DOMINGO = 6, "Domingo"

    profesional = models.ForeignKey(Profesional, on_delete=models.CASCADE, related_name="disponibilidades")
    dia_semana = models.PositiveSmallIntegerField(choices=Dia.choices)
    hora_inicio = models.TimeField()
    hora_fin = models.TimeField()

    class Meta:
        verbose_name_plural = "disponibilidades"
        constraints = [models.CheckConstraint(condition=Q(hora_fin__gt=F("hora_inicio")), name="disponibilidad_horas_validas")]


# ---------------------------------------------------------------- citas y pagos
class Cita(models.Model):
    class Modalidad(models.TextChoices):
        PRESENCIAL = "presencial", "Presencial"
        VIRTUAL = "virtual", "Virtual"

    class Estado(models.TextChoices):
        PENDIENTE = "pendiente", "Pendiente de pago"
        CONFIRMADA = "confirmada", "Confirmada"
        CANCELADA = "cancelada", "Cancelada"
        REALIZADA = "realizada", "Realizada"

    paciente = models.ForeignKey(User, on_delete=models.CASCADE, related_name="citas")
    profesional = models.ForeignKey(Profesional, on_delete=models.PROTECT, related_name="citas")
    fecha_hora = models.DateTimeField()
    modalidad = models.CharField(max_length=10, choices=Modalidad.choices)
    estado = models.CharField(max_length=10, choices=Estado.choices, default=Estado.PENDIENTE)

    class Meta:
        ordering = ["fecha_hora"]
        constraints = [
            models.UniqueConstraint(
                fields=["profesional", "fecha_hora"],
                condition=~Q(estado="cancelada"),
                name="cita_unica_por_profesional_y_hora",
            ),
            models.CheckConstraint(condition=Q(modalidad__in=["presencial", "virtual"]), name="cita_modalidad_valida"),
            models.CheckConstraint(
                condition=Q(estado__in=["pendiente", "confirmada", "cancelada", "realizada"]), name="cita_estado_valido"
            ),
        ]

    def __str__(self):
        return f"{self.paciente} con {self.profesional} - {self.fecha_hora:%d/%m/%Y %H:%M}"


class HistorialCita(models.Model):
    """Historial de reprogramaciones (RF-06)."""

    cita = models.ForeignKey(Cita, on_delete=models.CASCADE, related_name="historial")
    fecha_anterior = models.DateTimeField()
    fecha_nueva = models.DateTimeField()
    motivo = models.CharField(max_length=200, blank=True)
    fecha_cambio = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name_plural = "historial de citas"
        ordering = ["-fecha_cambio"]


class Pago(models.Model):
    """Cada intento de pago es una fila: relación Cita 1:N Pago (flujo alterno de CU-04, RF-07)."""

    class Estado(models.TextChoices):
        PENDIENTE = "pendiente", "Pendiente"
        APROBADO = "aprobado", "Aprobado"
        FALLIDO = "fallido", "Fallido"

    cita = models.ForeignKey(Cita, on_delete=models.CASCADE, related_name="pagos")
    monto = models.DecimalField(max_digits=10, decimal_places=2)
    metodo = models.CharField(max_length=30)
    estado = models.CharField(max_length=10, choices=Estado.choices, default=Estado.PENDIENTE)
    referencia_transaccion = models.CharField(max_length=60, blank=True)
    comprobante = models.CharField(max_length=40, blank=True)
    fecha_pago = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-fecha_pago"]
        constraints = [
            models.CheckConstraint(condition=Q(monto__gte=0), name="pago_monto_no_negativo"),
            models.CheckConstraint(condition=Q(estado__in=["pendiente", "aprobado", "fallido"]), name="pago_estado_valido"),
        ]

    def __str__(self):
        return f"Pago {self.comprobante or self.pk} - {self.estado}"


class Calificacion(models.Model):
    """Calificación del paciente al profesional (CU-08). El promedio se calcula, no se guarda."""

    cita = models.OneToOneField(Cita, on_delete=models.CASCADE, related_name="calificacion")
    paciente = models.ForeignKey(User, on_delete=models.CASCADE, related_name="calificaciones_dadas")
    profesional = models.ForeignKey(Profesional, on_delete=models.CASCADE, related_name="calificaciones")
    puntuacion = models.PositiveSmallIntegerField()
    comentario = models.TextField(blank=True)
    fecha = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name_plural = "calificaciones"
        constraints = [
            models.CheckConstraint(condition=Q(puntuacion__gte=1, puntuacion__lte=5), name="calificacion_entre_1_y_5")
        ]


# ---------------------------------------------------------------- diario
class RegistroAnimo(models.Model):
    usuario = models.ForeignKey(User, on_delete=models.CASCADE, related_name="registros_animo")
    fecha = models.DateField(auto_now_add=True)
    nivel = models.PositiveSmallIntegerField(help_text="1 (muy mal) a 5 (muy bien)")
    nota = TextoCifrado(blank=True)  # CIFRADA (RNF-01)

    class Meta:
        ordering = ["-fecha", "-id"]
        verbose_name_plural = "registros de ánimo"
        constraints = [models.CheckConstraint(condition=Q(nivel__gte=1, nivel__lte=5), name="animo_nivel_entre_1_y_5")]


# ---------------------------------------------------------------- grupos y moderación
class GrupoApoyo(models.Model):
    nombre = models.CharField(max_length=100)
    tema = models.CharField(max_length=50)
    descripcion = models.TextField(blank=True)
    # 0..1: puede moderarlo solo la IA (observación 10)
    moderador = models.ForeignKey(Profesional, null=True, blank=True, on_delete=models.SET_NULL, related_name="grupos")
    moderado_por_ia = models.BooleanField(default=True)
    miembros = models.ManyToManyField(User, through="MiembroGrupo", related_name="grupos_apoyo")

    class Meta:
        verbose_name = "grupo de apoyo"
        verbose_name_plural = "grupos de apoyo"

    def __str__(self):
        return self.nombre


class MiembroGrupo(models.Model):
    usuario = models.ForeignKey(User, on_delete=models.CASCADE)
    grupo = models.ForeignKey(GrupoApoyo, on_delete=models.CASCADE)
    fecha_union = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name_plural = "miembros de grupo"
        constraints = [models.UniqueConstraint(fields=["usuario", "grupo"], name="miembro_unico_por_grupo")]


class Mensaje(models.Model):
    """FK real al autor (ya no hay emisor polimórfico). Contenido cifrado (RNF-01)."""

    class EstadoModeracion(models.TextChoices):
        APROBADO = "aprobado", "Aprobado"
        EN_REVISION = "en_revision", "En revisión"
        BLOQUEADO = "bloqueado", "Bloqueado"

    grupo = models.ForeignKey(GrupoApoyo, on_delete=models.CASCADE, related_name="mensajes")
    autor = models.ForeignKey(User, on_delete=models.CASCADE, related_name="mensajes")
    contenido = TextoCifrado()  # CIFRADO
    fecha = models.DateTimeField(auto_now_add=True)
    estado_moderacion = models.CharField(max_length=12, choices=EstadoModeracion.choices, default=EstadoModeracion.APROBADO)

    class Meta:
        ordering = ["fecha"]
        constraints = [
            models.CheckConstraint(
                condition=Q(estado_moderacion__in=["aprobado", "en_revision", "bloqueado"]), name="mensaje_estado_valido"
            )
        ]


class AlertaRiesgo(models.Model):
    """Se genera cuando la moderación detecta riesgo en un mensaje (RF-09, CU-09)."""

    class Nivel(models.TextChoices):
        BAJO = "bajo", "Bajo"
        MEDIO = "medio", "Medio"
        ALTO = "alto", "Alto"

    class Estado(models.TextChoices):
        ABIERTA = "abierta", "Abierta"
        ATENDIDA = "atendida", "Atendida"

    usuario = models.ForeignKey(User, on_delete=models.CASCADE, related_name="alertas_riesgo")
    mensaje = models.ForeignKey(Mensaje, null=True, blank=True, on_delete=models.SET_NULL, related_name="alertas")
    nivel = models.CharField(max_length=5, choices=Nivel.choices, default=Nivel.MEDIO)
    estado = models.CharField(max_length=10, choices=Estado.choices, default=Estado.ABIERTA)
    fecha = models.DateTimeField(auto_now_add=True)
    atendida_por = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name="alertas_atendidas")

    class Meta:
        verbose_name = "alerta de riesgo"
        verbose_name_plural = "alertas de riesgo"
        ordering = ["-fecha"]


class LineaAyuda(models.Model):
    nombre = models.CharField(max_length=100)
    telefono = models.CharField(max_length=30)
    descripcion = models.CharField(max_length=200, blank=True)
    activa = models.BooleanField(default=True)

    class Meta:
        verbose_name = "línea de ayuda"
        verbose_name_plural = "líneas de ayuda"

    def __str__(self):
        return f"{self.nombre} ({self.telefono})"


class EventoCrisis(models.Model):
    """Registro de qué ayuda se mostró o activó en una situación de crisis (CU-09, CU-10)."""

    usuario = models.ForeignKey(User, on_delete=models.CASCADE, related_name="eventos_crisis")
    alerta = models.ForeignKey(AlertaRiesgo, null=True, blank=True, on_delete=models.SET_NULL, related_name="eventos")
    linea = models.ForeignKey(LineaAyuda, null=True, blank=True, on_delete=models.SET_NULL, related_name="eventos")
    accion = models.CharField(max_length=40)
    fecha = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "evento de crisis"
        verbose_name_plural = "eventos de crisis"
        ordering = ["-fecha"]


# ---------------------------------------------------------------- test y recomendación
class Test(models.Model):
    nombre = models.CharField(max_length=100)
    tema = models.CharField(max_length=50)
    descripcion = models.TextField(blank=True)

    def __str__(self):
        return self.nombre


class Pregunta(models.Model):
    test = models.ForeignKey(Test, on_delete=models.CASCADE, related_name="preguntas")
    texto = models.CharField(max_length=255)
    orden = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["orden", "id"]

    def __str__(self):
        return self.texto


class Respuesta(models.Model):
    usuario = models.ForeignKey(User, on_delete=models.CASCADE, related_name="respuestas_test")
    pregunta = models.ForeignKey(Pregunta, on_delete=models.CASCADE, related_name="respuestas")
    valor = models.PositiveSmallIntegerField(help_text="0 (nunca) a 3 (casi todos los días)")
    fecha = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.CheckConstraint(condition=Q(valor__gte=0, valor__lte=3), name="respuesta_valor_entre_0_y_3")]


class Recomendacion(models.Model):
    """Resultado del matching (RF-05): recomienda UN grupo O UN profesional por fila."""

    usuario = models.ForeignKey(User, on_delete=models.CASCADE, related_name="recomendaciones")
    test = models.ForeignKey(Test, on_delete=models.CASCADE, related_name="recomendaciones")
    grupo = models.ForeignKey(GrupoApoyo, null=True, blank=True, on_delete=models.SET_NULL, related_name="recomendaciones")
    profesional = models.ForeignKey(Profesional, null=True, blank=True, on_delete=models.SET_NULL, related_name="recomendaciones")
    puntaje = models.PositiveSmallIntegerField()
    fecha = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "recomendación"
        verbose_name_plural = "recomendaciones"
        ordering = ["-fecha", "-id"]
        constraints = [
            models.CheckConstraint(
                condition=(Q(grupo__isnull=False) & Q(profesional__isnull=True))
                | (Q(grupo__isnull=True) & Q(profesional__isnull=False)),
                name="recomendacion_grupo_o_profesional",
            )
        ]
