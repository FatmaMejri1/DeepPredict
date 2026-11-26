from rest_framework import serializers

from .models import Alert


class AlertResourceSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    name = serializers.CharField()
    identifier = serializers.CharField()
    resource_type = serializers.CharField()
    status = serializers.CharField()


class AlertModelVersionSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    name = serializers.CharField()
    version = serializers.CharField()
    model_type = serializers.CharField()
    architecture = serializers.CharField()


class AlertPredictionSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    model_type = serializers.CharField(source="model_version.model_type")
    score = serializers.FloatField()
    risk_level = serializers.CharField(allow_null=True)
    is_anomalous = serializers.BooleanField(allow_null=True)
    window_start = serializers.DateTimeField()
    window_end = serializers.DateTimeField()
    created_at = serializers.DateTimeField()
    model = AlertModelVersionSerializer(source="model_version")


class AlertSerializer(serializers.ModelSerializer):
    resource = AlertResourceSerializer(read_only=True)
    latest_prediction = AlertPredictionSerializer(read_only=True, allow_null=True)
    acknowledged_by = serializers.SerializerMethodField()
    resolved_by = serializers.SerializerMethodField()

    class Meta:
        model = Alert
        fields = (
            "id", "alert_type", "severity", "status", "resource",
            "first_seen_at", "last_seen_at", "occurrence_count",
            "consecutive_clear_count", "latest_prediction", "acknowledged_by",
            "acknowledged_at", "resolved_by", "resolved_at", "resolution_source",
            "created_at", "updated_at",
        )

    def get_acknowledged_by(self, obj):
        return obj.acknowledged_by.username if obj.acknowledged_by_id else None

    def get_resolved_by(self, obj):
        return obj.resolved_by.username if obj.resolved_by_id else None
