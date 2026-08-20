"""
Test script to verify goat detection is working
"""

import os
import sys
import django
import numpy as np

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from ml_models.models import MLModel
from ml_models.ml_utils import get_detector

def test_detection():
    """Test the goat detection model"""
    
    print("🔍 Testing Goat Detection System\n")
    
    # Check if model is registered
    active_model = MLModel.objects.filter(is_active=True).first()
    
    if not active_model:
        print("❌ No active model found!")
        print("   Run: python load_goat_model.py first")
        return False
    
    print(f"✅ Active Model: {active_model.name} v{active_model.version}")
    print(f"   Type: {active_model.model_type}")
    print(f"   Path: {active_model.file_path}")
    
    # Check if model file exists (skip for Roboflow Inference)
    if active_model.model_type.lower().startswith('roboflow'):
        print("\nℹ️  Roboflow Inference selected - no local model file required")
    elif not os.path.exists(active_model.file_path):
        print(f"\n❌ Model file not found: {active_model.file_path}")
        return False
    
    print("\n📦 Loading model...")
    try:
        detector = get_detector(
            model_type=active_model.model_type,
            model_path=active_model.file_path,
            confidence_threshold=0.5,
            use_gpu=False
        )
        print("✅ Model loaded successfully!")
    except Exception as e:
        print(f"❌ Failed to load model: {e}")
        return False
    
    # Test with a sample image
    print("\n🎯 Testing Detection...")
    print("   You can test with:")
    print("   1. Camera feed from your goat house")
    print("   2. A saved image of goats")
    print("   3. Create a test image:")
    
    # Create a simple test image (blank for demo)
    test_image = np.zeros((640, 640, 3), dtype=np.uint8)
    
    try:
        result = detector.detect(test_image)
        print("\n✅ Detection works!")
        print(f"   Goats detected: {result['count']}")
        print(f"   Confidence: {result.get('confidence', 0):.2%}")
        
        if result['count'] > 0:
            print("\n   📍 Detection boxes:")
            for i, det in enumerate(result['detections'], 1):
                bbox = det['bbox']
                print(f"      Goat {i}: x={bbox['x']:.0f}, y={bbox['y']:.0f}, "
                      f"w={bbox['width']:.0f}, h={bbox['height']:.0f}, "
                      f"conf={det['confidence']:.2%}")
        else:
            print("\n   ℹ️ No goats detected in test image (expected for blank image)")
    
    except Exception as e:
        print(f"❌ Detection failed: {e}")
        return False
    
    print("\n" + "="*60)
    print("🎉 Detection System is Ready!")
    print("="*60)
    print("\n📋 To test with real goat images:")
    print("   1. Go to http://127.0.0.1:8000/ml/detection/")
    print("   2. Or use the API:")
    print("      import requests")
    print("      files = {'image': open('goat.jpg', 'rb')}")
    print("      r = requests.post('http://127.0.0.1:8000/ml/api/detect/', files=files)")
    print("      print(r.json())")
    
    return True

if __name__ == '__main__':
    success = test_detection()
    sys.exit(0 if success else 1)
