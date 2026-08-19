"""Small, standards-compatible TOTP implementation for console MFA."""
import base64
import hashlib
import hmac
import secrets
import struct
import time
from urllib.parse import quote

from django.db import transaction
from django.utils import timezone

from .models import ConsoleMfaDevice

STEP_SECONDS = 30
DIGITS = 6


def new_secret():
    return base64.b32encode(secrets.token_bytes(20)).decode("ascii").rstrip("=")


def provisioning_uri(user, secret):
    issuer = "PeptideNet"
    label = quote(f"{issuer}:{user.get_username()}")
    return f"otpauth://totp/{label}?secret={secret}&issuer={quote(issuer)}&digits=6&period=30"


def _counter(at_time=None):
    return int((time.time() if at_time is None else at_time) // STEP_SECONDS)


def code_for(secret, counter=None):
    counter = _counter() if counter is None else counter
    padded = secret + "=" * ((8 - len(secret) % 8) % 8)
    key = base64.b32decode(padded, casefold=True)
    digest = hmac.new(key, struct.pack(">Q", counter), hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    number = (struct.unpack(">I", digest[offset:offset + 4])[0] & 0x7FFFFFFF) % 10**DIGITS
    return f"{number:0{DIGITS}d}"


def verify_and_consume(device, submitted):
    submitted = "".join(ch for ch in str(submitted or "") if ch.isdigit())
    if len(submitted) != DIGITS:
        return False
    current = _counter()
    with transaction.atomic():
        locked = ConsoleMfaDevice.objects.select_for_update().get(pk=device.pk)
        for counter in (current - 1, current, current + 1):
            if counter <= locked.last_counter:
                continue
            if hmac.compare_digest(code_for(locked.secret, counter), submitted):
                locked.last_counter = counter
                fields = ["last_counter"]
                if not locked.confirmed:
                    locked.confirmed = True
                    locked.confirmed_at = timezone.now()
                    fields += ["confirmed", "confirmed_at"]
                locked.save(update_fields=fields)
                return True
    return False
