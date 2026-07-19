from django.urls import path

from . import webhooks

app_name = "comms"

# Twilio points its SMS/voice webhooks here (configure the numbers to hit these).
urlpatterns = [
    path("sms/", webhooks.inbound_sms, name="inbound_sms"),
    path("sms-status/", webhooks.sms_status, name="sms_status"),
    path("voice/", webhooks.voice, name="voice"),
    path("recording/", webhooks.recording, name="recording"),
]
