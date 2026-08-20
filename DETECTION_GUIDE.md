# Goat Detection & Recognition System Guide

## Current Status
✅ **Detection**: You have a trained YOLOv8 model that can detect goats  
❌ **Recognition**: Individual goat identification not yet implemented  

## Quick Start - Load Your Model

### Step 1: Register Your Trained Model
```bash
python load_goat_model.py
```

This will:
- Register your `best.pt` model in the database
- Set it as the active model
- Configure it for detection

### Step 2: Test Detection
```bash
python test_detection.py
```

This verifies:
- Model loads correctly
- Detection works
- System is ready

### Step 3: Access Detection Page
Open in browser: http://127.0.0.1:8000/ml/detection/

## How It Works Now

### Detection Only (Current)
Your model can:
- ✅ Detect goats in images/video
- ✅ Count number of goats
- ✅ Draw bounding boxes
- ✅ Report confidence scores
- ❌ Cannot identify individual goats (G001, G002, etc.)

### What You Get:
```json
{
  "count": 3,
  "detections": [
    {"bbox": {"x": 100, "y": 150, "width": 200, "height": 300}, "confidence": 0.89, "label": "goat"},
    {"bbox": {"x": 350, "y": 180, "width": 180, "height": 280}, "confidence": 0.92, "label": "goat"},
    {"bbox": {"x": 600, "y": 200, "width": 190, "height": 290}, "confidence": 0.87, "label": "goat"}
  ]
}
```

## Adding Individual Goat Recognition (Re-ID)

To identify individual goats (G001, G002, etc.), you need to add a Re-Identification system:

### Option 1: Deep Re-ID Model (Recommended)
Train a separate model that learns unique features of each goat:

1. **Collect Data**:
   - Take multiple photos of each goat from different angles
   - Label them by goat ID (G001, G002, etc.)
   - Need ~10-50 images per goat

2. **Train Re-ID Model**:
   - Use a Siamese Network or Triplet Loss model
   - Or fine-tune ResNet/EfficientNet for goat embeddings
   - Output: 128 or 256-dimensional feature vector per goat

3. **Integration**:
   Your system already has `GoatReIdentificationService` ready:
   ```python
   # Extract features
   feature_extractor.extract_features(goat_image)
   
   # Match to known goat
   reid_service.find_matching_goat(embedding)
   
   # Auto-register new goat
   reid_service.auto_register_goat(image, embedding)
   ```

### Option 2: Simple Visual Markers (Quick Solution)
- Use colored ear tags or collars
- Train YOLO to detect tag colors
- Map colors to goat IDs
- Fast to implement but requires physical tags

### Option 3: Facial Recognition Approach
- Crop goat faces from detections
- Use face recognition library (face_recognition, DeepFace)
- Compare to database of known goat faces

## Testing Detection with Real Goats

### Method 1: Via Web Interface
1. Go to: http://127.0.0.1:8000/ml/detection/
2. Upload a goat image
3. View detection results

### Method 2: Via API
```python
import requests

# Take photo at farm
url = 'http://127.0.0.1:8000/ml/api/detect/'
files = {'image': open('goat_photo.jpg', 'rb')}
response = requests.post(url, files=files)

result = response.json()
print(f"Goats detected: {result['count']}")
for i, det in enumerate(result['detections'], 1):
    print(f"  Goat {i}: confidence {det['confidence']:.2%}")
```

### Method 3: Live Camera Feed
Connect to your IP camera:
```python
import cv2
import requests

# Connect to camera
cap = cv2.VideoCapture('rtsp://camera_ip/stream')

while True:
    ret, frame = cap.read()
    if not ret:
        break
    
    # Save frame
    cv2.imwrite('temp_frame.jpg', frame)
    
    # Detect goats
    with open('temp_frame.jpg', 'rb') as f:
        response = requests.post(
            'http://127.0.0.1:8000/ml/api/detect/',
            files={'image': f}
        )
    
    result = response.json()
    print(f"Frame: {result['count']} goats detected")
    
    # Display (optional)
    cv2.imshow('Detection', frame)
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
```

## Database Structure

### Current Tables:
- `MLModel`: Stores your detection model info
- `Detection`: Stores detection history
- `Goat`: Stores individual goat records (from iot app)
- `GoatDetectionHistory`: Links detections to specific goats

### For Re-ID, you'll populate:
- `Goat.feature_embedding`: 128/256-d vector of goat features
- `Goat.primary_image`: Reference image of the goat

## Next Steps

### Immediate (Detection Only):
1. ✅ Load your trained model
2. ✅ Test detection with farm photos
3. ✅ Verify goat counting works
4. ✅ Set up automated detection schedule

### Future (Add Recognition):
1. Decide on Re-ID approach
2. Collect labeled goat images
3. Train Re-ID model
4. Integrate with existing system
5. Enable auto-registration of new goats

## Files Created for You:
- `load_goat_model.py` - Register your model
- `test_detection.py` - Test detection system
- This guide: `DETECTION_GUIDE.md`

## Troubleshooting

### Model won't load:
- Check file path: `weights/best.pt`
- Verify ultralytics installed: `pip install ultralytics`
- Check model format (.pt file from YOLOv8)

### Low detection accuracy:
- Your model was trained on specific conditions
- Test with similar lighting/angles as training data
- May need more training data

### Want individual recognition:
- Current model only detects "goat" class
- Need separate Re-ID model for individual IDs
- Follow "Option 1" above to implement

## Questions?
- Detection issues: Check `ml_models/ml_utils.py`
- Re-ID questions: Check `ml_models/reid_service.py`
- Database: Check `ml_models/models.py` and `iot/goat_models.py`
