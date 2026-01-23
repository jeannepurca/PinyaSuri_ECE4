#!/usr/bin/env python3
# debug_detection.py - Debug YOLOv8 output to see what's happening

import cv2
import numpy as np
import config
from classifier import PinyaSuriAI

def debug_detection(image_path):
    """Debug what the model is actually detecting"""
    
    # Load image
    frame = cv2.imread(image_path)
    if frame is None:
        print(f"❌ Failed to load image: {image_path}")
        return
    
    print(f"📸 Image shape: {frame.shape}")
    frame_height, frame_width = frame.shape[:2]
    
    # Initialize classifier
    classifier = PinyaSuriAI()
    
    # Run detection
    detections = classifier.detect(frame)
    
    print(f"\n🔍 Found {len(detections)} detection(s)\n")
    print("=" * 80)
    
    for i, det in enumerate(detections):
        print(f"\nDetection #{i+1}:")
        print(f"  Class: {det['class_name']} (index: {det['class_index']})")
        print(f"  Confidence: {det['confidence']:.4f}")
        print(f"  Normalized bbox: {det['bbox']}")
        print(f"    xmin={det['bbox'][0]:.4f}, ymin={det['bbox'][1]:.4f}")
        print(f"    xmax={det['bbox'][2]:.4f}, ymax={det['bbox'][3]:.4f}")
        
        # Calculate box dimensions
        bbox_width = det['bbox'][2] - det['bbox'][0]
        bbox_height = det['bbox'][3] - det['bbox'][1]
        print(f"  Box size (normalized): width={bbox_width:.4f}, height={bbox_height:.4f}")
        
        # Pixel coordinates
        x1, y1, x2, y2 = det['bbox_pixels']
        print(f"  Pixel bbox: ({x1}, {y1}) to ({x2}, {y2})")
        print(f"  Box size (pixels): {x2-x1}px × {y2-y1}px")
        
        # Check if box is suspiciously large (>80% of image)
        if bbox_width > 0.8 or bbox_height > 0.8:
            print(f"  ⚠️  WARNING: This box covers most of the image!")
            print(f"     Width coverage: {bbox_width*100:.1f}%")
            print(f"     Height coverage: {bbox_height*100:.1f}%")
    
    print("\n" + "=" * 80)
    
    # Draw bounding boxes
    output_frame = frame.copy()
    output_frame = classifier.draw_bounding_boxes(output_frame, detections)
    
    # Save debug image
    output_path = "debug_detection_output.jpg"
    cv2.imwrite(output_path, output_frame)
    print(f"\n✅ Debug image saved to: {output_path}")
    
    # Additional raw output inspection
    print("\n" + "=" * 80)
    print("🔬 RAW MODEL OUTPUT INSPECTION:")
    print("=" * 80)
    
    # Get raw predictions
    input_data = classifier.preprocess_frame(frame)
    classifier.interpreter.set_tensor(classifier.input_details[0]['index'], input_data)
    classifier.interpreter.invoke()
    output_data = classifier.interpreter.get_tensor(classifier.output_details[0]['index'])
    
    print(f"Raw output shape: {output_data.shape}")
    predictions = output_data[0].T
    print(f"Predictions shape after transpose: {predictions.shape}")
    
    # Show first few high-confidence predictions
    if len(predictions[0]) == 5:
        confidences = predictions[:, 4]
    else:
        confidences = predictions[:, 4:].max(axis=1)
    
    high_conf_indices = np.where(confidences > config.DETECTION_THRESHOLD)[0]
    print(f"\nPredictions above threshold ({config.DETECTION_THRESHOLD}): {len(high_conf_indices)}")
    
    if len(high_conf_indices) > 0:
        print("\nTop 5 predictions:")
        sorted_indices = high_conf_indices[np.argsort(confidences[high_conf_indices])[::-1]][:5]
        
        for idx in sorted_indices:
            pred = predictions[idx]
            x_center, y_center, width, height = pred[:4]
            conf = confidences[idx]
            
            print(f"\n  Prediction at index {idx}:")
            print(f"    Raw values: x_c={x_center:.4f}, y_c={y_center:.4f}, w={width:.4f}, h={height:.4f}")
            print(f"    Confidence: {conf:.4f}")
            
            # Check if values are already normalized or in pixels
            if x_center > 1.0 or y_center > 1.0 or width > 1.0 or height > 1.0:
                print(f"    ⚠️  Values > 1.0 detected - might need different normalization!")
                print(f"    If model input was {classifier.input_width}x{classifier.input_height}:")
                print(f"      x_c_norm = {x_center/classifier.input_width:.4f}")
                print(f"      y_c_norm = {y_center/classifier.input_height:.4f}")
                print(f"      w_norm = {width/classifier.input_width:.4f}")
                print(f"      h_norm = {height/classifier.input_height:.4f}")

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python debug_detection.py <image_path>")
        print("Example: python debug_detection.py images/20250123/pinyasuri_wp2_001.jpg")
        sys.exit(1)
    
    debug_detection(sys.argv[1])