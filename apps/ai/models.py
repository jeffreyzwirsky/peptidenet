from django.db import models


class AgentRun(models.Model):
    """Cost/usage ledger for every AI call — mirrors the SMASH AR-Sales AgentRun
    ledger. Lets the control panel show what AI is doing and what it costs."""

    purpose = models.CharField(max_length=40)          # support_chat, draft_sms, describe…
    provider = models.CharField(max_length=20, default="stub")   # anthropic/openai/stub
    model = models.CharField(max_length=60, blank=True)
    input_tokens = models.PositiveIntegerField(default=0)
    output_tokens = models.PositiveIntegerField(default=0)
    cost_usd = models.DecimalField(max_digits=8, decimal_places=5, default=0)
    site = models.ForeignKey("stores.Site", null=True, blank=True, on_delete=models.SET_NULL)
    ok = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.purpose} · {self.provider} · ${self.cost_usd}"


class AiConversation(models.Model):
    site = models.ForeignKey("stores.Site", null=True, blank=True, on_delete=models.SET_NULL,
                             related_name="ai_conversations")
    session_key = models.CharField(max_length=60, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)


class AiMessage(models.Model):
    ROLE = [("user", "User"), ("assistant", "Assistant")]
    conversation = models.ForeignKey(AiConversation, on_delete=models.CASCADE, related_name="messages")
    role = models.CharField(max_length=10, choices=ROLE)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]
