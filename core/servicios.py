"""Lógica de negocio compartida por la API y las pantallas web."""
import uuid

from django.db import transaction
from django.db.models import Avg, F, Q
from django.utils import timezone

from .models import (
    AlertaRiesgo, Cita, EventoCrisis, GrupoApoyo, LineaAyuda, Mensaje,
    Pago, Profesional, Recomendacion, Respuesta,
)

# Versión simple de la detección de riesgo (RF-09); luego puede reemplazarse por un modelo de IA
PALABRAS_RIESGO = ["suicid", "quitarme la vida", "no quiero vivir", "hacerme daño", "matarme"]


def es_admin(usuario):
    return usuario.is_authenticated and (usuario.is_staff or usuario.rol == "admin")


def horario_valido(profesional, fecha_hora):
    """True si la fecha cae dentro de la disponibilidad del profesional (o si aún no definió horario)."""
    bloques = profesional.disponibilidades.all()
    if not bloques.exists():
        return True
    local = timezone.localtime(fecha_hora)
    return bloques.filter(dia_semana=local.weekday(), hora_inicio__lte=local.time(), hora_fin__gt=local.time()).exists()


def horario_ocupado(profesional, fecha_hora, excluir=None):
    qs = Cita.objects.filter(profesional=profesional, fecha_hora=fecha_hora).exclude(estado="cancelada")
    if excluir is not None:
        qs = qs.exclude(pk=excluir.pk)
    return qs.exists()


@transaction.atomic
def pagar_cita(cita, metodo="Simulado", aprobado=True):
    """Registra UN intento de pago (Cita 1:N Pago). Pago SIMULADO: aquí iría la pasarela real."""
    codigo = uuid.uuid4().hex[:8].upper()
    pago = Pago.objects.create(
        cita=cita,
        monto=cita.profesional.tarifa_sesion,
        metodo=metodo,
        estado="aprobado" if aprobado else "fallido",
        referencia_transaccion=f"TX-{uuid.uuid4().hex[:10].upper()}",
        comprobante=f"MC-{codigo}" if aprobado else "",
    )
    if aprobado:
        cita.estado = "confirmada"
        cita.save()
    return pago


def mensajes_visibles(usuario):
    """Mensajes que puede ver el usuario: los aprobados de sus grupos y los suyos propios no bloqueados."""
    if es_admin(usuario):
        return Mensaje.objects.all()
    return (
        Mensaje.objects.filter(grupo__miembros=usuario)
        .filter(Q(estado_moderacion="aprobado") | (Q(autor=usuario) & ~Q(estado_moderacion="bloqueado")))
        .distinct()
    )


def crear_mensaje(grupo, autor, contenido):
    """Guarda el mensaje. Si detecta riesgo: lo pone en revisión, crea la alerta y registra el evento de crisis."""
    riesgo = any(p in contenido.lower() for p in PALABRAS_RIESGO)
    with transaction.atomic():
        mensaje = Mensaje.objects.create(
            grupo=grupo, autor=autor, contenido=contenido,
            estado_moderacion="en_revision" if riesgo else "aprobado",
        )
        if riesgo:
            alerta = AlertaRiesgo.objects.create(usuario=autor, mensaje=mensaje, nivel="medio")
            EventoCrisis.objects.create(
                usuario=autor, alerta=alerta,
                linea=LineaAyuda.objects.filter(activa=True).first(),
                accion="mostro_linea_ayuda",
            )
    return mensaje, riesgo


@transaction.atomic
def generar_recomendaciones(usuario, test, respuestas):
    """respuestas = [(pregunta, valor), ...]. Guarda las respuestas y genera recomendaciones (RF-04, RF-05).
    El test es ORIENTATIVO, no es un diagnóstico."""
    Respuesta.objects.bulk_create([Respuesta(usuario=usuario, pregunta=p, valor=v) for p, v in respuestas])
    puntaje = sum(v for _, v in respuestas)
    recomendaciones = []

    grupo = GrupoApoyo.objects.filter(tema__iexact=test.tema).first() or GrupoApoyo.objects.first()
    if grupo:
        recomendaciones.append(Recomendacion.objects.create(usuario=usuario, test=test, grupo=grupo, puntaje=puntaje))

    # Si el puntaje es de la mitad o más del máximo, también se sugiere un profesional
    if puntaje * 2 >= 3 * len(respuestas):
        aprobados = Profesional.objects.filter(estado_verificacion="aprobado")
        profesional = aprobados.filter(especialidad__icontains=test.tema).first()
        if not profesional:
            profesional = (
                aprobados.annotate(prom=Avg("calificaciones__puntuacion"))
                .order_by(F("prom").desc(nulls_last=True)).first()
            )
        if profesional:
            recomendaciones.append(
                Recomendacion.objects.create(usuario=usuario, test=test, profesional=profesional, puntaje=puntaje)
            )
    return recomendaciones
