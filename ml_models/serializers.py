from rest_framework import serializers
from .models import MLModel, Detection


class MLModelSerializer(serializers.ModelSerializer):
    """Serializer for ML Model"""
    category_display = serializers.CharField(source='get_category_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    uploaded_by_name = serializers.SerializerMethodField()
    has_file = serializers.SerializerMethodField()

    class Meta:
        model = MLModel
        fields = [
            'id', 'name', 'description', 'category', 'category_display',
            'model_type', 'version', 'file_path', 'has_file', 'file_size',
            'is_active', 'status', 'status_display',
            'uploaded_by', 'uploaded_by_name', 'validation_notes',
            'accuracy', 'input_size', 'metadata',
            'created_at', 'updated_at',
        ]
        # These are set by the server (upload/validation flow), never by the
        # client — otherwise a user could spoof ownership or activation state.
        read_only_fields = [
            'created_at', 'updated_at', 'uploaded_by', 'file_size',
            'status', 'is_active', 'validation_notes',
        ]

    def get_uploaded_by_name(self, obj):
        return obj.uploaded_by.get_username() if obj.uploaded_by else None

    def get_has_file(self, obj):
        return bool(obj.model_file)


class DetectionSerializer(serializers.ModelSerializer):
    """Serializer for Goat Detection results"""
    camera_name = serializers.CharField(source='camera.name', read_only=True)
    model_name = serializers.CharField(source='model.name', read_only=True)

    class Meta:
        model = Detection
        fields = '__all__'
        read_only_fields = ['timestamp']
