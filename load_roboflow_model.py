"""
Register a Roboflow Inference (self-hosted) model in the system.

Requirements:
- Roboflow Inference server running locally (default: http://localhost:9001)
- Environment variables:
  - ROBOFLOW_API_KEY
  - ROBOFLOW_MODEL_ID (example: goat-rbcef-ouwnl/1)
  - ROBOFLOW_INFERENCE_URL (optional, default: http://localhost:9001)
"""

import os
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from ml_models.models import MLModel

# Placeholder path since Roboflow Inference is remote
model_path = "roboflow://local"

# Deactivate all existing models first
MLModel.objects.all().update(is_active=False)

# Create or update the model entry
model, created = MLModel.objects.get_or_create(
    name="Roboflow Goat Detection",
    version="1.0",
    defaults={
        'description': 'Roboflow Inference (self-hosted) goat detection model',
        'model_type': 'roboflow',
        'file_path': model_path,
        'is_active': True,
        'input_size': {'width': 640, 'height': 640},
        'metadata': {
            'roboflow': {
                'endpoint': os.getenv('ROBOFLOW_INFERENCE_URL', 'http://localhost:9001'),
                'api_key_env': 'ROBOFLOW_API_KEY',
                'model_env': 'ROBOFLOW_MODEL_ID',
                'overlap': 0.3,
                'confidence': 0.5
            },
            'classes': ['goat'],
            'num_classes': 1,
            'framework': 'roboflow-inference'
        }
    }
)

if not created:
    model.file_path = model_path
    model.is_active = True
    model.model_type = 'roboflow'
    model.metadata = model.metadata or {}
    model.metadata.update({
        'roboflow': {
            'endpoint': os.getenv('ROBOFLOW_INFERENCE_URL', 'http://localhost:9001'),
            'api_key_env': 'ROBOFLOW_API_KEY',
            'model_env': 'ROBOFLOW_MODEL_ID',
            'overlap': 0.3,
            'confidence': 0.5
        }
    })
    model.save()
    print("✅ Roboflow model updated and activated")
else:
    print("✅ Roboflow model registered successfully")

print("\n📊 Model Details:")
print(f"   Name: {model.name}")
print(f"   Type: {model.model_type}")
print(f"   Version: {model.version}")
print(f"   Path: {model.file_path}")
print(f"   Active: {model.is_active}")
print("\n📌 Next Steps:")
print("   1. Ensure Roboflow Inference is running locally")
print("   2. Set ROBOFLOW_API_KEY and ROBOFLOW_MODEL_ID")
print("   3. Test detection: python test_detection.py")
