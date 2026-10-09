"""core/views.py - APIs en formato JSON (Django REST Framework)."""
from datetime import timedelta

from django.db.models import Avg, Count, Q
from django.utils import timezone
from rest_framework import permissions, serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response

from .models import (
    AlertaRiesgo, Calificacion, Cita, Consentimiento, Disponibilidad, GrupoApoyo, HistorialCita,
    LineaAyuda, MiembroGrupo, Pago, Profesional, Recomendacion, RegistroAnimo, Test, Usuario,
)
from .serializers import (
    AlertaRiesgoSerializer, CalificacionSerializer, CitaSerializer, ConsentimientoSerializer,
    DisponibilidadSerializer, GrupoApoyoSerializer, LineaAyudaSerializer, MensajeSerializer,
    PagoSerializer, ProfesionalSerializer, RecomendacionSerializer, RegistroAnimoSerializer,
    RespuestaEntradaSerializer, TestSerializer, UsuarioSerializer,
)
from .servicios import (
    crear_mensaje, es_admin, generar_recomendaciones, horario_ocupado, horario_valido,
    mensajes_visibles, pagar_cita,
)


class UsuarioViewSet(viewsets.ModelViewSet):
    serializer_class = UsuarioSerializer

    def get_permissions(self):
        if self.action == "create":  # registro abierto (RF-01)
            return [permissions.AllowAny()]
        return [permissions.IsAuthenticated()]

    def get_queryset(self):
        u = self.request.user
        if not u.is_authenticated:
            return Usuario.objects.none()
        return Usuario.objects.all() if es_admin(u) else Usuario.objects.filter(pk=u.pk)

    @action(detail=False, methods=["get"])
    def me(self, request):
        """Datos del usuario autenticado (para el frontend)."""
        return Response(self.get_serializer(request.user).data)


class ConsentimientoViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = ConsentimientoSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Consentimiento.objects.filter(usuario=self.request.user)


class ProfesionalViewSet(viewsets.ModelViewSet):
    serializer_class = ProfesionalSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        u = self.request.user
        base = Profesional.objects.select_related("usuario").annotate(promedio=Avg("calificaciones__puntuacion"))
        if es_admin(u):
            return base
        if self.action in ("update", "partial_update", "destroy"):
            return base.filter(usuario=u)
        return base.filter(Q(estado_verificacion="aprobado") | Q(usuario=u))

    def perform_create(self, serializer):
        u = self.request.user
        if u.rol != Usuario.Rol.PROFESIONAL:
            raise PermissionDenied("Solo usuarios con rol profesional.")
        if Profesional.objects.filter(pk=u.pk).exists():
            raise ValidationError("Ya tienes un perfil profesional.")
        serializer.save(usuario=u)


class DisponibilidadViewSet(viewsets.ModelViewSet):
    serializer_class = DisponibilidadSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        u = self.request.user
        qs = Disponibilidad.objects.all()
        if self.action in ("update", "partial_update", "destroy") and not es_admin(u):
            qs = qs.filter(profesional__usuario=u)
        prof = self.request.query_params.get("profesional")  # /api/disponibilidad/?profesional=3
        return qs.filter(profesional_id=prof) if (prof and prof.isdigit()) else qs

    def perform_create(self, serializer):
        perfil = Profesional.objects.filter(pk=self.request.user.pk).first()
        if not perfil:
            raise PermissionDenied("Solo profesionales pueden definir su disponibilidad.")
        serializer.save(profesional=perfil)


class CitaViewSet(viewsets.ModelViewSet):
    serializer_class = CitaSerializer
    permission_classes = [permissions.IsAuthenticated]
    http_method_names = ["get", "post", "head", "options"]  # los cambios se hacen con las acciones de abajo

    def get_queryset(self):
        u = self.request.user
        if es_admin(u):
            return Cita.objects.all()
        return Cita.objects.filter(Q(paciente=u) | Q(profesional__usuario=u))

    def perform_create(self, serializer):
        serializer.save(paciente=self.request.user)

    @action(detail=True, methods=["post"])
    def cancelar(self, request, pk=None):
        cita = self.get_object()
        cita.estado = Cita.Estado.CANCELADA
        cita.save()
        return Response(self.get_serializer(cita).data)

    @action(detail=True, methods=["post"])
    def reprogramar(self, request, pk=None):
        """Body: {"fecha_hora": "2026-11-03T10:00:00-05:00", "motivo": "..."}"""
        cita = self.get_object()
        if cita.paciente != request.user:
            raise PermissionDenied("Solo el paciente puede reprogramar su cita.")
        if cita.estado not in (Cita.Estado.PENDIENTE, Cita.Estado.CONFIRMADA):
            raise ValidationError("Esta cita no se puede reprogramar.")
        nueva = serializers.DateTimeField().run_validation(request.data.get("fecha_hora"))
        if nueva <= timezone.now():
            raise ValidationError({"fecha_hora": "La fecha debe ser futura."})
        if not horario_valido(cita.profesional, nueva):
            raise ValidationError({"fecha_hora": "El profesional no atiende en ese horario."})
        if horario_ocupado(cita.profesional, nueva, excluir=cita):
            raise ValidationError({"fecha_hora": "Ese horario ya está ocupado."})
        HistorialCita.objects.create(
            cita=cita, fecha_anterior=cita.fecha_hora, fecha_nueva=nueva, motivo=request.data.get("motivo", "")
        )
        cita.fecha_hora = nueva
        cita.save()
        return Response(self.get_serializer(cita).data)


