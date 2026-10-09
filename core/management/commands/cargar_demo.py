from datetime import time

from django.core.management.base import BaseCommand
from django.utils import timezone

from core.models import Disponibilidad, GrupoApoyo, LineaAyuda, Pregunta, Profesional, Test, Usuario


class Command(BaseCommand):
    help = "Carga grupos, profesionales, test y líneas de ayuda de ejemplo"

    def handle(self, *args, **opciones):
        for nombre, tema in [("Ansiedad", "ansiedad"), ("Duelo", "duelo"), ("Estrés", "estrés")]:
            if not GrupoApoyo.objects.filter(nombre=nombre).exists():
                GrupoApoyo.objects.create(nombre=nombre, tema=tema, descripcion=f"Grupo de apoyo sobre {tema}.")

        demos = [
            ("psicologa1", "Laura", "Gómez", "Psicología clínica y ansiedad", "DEMO-001", 40000),
            ("psicologo2", "Carlos", "Pérez", "Terapia de duelo", "DEMO-002", 35000),
        ]
        for username, nombre, apellido, especialidad, cedula, tarifa in demos:
            usuario, creado = Usuario.objects.get_or_create(
                username=username,
                defaults={"email": f"{username}@demo.com", "first_name": nombre, "last_name": apellido, "rol": "profesional"},
            )
            if creado:
                usuario.set_password("Demo12345")
                usuario.save()
            perfil, _ = Profesional.objects.get_or_create(
                usuario=usuario,
                defaults={
                    "especialidad": especialidad, "cedula_profesional": cedula, "tarifa_sesion": tarifa,
                    "estado_verificacion": "aprobado", "fecha_verificacion": timezone.now(),
                },
            )
            if not perfil.disponibilidades.exists():
                for dia in range(5):  # lunes a viernes
                    Disponibilidad.objects.create(profesional=perfil, dia_semana=dia, hora_inicio=time(8), hora_fin=time(17))

        if not Test.objects.exists():
            test = Test.objects.create(
                nombre="Test de bienestar emocional",
                tema="ansiedad",
                descripcion="Test orientativo. NO es un diagnóstico ni reemplaza la valoración de un profesional.",
            )
            preguntas = [
                "En las últimas 2 semanas, ¿con qué frecuencia te has sentido nervioso/a o con mucha tensión?",
                "¿Con qué frecuencia te ha costado dejar de preocuparte?",
                "¿Con qué frecuencia has tenido dificultad para dormir o descansar bien?",
                "¿Con qué frecuencia has perdido el interés o las ganas de hacer cosas que antes disfrutabas?",
                "¿Con qué frecuencia te has sentido abrumado/a por tus responsabilidades?",
            ]
            for orden, texto in enumerate(preguntas, start=1):
                Pregunta.objects.create(test=test, texto=texto, orden=orden)

        if not LineaAyuda.objects.exists():
            # VERIFICAR estos datos antes de la entrega: pueden cambiar
            LineaAyuda.objects.create(nombre="Emergencias", telefono="123", descripcion="Peligro inmediato")
            LineaAyuda.objects.create(nombre="Línea 192, opción 4", telefono="192", descripcion="Salud mental (Ministerio de Salud)")

        self.stdout.write(self.style.SUCCESS("Datos de ejemplo cargados."))
