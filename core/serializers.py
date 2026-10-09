from django.utils import timezone
from rest_framework import serializers

from .models import (
    AlertaRiesgo, Calificacion, Cita, Consentimiento, Disponibilidad, GrupoApoyo, LineaAyuda,
    Mensaje, Pago, Pregunta, Profesional, Recomendacion, RegistroAnimo, Test, Usuario,
)
from .servicios import horario_ocupado, horario_valido

VERSION_TERMINOS = "1.0"


class UsuarioSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=False, min_length=8)
    acepta_terminos = serializers.BooleanField(write_only=True, required=False)

    class Meta:
        model = Usuario
        fields = ["id", "username", "email", "first_name", "last_name", "rol", "password", "acepta_terminos", "fecha_registro"]
        read_only_fields = ["id", "fecha_registro"]

    def validate_rol(self, value):
        if value == Usuario.Rol.ADMIN:
            raise serializers.ValidationError("Rol no permitido.")
        return value

    def validate(self, attrs):
        if self.instance is None and not attrs.get("acepta_terminos"):
            raise serializers.ValidationError({"acepta_terminos": "Debes aceptar los términos y la política de privacidad."})
        return attrs

    def create(self, validated_data):
        validated_data.pop("acepta_terminos", None)
        password = validated_data.pop("password", None)
        if not password:
            raise serializers.ValidationError({"password": "La contraseña es obligatoria."})
        usuario = Usuario(**validated_data)
        usuario.set_password(password)
        usuario.save()
        for tipo in (Consentimiento.Tipo.TERMINOS, Consentimiento.Tipo.PRIVACIDAD):
            Consentimiento.objects.create(usuario=usuario, tipo=tipo, version=VERSION_TERMINOS)
        return usuario

    def update(self, instance, validated_data):
        validated_data.pop("acepta_terminos", None)
        password = validated_data.pop("password", None)
        usuario = super().update(instance, validated_data)
        if password:
            usuario.set_password(password)
            usuario.save()
        return usuario


class ConsentimientoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Consentimiento
        fields = ["id", "tipo", "version", "fecha"]


class ProfesionalSerializer(serializers.ModelSerializer):
    nombre = serializers.CharField(source="usuario.get_full_name", read_only=True)
    calificacion_promedio = serializers.FloatField(source="promedio", read_only=True)

    class Meta:
        model = Profesional
        fields = ["usuario", "nombre", "especialidad", "cedula_profesional", "tarifa_sesion", "biografia",
                  "estado_verificacion", "fecha_verificacion", "documento_soporte", "calificacion_promedio"]
        # El profesional no puede verificarse solo: lo hace el administrador
        read_only_fields = ["usuario", "estado_verificacion", "fecha_verificacion"]


class DisponibilidadSerializer(serializers.ModelSerializer):
    class Meta:
        model = Disponibilidad
        fields = ["id", "profesional", "dia_semana", "hora_inicio", "hora_fin"]
        read_only_fields = ["profesional"]

    def validate(self, attrs):
        if attrs["hora_fin"] <= attrs["hora_inicio"]:
            raise serializers.ValidationError("La hora de fin debe ser posterior a la de inicio.")
        return attrs


class CitaSerializer(serializers.ModelSerializer):
    profesional_nombre = serializers.CharField(source="profesional.usuario.get_full_name", read_only=True)

    class Meta:
        model = Cita
        fields = ["id", "paciente", "profesional", "profesional_nombre", "fecha_hora", "modalidad", "estado"]
        read_only_fields = ["paciente", "estado"]

    def validate_fecha_hora(self, value):
        if value <= timezone.now():
            raise serializers.ValidationError("La fecha debe ser futura.")
        return value

    def validate_profesional(self, value):
        if not value.verificado:
            raise serializers.ValidationError("El profesional aún no está verificado.")
        return value

    def validate(self, attrs):
        profesional, fecha = attrs.get("profesional"), attrs.get("fecha_hora")
        if profesional and fecha:
            if not horario_valido(profesional, fecha):
                raise serializers.ValidationError({"fecha_hora": "El profesional no atiende en ese horario."})
            if horario_ocupado(profesional, fecha, self.instance):
                raise serializers.ValidationError({"fecha_hora": "Ese horario ya está ocupado."})
        return attrs


class PagoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Pago
        fields = ["id", "cita", "monto", "metodo", "estado", "referencia_transaccion", "comprobante", "fecha_pago"]
        read_only_fields = ["monto", "estado", "referencia_transaccion", "comprobante", "fecha_pago"]


class CalificacionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Calificacion
        fields = ["id", "cita", "paciente", "profesional", "puntuacion", "comentario", "fecha"]
        read_only_fields = ["paciente", "profesional", "fecha"]

    def validate_puntuacion(self, value):
        if not 1 <= value <= 5:
            raise serializers.ValidationError("La puntuación debe estar entre 1 y 5.")
        return value

    def validate_cita(self, cita):
        if cita.paciente != self.context["request"].user:
            raise serializers.ValidationError("Solo puedes calificar tus propias citas.")
        if cita.estado != Cita.Estado.REALIZADA:
            raise serializers.ValidationError("Solo se pueden calificar citas realizadas.")
        return cita


class RegistroAnimoSerializer(serializers.ModelSerializer):
    class Meta:
        model = RegistroAnimo
        fields = ["id", "usuario", "fecha", "nivel", "nota"]
        read_only_fields = ["usuario", "fecha"]

    def validate_nivel(self, value):
        if not 1 <= value <= 5:
            raise serializers.ValidationError("El nivel debe estar entre 1 y 5.")
        return value


class GrupoApoyoSerializer(serializers.ModelSerializer):
    total_miembros = serializers.IntegerField(read_only=True)

    class Meta:
        model = GrupoApoyo
        fields = ["id", "nombre", "tema", "descripcion", "moderador", "moderado_por_ia", "total_miembros"]


class MensajeSerializer(serializers.ModelSerializer):
    autor_nombre = serializers.CharField(source="autor.username", read_only=True)

    class Meta:
        model = Mensaje
        fields = ["id", "grupo", "autor", "autor_nombre", "contenido", "fecha", "estado_moderacion"]
        read_only_fields = ["autor", "fecha", "estado_moderacion"]


class AlertaRiesgoSerializer(serializers.ModelSerializer):
    class Meta:
        model = AlertaRiesgo
        fields = ["id", "usuario", "mensaje", "nivel", "estado", "fecha", "atendida_por"]


class LineaAyudaSerializer(serializers.ModelSerializer):
    class Meta:
        model = LineaAyuda
        fields = ["id", "nombre", "telefono", "descripcion"]


class PreguntaSerializer(serializers.ModelSerializer):
    class Meta:
        model = Pregunta
        fields = ["id", "texto", "orden"]


class TestSerializer(serializers.ModelSerializer):
    preguntas = PreguntaSerializer(many=True, read_only=True)

    class Meta:
        model = Test
        fields = ["id", "nombre", "tema", "descripcion", "preguntas"]


class RespuestaEntradaSerializer(serializers.Serializer):
    pregunta = serializers.PrimaryKeyRelatedField(queryset=Pregunta.objects.all())
    valor = serializers.IntegerField(min_value=0, max_value=3)


class RecomendacionSerializer(serializers.ModelSerializer):
    grupo_nombre = serializers.CharField(source="grupo.nombre", read_only=True)
    profesional_nombre = serializers.CharField(source="profesional.usuario.get_full_name", read_only=True)

    class Meta:
        model = Recomendacion
        fields = ["id", "test", "grupo", "grupo_nombre", "profesional", "profesional_nombre", "puntaje", "fecha"]