class PagoViewSet(viewsets.ModelViewSet):
    serializer_class = PagoSerializer
    permission_classes = [permissions.IsAuthenticated]
    http_method_names = ["get", "post", "head", "options"]

    def get_queryset(self):
        u = self.request.user
        return Pago.objects.all() if es_admin(u) else Pago.objects.filter(cita__paciente=u)

    def perform_create(self, serializer):
        cita = serializer.validated_data["cita"]
        if cita.paciente != self.request.user:
            raise PermissionDenied("Solo puedes pagar tus propias citas.")
        if cita.estado != Cita.Estado.PENDIENTE:
            raise ValidationError("La cita no está pendiente de pago.")
        # Para probar el flujo alterno de CU-04 (reintentar): enviar "simular_fallo": true
        fallo = str(self.request.data.get("simular_fallo", "")).lower() in ("1", "true", "si")
        serializer.instance = pagar_cita(cita, metodo=serializer.validated_data.get("metodo", "Simulado"), aprobado=not fallo)


class CalificacionViewSet(viewsets.ModelViewSet):
    serializer_class = CalificacionSerializer
    permission_classes = [permissions.IsAuthenticated]
    http_method_names = ["get", "post", "head", "options"]

    def get_queryset(self):
        u = self.request.user
        return Calificacion.objects.all() if es_admin(u) else Calificacion.objects.filter(paciente=u)

    def perform_create(self, serializer):
        cita = serializer.validated_data["cita"]
        serializer.save(paciente=self.request.user, profesional=cita.profesional)


class RegistroAnimoViewSet(viewsets.ModelViewSet):
    serializer_class = RegistroAnimoSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return RegistroAnimo.objects.filter(usuario=self.request.user)

    def perform_create(self, serializer):
        serializer.save(usuario=self.request.user)

    @action(detail=False, methods=["get"])
    def resumen(self, request):
        """Promedio de ánimo de los últimos 7 días (para el gráfico del frontend)."""
        desde = timezone.now().date() - timedelta(days=7)
        promedio = self.get_queryset().filter(fecha__gte=desde).aggregate(p=Avg("nivel"))["p"]
        return Response({
            "promedio_1_a_5": round(promedio, 2) if promedio else None,
            "porcentaje": round(promedio / 5 * 100) if promedio else 0,
        })


class GrupoApoyoViewSet(viewsets.ModelViewSet):
    serializer_class = GrupoApoyoSerializer

    def get_permissions(self):
        if self.action in ("list", "retrieve", "unirse", "salir"):
            return [permissions.IsAuthenticated()]
        return [permissions.IsAdminUser()]  # crear/editar grupos: solo administración

    def get_queryset(self):
        return GrupoApoyo.objects.annotate(total_miembros=Count("miembros"))

    @action(detail=True, methods=["post"])
    def unirse(self, request, pk=None):
        grupo = self.get_object()
        _, creado = MiembroGrupo.objects.get_or_create(usuario=request.user, grupo=grupo)
        return Response({"unido": True, "nuevo": creado})

    @action(detail=True, methods=["post"])
    def salir(self, request, pk=None):
        MiembroGrupo.objects.filter(usuario=request.user, grupo=self.get_object()).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class MensajeViewSet(viewsets.ModelViewSet):
    serializer_class = MensajeSerializer
    permission_classes = [permissions.IsAuthenticated]
    http_method_names = ["get", "post", "head", "options"]

    def get_queryset(self):
        qs = mensajes_visibles(self.request.user)
        grupo = self.request.query_params.get("grupo")  # /api/mensajes/?grupo=1
        return qs.filter(grupo_id=grupo) if (grupo and grupo.isdigit()) else qs

    def perform_create(self, serializer):
        grupo = serializer.validated_data["grupo"]
        if not grupo.miembros.filter(pk=self.request.user.pk).exists():
            raise PermissionDenied("Debes unirte al grupo para escribir.")
        mensaje, _ = crear_mensaje(grupo, self.request.user, serializer.validated_data["contenido"])
        serializer.instance = mensaje


class AlertaRiesgoViewSet(viewsets.ReadOnlyModelViewSet):
    """Solo administración: revisión de alertas de riesgo (CU-09)."""
    queryset = AlertaRiesgo.objects.all()
    serializer_class = AlertaRiesgoSerializer
    permission_classes = [permissions.IsAdminUser]

    @action(detail=True, methods=["post"])
    def atender(self, request, pk=None):
        alerta = self.get_object()
        alerta.estado = AlertaRiesgo.Estado.ATENDIDA
        alerta.atendida_por = request.user
        alerta.save()
        return Response(self.get_serializer(alerta).data)


class LineaAyudaViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = LineaAyuda.objects.filter(activa=True)
    serializer_class = LineaAyudaSerializer
    permission_classes = [permissions.AllowAny]


class TestViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Test.objects.prefetch_related("preguntas")
    serializer_class = TestSerializer
    permission_classes = [permissions.IsAuthenticated]

    @action(detail=True, methods=["post"])
    def responder(self, request, pk=None):
        """Body: {"respuestas": [{"pregunta": 1, "valor": 2}, ...]}"""
        test = self.get_object()
        datos = request.data.get("respuestas", []) if hasattr(request.data, "get") else request.data
        ser = RespuestaEntradaSerializer(data=datos, many=True)
        ser.is_valid(raise_exception=True)
        pares = [(d["pregunta"], d["valor"]) for d in ser.validated_data]
        if {p.pk for p, _ in pares} != set(test.preguntas.values_list("pk", flat=True)):
            raise ValidationError("Responde todas las preguntas de este test.")
        recomendaciones = generar_recomendaciones(request.user, test, pares)
        return Response(RecomendacionSerializer(recomendaciones, many=True).data, status=status.HTTP_201_CREATED)


class RecomendacionViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = RecomendacionSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Recomendacion.objects.filter(usuario=self.request.user)
