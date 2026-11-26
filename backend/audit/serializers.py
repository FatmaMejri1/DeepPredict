from rest_framework import serializers

from .models import AuditLog


class AuditLogSerializer(serializers.ModelSerializer):
    username = serializers.SerializerMethodField()

    class Meta:
        model = AuditLog
        fields = (
            "id",
            "timestamp",
            "username",
            "action",
            "resource_type",
            "resource_id",
        )
        read_only_fields = fields

    def get_username(self, obj):
        return obj.username or (obj.user.username if obj.user_id and obj.user else "Unknown")
