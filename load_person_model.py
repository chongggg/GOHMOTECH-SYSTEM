"""
Register (and activate) a person-detection model ALONGSIDE the goat model.

Unlike load_goat_model.py this does NOT deactivate every model — it deactivates
only other *person* models, so the active goat model keeps running and goat +
person detection run together on each frame (see
ml_models.views.detect_goats_api).

Uses stock YOLOv8n COCO weights: ``YOLO('yolov8n.pt')`` auto-downloads them on
first load and the COCO class set includes ``person``. Point ``model_path`` at
your own person-trained .pt instead if you have one — but note that a goat-only
model (e.g. weights/best.pt) has NO person class and will never detect people.
"""

import os
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from ml_models.models import MLModel

# Stock COCO weights (has a 'person' class). Ultralytics auto-downloads this on
# the first YOLO() load, so the file need not already exist on disk.
model_path = 'yolov8n.pt'

# Deactivate only other PERSON models — never the goat model.
MLModel.objects.filter(category='person', is_active=True).update(
    is_active=False, status='inactive'
)

# Create or update the person model entry
model, created = MLModel.objects.get_or_create(
    name="Person Detection (COCO)",
    version="1.0",
    defaults={
        'description': 'YOLOv8n COCO weights - detects the person class',
        'category': 'person',
        'model_type': 'yolov8',
        'file_path': model_path,
        'is_active': True,
        'status': 'active',
        'input_size': {'width': 640, 'height': 640},
        'metadata': {
            'classes': 'coco',
            'framework': 'ultralytics',
            'notes': 'Stock COCO model; person class used for security detection.'
        }
    }
)

if not created:
    # Update existing entry
    model.file_path = model_path
    model.category = 'person'
    model.model_type = 'yolov8'
    model.is_active = True
    model.status = 'active'
    model.save()
    print("✅ Person model updated and activated")
else:
    print("✅ Person model registered and activated")

print("\n📊 Model Details:")
print(f"   Name: {model.name}")
print(f"   Category: {model.category}")
print(f"   Type: {model.model_type}")
print(f"   Version: {model.version}")
print(f"   Path: {model.file_path}")
print(f"   Active: {model.is_active}")

# Confirm the goat model was left untouched (both should be active).
goat = MLModel.objects.filter(category='goat', is_active=True).first()
print(f"\n🐐 Active goat model:   {goat.name if goat else '(none registered)'}")
print(f"🧍 Active person model: {model.name}")
print("\n🎯 Both models now run on each frame.")
print("   Open the live feed:  http://127.0.0.1:8000/ml/detection/")
print("   Persons show up in:  http://127.0.0.1:8000/security/ (Person Detection tab)")
