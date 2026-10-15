from datetime import timedelta, time

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from core.models import (
    AlertaRiesgo,
    Calificacion,
    Cita,
    Consentimiento,
    Disponibilidad,
    EventoCrisis,
    GrupoApoyo,
    HistorialCita,
    LineaAyuda,
    Mensaje,
    MiembroGrupo,
    Pago,
    Pregunta,
    Profesional,
    Recomendacion,
    RegistroAnimo,
    Respuesta,
    Test,
    Usuario,
)


TARGET = 100


class Command(BaseCommand):
    help = "Agrega datos sintéticos hasta que cada tabla de core tenga al menos 100 registros."

    @transaction.atomic
    def handle(self, *args, **options):
        self._fill_patients()
        self._fill_professionals()
        self._fill_groups()
        self._fill_tests()
        self._fill_help_lines()
        self._fill_availability()
        self._fill_consents()
        self._fill_appointments()
        self._fill_appointment_history()
        self._fill_payments()
        self._fill_ratings()
        self._fill_mood_records()
        self._fill_memberships()
        self._fill_messages()
        self._fill_alerts()
        self._fill_crisis_events()
        self._fill_questions()
        self._fill_answers()
        self._fill_recommendations()

        counts = [(model, model.objects.count()) for model in self._models()]
        below_target = [(model, count) for model, count in counts if count < TARGET]
        if below_target:
            details = ", ".join(f"{model.__name__}: {count}" for model, count in below_target)
            raise RuntimeError(f"No se alcanzó el mínimo de registros: {details}")

        self.stdout.write(self.style.SUCCESS("Registros por tabla de core:"))
        for model, count in counts:
            self.stdout.write(f"{model.__name__}: {count}")
        self.stdout.write(self.style.SUCCESS("Carga completada; los datos existentes se conservaron."))

    @staticmethod
    def _models():
        return (
            Usuario, Consentimiento, Profesional, Disponibilidad, Cita, HistorialCita,
            Pago, Calificacion, RegistroAnimo, GrupoApoyo, MiembroGrupo, Mensaje,
            AlertaRiesgo, LineaAyuda, EventoCrisis, Test, Pregunta, Respuesta, Recomendacion,
        )

    @staticmethod
    def _create_user(username, role, number):
        user = Usuario.objects.create_user(
            username=username,
            email=f"{username}@demo.invalid",
            first_name="Usuario",
            last_name=f"Demo {number:03}",
            rol=role,
            password=None,
        )
        return user

    def _fill_patients(self):
        number = 1
        while Usuario.objects.filter(username__startswith="demo_paciente_").count() < TARGET:
            username = f"demo_paciente_{number:03}"
            if not Usuario.objects.filter(username=username).exists():
                self._create_user(username, Usuario.Rol.PACIENTE, number)
            number += 1

    def _fill_professionals(self):
        admin = Usuario.objects.filter(is_staff=True).first()
        number = 1
        while Profesional.objects.count() < TARGET:
            username = f"demo_profesional_{number:03}"
            if Usuario.objects.filter(username=username).exists():
                number += 1
                continue
            user = self._create_user(username, Usuario.Rol.PROFESIONAL, number)
            Profesional.objects.create(
                usuario=user,
                especialidad=f"Atención psicológica demo {number:03}",
                cedula_profesional=f"DEMO-REG-{number:06}",
                tarifa_sesion=40000,
                biografia="Perfil sintético para pruebas; no corresponde a un profesional real.",
                estado_verificacion=Profesional.EstadoVerificacion.APROBADO,
                fecha_verificacion=timezone.now(),
                admin_verificador=admin,
            )
            number += 1

    def _fill_groups(self):
        number = 1
        while GrupoApoyo.objects.count() < TARGET:
            nombre = f"Grupo demo {number:03}"
            GrupoApoyo.objects.get_or_create(
                nombre=nombre,
                defaults={
                    "tema": "bienestar",
                    "descripcion": "Grupo sintético de demostración; no es un servicio clínico.",
                },
            )
            number += 1

    def _fill_tests(self):
        number = 1
        while Test.objects.count() < TARGET:
            nombre = f"Test demo {number:03}"
            test, _ = Test.objects.get_or_create(
                nombre=nombre,
                defaults={
                    "tema": "bienestar",
                    "descripcion": "Contenido sintético de demostración; no es diagnóstico ni evaluación clínica.",
                },
            )
            if not test.preguntas.exists():
                Pregunta.objects.create(
                    test=test,
                    texto="Pregunta sintética de demostración: ¿con qué frecuencia te has sentido bajo estrés?",
                    orden=1,
                )
            number += 1

    def _fill_help_lines(self):
        number = 1
        while LineaAyuda.objects.count() < TARGET:
            LineaAyuda.objects.get_or_create(
                nombre=f"Línea demo no operativa {number:03}",
                defaults={
                    "telefono": f"000-DEMO-{number:06}",
                    "descripcion": "Dato sintético; no es una línea real de ayuda.",
                    "activa": False,
                },
            )
            number += 1

    def _fill_availability(self):
        professionals = list(Profesional.objects.order_by("usuario_id"))
        while Disponibilidad.objects.count() < TARGET:
            number = Disponibilidad.objects.count()
            Disponibilidad.objects.create(
                profesional=professionals[number % len(professionals)],
                dia_semana=number % 7,
                hora_inicio=time(8),
                hora_fin=time(17),
            )

    def _fill_consents(self):
        users = list(Usuario.objects.order_by("pk"))
        types = list(Consentimiento.Tipo.values)
        number = 0
        while Consentimiento.objects.count() < TARGET:
            usuario = users[number % len(users)]
            tipo = types[(number // len(users)) % len(types)]
            version = f"D{number:07}"
            Consentimiento.objects.get_or_create(
                usuario=usuario,
                tipo=tipo,
                version=version,
            )
            number += 1

    def _fill_appointments(self):
        patients = list(
            Usuario.objects.filter(username__startswith="demo_paciente_").order_by("pk")
        )
        professionals = list(Profesional.objects.order_by("usuario_id"))
        number = 0
        while Cita.objects.count() < TARGET:
            self._create_appointment(patients, professionals, number)
            number += 1

    @staticmethod
    def _create_appointment(patients, professionals, number):
        Cita.objects.create(
            paciente=patients[number % len(patients)],
            profesional=professionals[number % len(professionals)],
            fecha_hora=timezone.now() - timedelta(days=400 + number),
            modalidad=Cita.Modalidad.VIRTUAL,
            estado=Cita.Estado.REALIZADA,
        )

    def _fill_appointment_history(self):
        appointments = list(Cita.objects.order_by("pk"))
        while HistorialCita.objects.count() < TARGET:
            number = HistorialCita.objects.count()
            appointment = appointments[number % len(appointments)]
            HistorialCita.objects.create(
                cita=appointment,
                fecha_anterior=appointment.fecha_hora - timedelta(days=2),
                fecha_nueva=appointment.fecha_hora,
                motivo="Reprogramación sintética de demostración.",
            )

    def _fill_payments(self):
        appointments = list(Cita.objects.order_by("pk"))
        while Pago.objects.count() < TARGET:
            number = Pago.objects.count()
            appointment = appointments[number % len(appointments)]
            Pago.objects.create(
                cita=appointment,
                monto=appointment.profesional.tarifa_sesion,
                metodo="Demo",
                estado=Pago.Estado.APROBADO,
                referencia_transaccion=f"DEMO-TX-{number:08}",
                comprobante=f"DEMO-{number:08}",
            )

    def _fill_ratings(self):
        while Calificacion.objects.count() < TARGET:
            appointment = (
                Cita.objects.filter(estado=Cita.Estado.REALIZADA)
                .exclude(calificacion__isnull=False)
                .order_by("pk")
                .first()
            )
            if appointment is None:
                patients = list(
                    Usuario.objects.filter(username__startswith="demo_paciente_").order_by("pk")
                )
                professionals = list(Profesional.objects.order_by("usuario_id"))
                self._create_appointment(
                    patients,
                    professionals,
                    Cita.objects.count() + 10000,
                )
                continue
            Calificacion.objects.create(
                cita=appointment,
                paciente=appointment.paciente,
                profesional=appointment.profesional,
                puntuacion=5,
                comentario="Calificación sintética de demostración.",
            )

    def _fill_mood_records(self):
        users = list(Usuario.objects.filter(username__startswith="demo_paciente_").order_by("pk"))
        while RegistroAnimo.objects.count() < TARGET:
            number = RegistroAnimo.objects.count()
            RegistroAnimo.objects.create(
                usuario=users[number % len(users)],
                nivel=3,
                nota="Registro sintético de demostración; no es información clínica real.",
            )

    def _fill_memberships(self):
        patients = list(
            Usuario.objects.filter(username__startswith="demo_paciente_").order_by("pk")
        )
        groups = list(GrupoApoyo.objects.order_by("pk"))
        number = 0
        while MiembroGrupo.objects.count() < TARGET:
            user = patients[number % len(patients)]
            group = groups[(number // len(patients)) % len(groups)]
            MiembroGrupo.objects.get_or_create(usuario=user, grupo=group)
            number += 1

    def _fill_messages(self):
        memberships = list(MiembroGrupo.objects.select_related("usuario", "grupo").order_by("pk"))
        while Mensaje.objects.count() < TARGET:
            number = Mensaje.objects.count()
            membership = memberships[number % len(memberships)]
            Mensaje.objects.create(
                grupo=membership.grupo,
                autor=membership.usuario,
                contenido=f"Mensaje sintético de demostración número {number + 1}.",
                estado_moderacion=Mensaje.EstadoModeracion.APROBADO,
            )

    def _fill_alerts(self):
        admin = Usuario.objects.filter(is_staff=True).first()
        users = list(Usuario.objects.filter(username__startswith="demo_paciente_").order_by("pk"))
        while AlertaRiesgo.objects.count() < TARGET:
            number = AlertaRiesgo.objects.count()
            AlertaRiesgo.objects.create(
                usuario=users[number % len(users)],
                nivel=AlertaRiesgo.Nivel.BAJO,
                estado=AlertaRiesgo.Estado.ATENDIDA,
                atendida_por=admin,
            )

    def _fill_crisis_events(self):
        alerts = list(AlertaRiesgo.objects.order_by("pk"))
        users = list(Usuario.objects.filter(username__startswith="demo_paciente_").order_by("pk"))
        while EventoCrisis.objects.count() < TARGET:
            number = EventoCrisis.objects.count()
            EventoCrisis.objects.create(
                usuario=users[number % len(users)],
                alerta=alerts[number % len(alerts)],
                accion="demo_no_operativo",
            )

    def _fill_questions(self):
        tests = list(Test.objects.order_by("pk"))
        number = 0
        while Pregunta.objects.count() < TARGET:
            test = tests[number % len(tests)]
            Pregunta.objects.create(
                test=test,
                texto=f"Pregunta sintética de demostración número {number + 1}.",
                orden=test.preguntas.count() + 1,
            )
            number += 1

    def _fill_answers(self):
        users = list(Usuario.objects.filter(username__startswith="demo_paciente_").order_by("pk"))
        questions = list(Pregunta.objects.order_by("pk"))
        while Respuesta.objects.count() < TARGET:
            number = Respuesta.objects.count()
            Respuesta.objects.create(
                usuario=users[number % len(users)],
                pregunta=questions[number % len(questions)],
                valor=number % 4,
            )

    def _fill_recommendations(self):
        users = list(Usuario.objects.filter(username__startswith="demo_paciente_").order_by("pk"))
        tests = list(Test.objects.order_by("pk"))
        groups = list(GrupoApoyo.objects.order_by("pk"))
        professionals = list(Profesional.objects.order_by("usuario_id"))
        while Recomendacion.objects.count() < TARGET:
            number = Recomendacion.objects.count()
            recommendation = {
                "usuario": users[number % len(users)],
                "test": tests[number % len(tests)],
                "puntaje": number % 16,
            }
            if number % 2:
                recommendation["grupo"] = groups[number % len(groups)]
            else:
                recommendation["profesional"] = professionals[number % len(professionals)]
            Recomendacion.objects.create(**recommendation)
