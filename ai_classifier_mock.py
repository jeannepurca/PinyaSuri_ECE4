import numpy as np
from PIL import Image
import logging
import random

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("MockClassifier")

class MockTFLiteClassifier:
    """
    Mock classifier for testing without a real model
    """
    
    def __init__(self, model_path: str, input_size=(224, 224)):
        self.model_path = model_path
        self.input_size = input_size
        self.class_names = {
            0: "Healthy",
            1: "Mealybug Wilt Disease",
            2: "Root Rot Disease",
            3: "Crown Rot Disease",
            4: "Fruit Fasciation Disorder",
            5: "Multiple Crown Disorder"
        }
        logger.info(f"Using MOCK classifier")

    def preprocess(self, img_path):
        """
        Mock preprocessing that just checks if image exists
        """

        try:
            img = Image.open(img_path)
            logger.info(f"Image loaded: {img_path}, size: {img.size}")
            return np.zeros((1, *self.input_size, 3), dtype=np.float32)
        except Exception as e:
            logger.error(f"Failed to load image: {e}")
            return np.zeros((1, *self.input_size, 3), dtype=np.float32)

    def predict(self, img_path):
        """
        Generate mock predictions
        """
        
        try:
            # Generate random probabilities
            probs = np.random.random(6)
            probs = probs / probs.sum()  # Normalize to sum to 1
            
            pred_idx = int(np.argmax(probs))
            confidence = float(probs[pred_idx])
            
            # Sometimes simulate detection issues
            if random.random() < 0.1:  # 10% chance to simulate low confidence
                confidence = random.uniform(0.1, 0.3)
                pred_idx = 0  # Default to "Healthy" when uncertain
            
            logger.info(f"Mock prediction for {img_path}: class={self.class_names[pred_idx]}, confidence={confidence:.3f}")
            
            return {
                "index": pred_idx,
                "confidence": confidence,
                "raw": probs.tolist(),
                "is_mock": True  # Flag to indicate mock data
            }
        except Exception as e:
            logger.error(f"Mock prediction failed: {e}")
            # Return a safe default
            return {
                "index": 0,
                "confidence": 0.5,
                "raw": [1.0, 0, 0, 0, 0, 0],
                "is_mock": True
            }