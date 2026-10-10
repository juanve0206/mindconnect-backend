# MindConnect - Backend

Backend de **MindConnect** (apoyo psicológico preventivo con grupos moderados por IA y citas a bajo costo),
desarrollado con **Django** y **Django REST Framework**. Proyecto final de Ingeniería de Software I, Universidad de La Guajira.

## Requisitos

- Python 3.11.1
- Django 5.2.12 (compatible con Python 3.11)

## Estructura (`core/`)

| Archivo | Para qué sirve |
| --- | --- |
| `models.py` | Estructura de las 19 tablas de la base de datos |
| `serializers.py` | Seguridad y filtro entre las tablas y las vistas (validaciones, campos de solo lectura) |
| `views.py` | APIs en formato JSON |
| `urls.py` | Rutas que consulta el frontend |
| `servicios.py` | Lógica de negocio (pagos, moderación de riesgo, recomendaciones) |
| `campos.py` | Campo de texto cifrado para datos sensibles (RNF-01) |

## Instalación

### Descargar el proyecto

El repositorio es público. Se puede descargar el proyecto completo como [archivo ZIP](https://github.com/juanve0206/mindconnect-backend/archive/refs/heads/main.zip) o clonarlo con:

```bash
git clone https://github.com/juanve0206/mindconnect-backend.git
cd mindconnect-backend
```

### Ejecutarlo en Windows

En Windows, instala Python 3.11.1 y crea el entorno virtual con:

```bash
py -3.11 -m venv venv
venv\Scripts\activate          # Windows  (Mac/Linux: source venv/bin/activate)
pip install -r requirements.txt
python manage.py migrate
python manage.py createsuperuser
python manage.py cargar_demo   # grupos, profesionales, test y líneas de ayuda de ejemplo
python manage.py runserver
```

En macOS/Linux, usa `python3.11 -m venv venv` para crear el entorno virtual.

Servidor: http://127.0.0.1:8000/ (redirige a `/api/`). Panel de administración: `/admin/`.
La advertencia amarilla de Django sobre el servidor de desarrollo al ejecutar `runserver` es normal en pruebas locales; no es un error y no impide usar la aplicación. `runserver` está destinado al computador local, no a publicar el sitio en Internet.
Cuentas demo de profesionales: `psicologa1` y `psicologo2`, contraseña `Demo12345` (solo para pruebas).

## Autenticación

- **Frontend:** `POST /api/token/` con `{"username": "...", "password": "..."}` devuelve un token.
  Luego se envía en cada petición: `Authorization: Token <token>`.
- **Navegador:** `/api-auth/login/` para probar la API con sesión.
- **Registro:** `POST /api/usuarios/` (no requiere token) con `username`, `email`, `password`, `rol` y `acepta_terminos: true`.

## Endpoints principales

| Ruta | Descripción |
| --- | --- |
| `/api/usuarios/` y `/api/usuarios/me/` | Registro y perfil (RF-01, RF-03) |
| `/api/consentimientos/` | Consentimientos aceptados por el usuario |
| `/api/profesionales/` | Perfiles; solo se listan los verificados (RF-02). Incluye promedio de calificación |
| `/api/disponibilidad/?profesional=ID` | Calendario de disponibilidad (RF-06) |
| `/api/citas/` | Agendar; `/api/citas/{id}/cancelar/` y `/api/citas/{id}/reprogramar/` (RF-06) |
| `/api/pagos/` | Pagar una cita; permite reintentos (RF-07, CU-04) |
| `/api/calificaciones/` | Calificar a un profesional (CU-08) |
| `/api/animo/` y `/api/animo/resumen/` | Diario de ánimo (la nota se guarda cifrada) |
| `/api/grupos/` | Grupos de apoyo; `/api/grupos/{id}/unirse/` y `/salir/` (RF-08) |
| `/api/mensajes/?grupo=ID` | Chat del grupo, con moderación de riesgo (RF-09) |
| `/api/alertas/` | Alertas de riesgo (solo administración) (CU-09) |
| `/api/lineas-ayuda/` | Líneas de ayuda para crisis (CU-10) |
| `/api/tests/` y `/api/tests/{id}/responder/` | Test de bienestar orientativo (RF-04) |
| `/api/recomendaciones/` | Grupos y profesionales recomendados (RF-05) |

## Modelo de datos

Usuario, Consentimiento, Profesional (especialización 1:1 de Usuario), Disponibilidad, Cita, HistorialCita, Pago (Cita 1:N Pago),
Calificacion, RegistroAnimo, GrupoApoyo, MiembroGrupo, Mensaje, AlertaRiesgo, LineaAyuda, EventoCrisis, Test, Pregunta, Respuesta y Recomendacion.
Columnas cifradas: `RegistroAnimo.nota` y `Mensaje.contenido`.
