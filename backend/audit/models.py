import uuid
from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.db import models


class ActionType(models.TextChoices):
    LOGIN_SUCCESS = "LOGIN_SUCCESS", "Login Successful"
    LOGIN_FAILED = "LOGIN_FAILED", "Login Failed"
    LOGOUT = "LOGOUT", "Logout"
    CREATE = "CREATE", "Entity Created"
    UPDATE = "UPDATE", "Entity Updated"
    DELETE = "DELETE", "Entity Deleted"
    PREDICT_RUN = "PREDICT_RUN", "Inference Executed"
    CONFIG_CHANGE = "CONFIG_CHANGE", "Configuration Changed"


class AuditLog(models.Model):
    """
    Immutable audit log recording critical system and security events.
    Enforces immutability at the model layer to prevent modification or tampering.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="audit_logs",
    )
    username = models.CharField(max_length=150, blank=True, help_text="Stored username in case user is deleted")
    action = models.CharField(max_length=30, choices=ActionType.choices, db_index=True)
    resource_type = models.CharField(max_length=100, blank=True, db_index=True)
    resource_id = models.CharField(max_length=150, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    details = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-timestamp"]
        verbose_name = "Audit Log"
        verbose_name_plural = "Audit Logs"
        indexes = [
            models.Index(fields=["-timestamp", "action"]),
            models.Index(fields=["resource_type", "resource_id"]),
        ]

    def __str__(self):
        user_str = self.username or (self.user.username if self.user else "Anonymous")
        return f"[{self.timestamp.strftime('%Y-%m-%d %H:%M:%S')}] {user_str} - {self.action} ({self.resource_type})"

    def save(self, *args, **kwargs):
        # Enforce immutability: allow insert (pk is None or not in DB), reject update
        if not self._state.adding and AuditLog.objects.filter(pk=self.pk).exists():
            raise PermissionDenied("Audit logs are strictly immutable and cannot be updated.")
        if self.user and not self.username:
            self.username = self.user.username
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise PermissionDenied("Audit logs are strictly immutable and cannot be deleted.")
