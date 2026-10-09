from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.forms import AdminUserCreationForm, UserChangeForm
from django.utils import timezone

from .models import (
    AlertaRiesgo, Calificacion, Cita, Consentimiento, Disponibilidad, EventoCrisis, GrupoApoyo,
    HistorialCita, LineaAyuda, Mensaje, MiembroGrupo, Pago, Pregunta, Profesional, Recomendacion,
    RegistroAnimo, Respuesta, Test, Usuario,
)


class UsuarioCreacionForm(AdminUserCreationForm):
    class Meta(AdminUserCreationForm.Meta):
        model = Usuario
        fields = ("username", "email", "rol")


class UsuarioCambioForm(UserChangeForm):
    class Meta(UserChangeForm.Meta):
        model = Usuario


@admin.register(Usuario)
class UsuarioAdmin(UserAdmin):
    form = UsuarioCambioForm
    add_form = UsuarioCreacionForm
    list_display = ("username", "email", "rol", "is_staff")
    list_filter = ("rol", "is_staff")
    fieldsets = UserAdmin.fieldsets + (("MindConnect", {"fields": ("rol",)}),)
    add_fieldsets = UserAdmin.add_fieldsets + (("MindConnect", {"fields": ("email", "rol")}),)


class DisponibilidadInline(admin.TabularInline):
    model = Disponibilidad
    extra = 1


@admin.action(description="Aprobar verificación de los profesionales seleccionados")
def aprobar_profesionales(modeladmin, request, queryset):
    queryset.update(estado_verificacion="aprobado", fecha_verificacion=timezone.now(), admin_verificador=request.user)


@admin.action(description="Rechazar verificación de los profesionales seleccionados")
def rechazar_profesionales(modeladmin, request, queryset):
    queryset.update(estado_verificacion="rechazado", fecha_verificacion=timezone.now(), admin_verificador=request.user)


@admin.register(Profesional)
class ProfesionalAdmin(admin.ModelAdmin):
    list_display = ("usuario", "especialidad", "estado_verificacion", "fecha_verificacion", "admin_verificador")
    list_filter = ("estado_verificacion",)
    actions = [aprobar_profesionales, rechazar_profesionales]
    inlines = [DisponibilidadInline]


@admin.action(description="Marcar alertas como atendidas")
def atender_alertas(modeladmin, request, queryset):
    queryset.update(estado="atendida", atendida_por=request.user)


@admin.register(AlertaRiesgo)
class AlertaRiesgoAdmin(admin.ModelAdmin):
    list_display = ("usuario", "nivel", "estado", "fecha", "atendida_por")
    list_filter = ("estado", "nivel")
    actions = [atender_alertas]


class PreguntaInline(admin.TabularInline):
    model = Pregunta
    extra = 1


@admin.register(Test)
class TestAdmin(admin.ModelAdmin):
    inlines = [PreguntaInline]


admin.site.register([
    Consentimiento, Cita, HistorialCita, Pago, Calificacion, RegistroAnimo, GrupoApoyo,
    MiembroGrupo, Mensaje, LineaAyuda, EventoCrisis, Respuesta, Recomendacion,
])
