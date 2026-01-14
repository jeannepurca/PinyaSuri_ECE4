#!/usr/bin/env python3
# ai_processor.py

import logging
import numpy as np
from PIL import Image
import tflite_runtime.interpreter as tflite
import config

logger = logging.getLogger(__name__)

class AIProcessor:
    def __init__(self):
        """Initialize TFLite model for real-time inference"""
        try:
            self.interpreter = tflite.Interpreter(model_path=str(config.MODEL_PATH))
            self.interpreter.allocate_tensors()
            
            self.input_details = self.interpreter.get_input_details()
            self.output_details = self.interpreter.get_output_details()
            
            # Get input shape
            self.input_shape = self.input_details[0]['shape']
            self.input_height = self.input_shape[1]
            self.input_width = self.input_shape[2]
            
            logger.info(f"✓ AI Model loaded: {config.MODEL_PATH.name}")
            logger.info(f"  Input size: {self.input_width}x{self.input_height}")
            
        except Exception as e:
            logger.error(f"⚠ Failed to load AI model: {e}")
            raise
    
    def preprocess_image(self, image_path):
        """Load and preprocess image for model"""
        try:
            # Load image
            img = Image.open(image_path).convert('RGB')
            
            # Resize to model input size
            img = img.resize((self.input_width, self.input_height))
            
            # Convert to numpy array and normalize
            img_array = np.array(img, dtype=np.float32)
            img_array = img_array / 255.0  # Normalize to [0, 1]
            
            # Add batch dimension
            img_array = np.expand_dims(img_array, axis=0)
            
            return img_array
            
        except Exception as e:
            logger.error(f"⚠ Image preprocessing failed: {e}")
            raise
    
    def classify(self, image_path):
        """
        Run inference on image
        
        Returns:
            dict: {
                'class_id': int,
                'class_name': str,
                'confidence': float,
                'all_probabilities': dict
            }
        """
        try:
            # Preprocess
            input_data = self.preprocess_image(image_path)
            
            # Run inference
            self.interpreter.set_tensor(self.input_details[0]['index'], input_data)
            self.interpreter.invoke()
            
            # Get output
            output_data = self.interpreter.get_tensor(self.output_details[0]['index'])
            probabilities = output_data[0]
            
            # Get top prediction
            class_id = int(np.argmax(probabilities))
            confidence = float(probabilities[class_id])
            class_name = config.get_class_name(class_id)
            
            # Get all probabilities
            all_probs = {
                config.get_class_name(i): float(probabilities[i])
                for i in range(len(probabilities))
            }
            
            return {
                'class_id': class_id,
                'class_name': class_name,
                'confidence': confidence,
                'all_probabilities': all_probs
            }
            
        except Exception as e:
            logger.error(f"⚠ Classification failed: {e}")
            raise