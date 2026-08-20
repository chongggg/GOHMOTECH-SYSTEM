"""
Register a Roboflow Hosted API model in the system.

Environment variables:
- ROBOFLOW_API_KEY
- ROBOFLOW_MODEL_ID (example: workspace/model/1)
- ROBOFLOW_HOSTED_URL (optional, default: https://detect.roboflow.com)
"""

import os
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from ml_models.models import MLModel

# Placeholder path since Roboflow Hosted API is remote
model_path = "roboflow://hosted"

# Deactivate all existing models first
MLModel.objects.all().update(is_active=False)

# Create or update the model entry
model, created = MLModel.objects.get_or_create(
    name="Roboflow Goat Detection (Hosted)",
    version="1.0",
    defaults={
        'description': 'Roboflow Hosted API goat detection model',
        'model_type': 'roboflow-hosted',
        'file_path': model_path,
        'is_active': True,
        'input_size': {'width': 640, 'height': 640},
        'metadata': {
            'roboflow': {
                'endpoint': os.getenv('ROBOFLOW_HOSTED_URL', 'https://detect.roboflow.com'),
                'api_key_env': 'ROBOFLOW_API_KEY',
                'model_env': 'ROBOFLOW_MODEL_ID',
                'overlap': 0.3,
                'confidence': 0.5
            },
            'classes': ['goat'],
            'num_classes': 1,
            'framework': 'roboflow-hosted'
        }
    }
)

if not created:
    model.file_path = model_path
    model.is_active = True
    model.model_type = 'roboflow-hosted'
    model.metadata = model.metadata or {}
    model.metadata.update({
        'roboflow': {
            'endpoint': os.getenv('ROBOFLOW_HOSTED_URL', 'https://detect.roboflow.com'),
            'api_key_env': 'ROBOFLOW_API_KEY',
            'model_env': 'ROBOFLOW_MODEL_ID',
            'overlap': 0.3,
            'confidence': 0.5
        }
    })
    model.save()
    print("✅ Roboflow hosted model updated and activated")
else:
    print("✅ Roboflow hosted model registered successfully")

print("\n📊 Model Details:")
print(f"   Name: {model.name}")
print(f"   Type: {model.model_type}")
print(f"   Version: {model.version}")
print(f"   Path: {model.file_path}")
print(f"   Active: {model.is_active}")
print("\n📌 Next Steps:")
print("   1. Set ROBOFLOW_API_KEY and ROBOFLOW_MODEL_ID")
print("   2. Test detection: python test_detection.py")
