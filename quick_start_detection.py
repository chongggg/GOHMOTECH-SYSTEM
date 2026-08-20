"""
Quick Start: Test Goat Detection
=================================

Follow these steps to test your trained detection model:
"""

print("\n" + "="*60)
print("🐐 GOAT DETECTION SYSTEM - QUICK START")
print("="*60)

print("\n📋 Step-by-Step Instructions:")
print("\n1️⃣  LOAD YOUR MODEL")
print("   Run: python load_goat_model.py")
print("   This registers your trained model (best.pt) in the system")

print("\n2️⃣  RESTART DJANGO SERVER")
print("   Press Ctrl+C to stop current server")
print("   Run: python manage.py runserver")

print("\n3️⃣  ACCESS TEST PAGE")
print("   Open browser: http://127.0.0.1:8000/ml/detection/test/")
print("   OR click 'Test Detection' in the sidebar")

print("\n4️⃣  UPLOAD & TEST")
print("   - Take a photo of goats at your farm")
print("   - Upload the image")
print("   - Click 'Detect Goats'")
print("   - View results!")

print("\n" + "="*60)
print("✅ Your detection model path:")
print("   C:\\Users\\johnc\\OneDrive\\Desktop\\capstone\\weights\\best.pt")
print("="*60)

print("\n💡 Tips:")
print("   • Use good lighting for better detection")
print("   • Make sure goats are clearly visible")
print("   • Model was trained on specific conditions")
print("   • Test with different angles/distances")

print("\n🔧 Troubleshooting:")
print("   • If 'No Model Loaded' appears, run load_goat_model.py")
print("   • If detection fails, check Django server logs")
print("   • Make sure ultralytics is installed: pip install ultralytics")

print("\n📊 What You'll Get:")
print("   ✓ Number of goats detected")
print("   ✓ Confidence scores")
print("   ✓ Bounding box positions")
print("   ✗ Individual goat IDs (needs Re-ID model)")

print("\n🚀 Ready to start!")
print("   Run: python load_goat_model.py\n")
