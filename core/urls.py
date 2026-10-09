from django.conf import settings
from django.conf.urls.static import static
from django.urls import include, path
from django.views.generic import RedirectView
from rest_framework.authtoken.views import obtain_auth_token
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register("usuarios", views.UsuarioViewSet, basename="usuario")
router.register("consentimientos", views.ConsentimientoViewSet, basename="consentimiento")
router.register("profesionales", views.ProfesionalViewSet, basename="profesional")
router.register("disponibilidad", views.DisponibilidadViewSet, basename="disponibilidad")
router.register("citas", views.CitaViewSet, basename="cita")
router.register("pagos", views.PagoViewSet, basename="pago")
router.register("calificaciones", views.CalificacionViewSet, basename="calificacion")
router.register("animo", views.RegistroAnimoViewSet, basename="animo")
router.register("grupos", views.GrupoApoyoViewSet, basename="grupo")
router.register("mensajes", views.MensajeViewSet, basename="mensaje")
router.register("alertas", views.AlertaRiesgoViewSet, basename="alerta")
router.register("lineas-ayuda", views.LineaAyudaViewSet, basename="lineaayuda")
router.register("tests", views.TestViewSet, basename="test")
router.register("recomendaciones", views.RecomendacionViewSet, basename="recomendacion")

urlpatterns = [
    path("", RedirectView.as_view(url="/api/")),
    path("api/token/", obtain_auth_token, name="token"),  # login para el frontend: devuelve un token
    path("api/", include(router.urls)),
    path("api-auth/", include("rest_framework.urls")),  # login para probar la API en el navegador
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
