from django.urls import path

from . import webhooks

app_name = "comms"

# Twilio points its SMS/voice webhooks here (configure the numbers to hit these).
urlpatterns = [
    path("sms/", webhooks.inbound_sms, name="inbound_sms"),
    path("sms-status/", webhooks.sms_status, name="sms_status"),
    path("voice/", webhooks.voice, name="voice"),
    path("gather/", webhooks.gather, name="gather"),
    path("recording/", webhooks.recording, name="recording"),
    path("recording-done/", webhooks.recording_done, name="recording_done"),
    # Paste this one into the Twilio Console: number -> Voice -> "Call status
    # changes" (POST). Twilio cannot be told about it from TwiML for an
    # inbound leg, which is why every Call row sat at "ringing" until now.
    path("call-status/", webhooks.call_status, name="call_status"),
]
