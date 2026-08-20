"""
Script to load your trained goat detection model into the system
"""

import os
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from ml_models.models import MLModel

# Path to your best trained model
model_path = r"C:\Users\johnc\OneDrive\Desktop\capstone\weights\best.pt"

# Check if model file exists
if not os.path.exists(model_path):
    print(f"❌ Model file not found: {model_path}")
    exit(1)

# Deactivate only other GOAT models — never the person model, so goat and
# person detection can stay active together (see ml_models.views per-category
# activation). Using .all() here would silently kill an active person model.
MLModel.objects.filter(category='goat', is_active=True).update(is_active=False)

# Create or update the model entry
model, created = MLModel.objects.get_or_create(
    name="Goat Detection Model",
    version="1.0",
    defaults={
        'description': 'YOLOv8 trained model for goat detection',
        'category': 'goat',
        'model_type': 'yolov8',
        'file_path': model_path,
        'is_active': True,
        'input_size': {'width': 640, 'height': 640},
        'metadata': {
            'classes': ['goat'],
            'num_classes': 1,
            'framework': 'ultralytics',
            'notes': 'Detects goats only - no individual recognition yet'
        }
    }
)

if not created:
    # Update existing model
    model.file_path = model_path
    model.category = 'goat'
    model.is_active = True
    model.model_type = 'yolov8'
    model.save()
    print("✅ Model updated and activated")
else:
    print("✅ Model registered successfully")

print("\n📊 Model Details:")
print(f"   Name: {model.name}")
print(f"   Type: {model.model_type}")
print(f"   Version: {model.version}")
print(f"   Path: {model.file_path}")
print(f"   Active: {model.is_active}")
print("\n🎯 Your model is now ready for goat detection!")
print("\n📌 Next Steps:")
print("   1. Test detection: python test_detection.py")
print("   2. Access detection page: http://127.0.0.1:8000/ml/detection/")
print("   3. For individual goat recognition, we need to add Re-ID feature later")
