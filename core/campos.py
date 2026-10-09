import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings
from django.db import models


def _fernet():
    clave = base64.urlsafe_b64encode(hashlib.sha256(settings.SECRET_KEY.encode()).digest())
    return Fernet(clave)


class TextoCifrado(models.TextField):
    """Campo de texto que se guarda CIFRADO (Fernet/AES) en la base de datos (RNF-01)."""

    def get_prep_value(self, value):
        value = super().get_prep_value(value)
        if value in (None, ""):
            return value
        return _fernet().encrypt(value.encode()).decode()

    def from_db_value(self, value, expression, connection):
        if value in (None, ""):
            return value
        try:
            return _fernet().decrypt(value.encode()).decode()
        except InvalidToken:
            return value
