#!/usr/bin/env python3
# classifier.py

import logging
import numpy as np
import cv2
import config

logger = logging.getLogger(__name__)

class PinyaSuriAI:    
    def __init__(self):
        try:
            import tflite_runtime.interpreter as tflite
            
            if not config.MODEL_PATH.exists():
                raise FileNotFoundError(f"Model not found at {config.MODEL_PATH}")
            
            # Load the model
            self.interpreter = tflite.Interpreter(model_path=str(config.MODEL_PATH))
            self.interpreter.allocate_tensors()
            
            # Get input/output details
            self.input_details = self.interpreter.get_input_details()
            self.output_details = self.interpreter.get_output_details()
            
            # Get expected input shape
            self.input_shape = self.input_details[0]['shape']
            self.input_height = self.input_shape[1]
            self.input_width = self.input_shape[2]
            
            logger.info(f"✓h Object Detection Model loaded: {config.MODEL_PATH.name}")
            logger.info(f"  Input shape: {self.input_shape}")
            logger.info(f"  Number of classes: {len(config.CLASS_NAMES)}")
            logger.info(f"  Detection threshold: {config.DETECTION_THRESHOLD}")
            
        except ImportError:
            logger.error("⚠ tflite_runtime not installed!")
            logger.error("  Install with: pip3 install tflite-runtime")
            raise
            
        except Exception as e:
            logger.error(f"⚠ Failed to load detection model: {e}")
            raise

    def preprocess_frame(self, frame):
        """Preprocess with center crop to maintain 1:1 aspect ratio"""
        # Convert to RGB
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        
        # Get dimensions
        h, w = rgb_frame.shape[:2]
        
        # CENTER CROP TO SQUARE
        if w > h:
            # Landscape (4000x3000) - crop left/right
            crop_size = h  # 3000
            start_x = (w - h) // 2  # (4000-3000)//2 = 500
            cropped = rgb_frame[:, start_x:start_x + crop_size]  # Keep center 3000x3000
        elif h > w:
            # Portrait - crop top/bottom (unlikely with your camera)
            crop_size = w
            start_y = (h - w) // 2
            cropped = rgb_frame[start_y:start_y + crop_size, :]
        else:
            # Already square
            cropped = rgb_frame
        
        # Now resize square to model input (no distortion!)
        resized = cv2.resize(cropped, (self.input_width, self.input_height))
        
        # Normalize
        normalized = resized.astype(np.float32) / 255.0
        input_data = np.expand_dims(normalized, axis=0)
        
        return input_data

    def detect(self, frame):
        """Detect multiple pineapples in a frame (YOLOv8 format)"""
        try:
            frame_height, frame_width = frame.shape[:2]
            
            # Preprocess
            input_data = self.preprocess_frame(frame)
            if input_data is None:
                return []
            
            # Run inference
            self.interpreter.set_tensor(self.input_details[0]['index'], input_data)
            self.interpreter.invoke()
            
            # YOLOv8 has 1 output tensor
            output_data = self.interpreter.get_tensor(self.output_details[0]['index'])
            
            logger.debug(f"YOLOv8 output shape: {output_data.shape}")
            
            # Transpose to [num_boxes, num_features]
            predictions = output_data[0].T  # Shape: [8400, 5] or [8400, 84]
            
            detections = []
            
            for pred in predictions:
                # YOLOv8 format: [x_center, y_center, width, height, class_scores...]
                x_center, y_center, width, height = pred[:4]
                
                # Get class confidence
                if len(pred) == 5:
                    # Single class model
                    confidence = float(pred[4])
                    class_idx = 0
                else:
                    # Multi-class model
                    class_scores = pred[4:]
                    class_idx = int(np.argmax(class_scores))
                    confidence = float(class_scores[class_idx])
                
                # Filter by confidence threshold
                if confidence < config.DETECTION_THRESHOLD:
                    continue
                
                class_name = config.get_class_name(class_idx)
                
                # Convert from center format to corner format
                xmin = (x_center - width / 2) / self.input_width
                ymin = (y_center - height / 2) / self.input_height
                xmax = (x_center + width / 2) / self.input_width
                ymax = (y_center + height / 2) / self.input_height
                
                # Clamp to [0, 1]
                xmin = max(0.0, min(1.0, xmin))
                ymin = max(0.0, min(1.0, ymin))
                xmax = max(0.0, min(1.0, xmax))
                ymax = max(0.0, min(1.0, ymax))
                
                # Convert to pixel coordinates
                x1_px = int(xmin * frame_width)
                y1_px = int(ymin * frame_height)
                x2_px = int(xmax * frame_width)
                y2_px = int(ymax * frame_height)
                
                detection = {
                    'class_index': class_idx,
                    'class_name': class_name,
                    'confidence': confidence,
                    'bbox': (xmin, ymin, xmax, ymax),  # normalized
                    'bbox_pixels': (x1_px, y1_px, x2_px, y2_px)  # pixels
                }
                
                detections.append(detection)
            
            logger.debug(f"Detected {len(detections)} pineapple(s)")
            
            return detections
            
        except Exception as e:
            logger.error(f"⚠ Detection failed: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return []
        
    def detect_with_nms(self, frame, iou_threshold=0.5):
        """Detect with Non-Maximum Suppression to remove overlapping boxes"""
        detections = self.detect(frame)
        
        if len(detections) <= 1:
            return detections
        
        # Apply NMS
        boxes = np.array([d['bbox'] for d in detections])
        scores = np.array([d['confidence'] for d in detections])
        
        # Convert to [x1, y1, x2, y2] format for NMS
        indices = self._nms(boxes, scores, iou_threshold)
        
        filtered_detections = [detections[i] for i in indices]
        
        logger.debug(f"NMS: {len(detections)} → {len(filtered_detections)} detections")
        
        return filtered_detections
    
    def _nms(self, boxes, scores, iou_threshold):
        """Simple Non-Maximum Suppression implementation"""

        # Sort by score
        sorted_indices = np.argsort(scores)[::-1]
        
        keep = []
        
        while len(sorted_indices) > 0:

            # Pick box with highest score
            current = sorted_indices[0]
            keep.append(current)
            
            if len(sorted_indices) == 1:
                break
            
            # Calculate IoU with remaining boxes
            current_box = boxes[current]
            remaining_boxes = boxes[sorted_indices[1:]]
            
            ious = self._calculate_iou(current_box, remaining_boxes)
            
            # Keep boxes with IoU below threshold
            sorted_indices = sorted_indices[1:][ious < iou_threshold]
        
        return keep
    
    def _calculate_iou(self, box, boxes):
        """Calculate IoU between one box and multiple boxes"""
        # box: [xmin, ymin, xmax, ymax]
        # boxes: [N, 4]
        
        x1 = np.maximum(box[0], boxes[:, 0])
        y1 = np.maximum(box[1], boxes[:, 1])
        x2 = np.minimum(box[2], boxes[:, 2])
        y2 = np.minimum(box[3], boxes[:, 3])
        
        intersection = np.maximum(0, x2 - x1) * np.maximum(0, y2 - y1)
        
        box_area = (box[2] - box[0]) * (box[3] - box[1])
        boxes_area = (boxes[:, 2] - boxes[:, 0]) * (boxes[:, 3] - boxes[:, 1])
        
        union = box_area + boxes_area - intersection
        
        iou = intersection / (union + 1e-6)
        
        return iou

    def draw_bounding_boxes(self, frame, detections):
        """Draw bounding boxes and labels on frame"""
        for det in detections:
            # Get bounding box in pixels
            x1, y1, x2, y2 = det['bbox_pixels']
            
            # Get class info
            class_idx = det['class_index']
            class_name = det['class_name']
            confidence = det['confidence']
            
            # Get color for this class
            color = config.get_class_color(class_idx)
            
            # Draw rectangle
            cv2.rectangle(frame, (x1, y1), (x2, y2), color, config.BBOX_THICKNESS)
            
            # Prepare label text
            label = f"{class_name}: {confidence:.2f}"
            
            # Get text size for background rectangle
            (text_width, text_height), baseline = cv2.getTextSize(
                label, 
                cv2.FONT_HERSHEY_SIMPLEX, 
                config.FONT_SCALE, 
                1
            )
            
            # Draw label background (filled rectangle)
            label_y = y1 - 10 if y1 > text_height + 10 else y2 + text_height + 10
            cv2.rectangle(
                frame,
                (x1, label_y - text_height - baseline),
                (x1 + text_width, label_y + baseline),
                color,
                -1  # Filled
            )
            
            # Draw label text
            cv2.putText(
                frame,
                label,
                (x1, label_y - baseline),
                cv2.FONT_HERSHEY_SIMPLEX,
                config.FONT_SCALE,
                (255, 255, 255),  # White text
                1,
                cv2.LINE_AA
            )
        
        return frame

    def get_detection_summary(self, detections):
        """Get summary statistics from detections"""
        if not detections:
            return {
                'total_count': 0,
                'class_counts': {},
                'avg_confidence': 0.0
            }
        
        class_counts = {}
        total_confidence = 0.0
        
        for det in detections:
            class_name = det['class_name']
            class_counts[class_name] = class_counts.get(class_name, 0) + 1
            total_confidence += det['confidence']
        
        return {
            'total_count': len(detections),
            'class_counts': class_counts,
            'avg_confidence': total_confidence / len(detections)
        }