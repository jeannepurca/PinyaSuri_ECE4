import numpy as np
from PIL import Image
import tflite_runtime.interpreter as tflite
import logging

logger = logging.getLogger("Classifier")    # Create logger for Classifier  

class TFLiteClassifier:
    def __init__(self, model_path: str, input_size=(224,224)):              # Initialize TFLite model
        self.model_path = model_path                                        # Path to TFLite model
        self.input_size = input_size                                        # Expected input size for the model 
        self.interpreter = tflite.Interpreter(model_path=self.model_path)   # Load the model
        self.interpreter.allocate_tensors()                                 # Allocate tensors  
        self.input_details = self.interpreter.get_input_details()           # Get input details
        self.output_details = self.interpreter.get_output_details()         # Get output details
        logger.info(f"Loaded TFLite model: {model_path}")                   # Log the loaded model

    def preprocess(self, img_path):         # Preprocess image for model input
        img = Image.open(img_path).convert("RGB").resize(self.input_size)   # Load and resize image
        arr = np.array(img).astype(np.float32)                              # Convert to numpy array
        arr = arr / 255.0                                                   # Normalize to [0,1]
        arr = np.expand_dims(arr, axis=0)                                   # Add batch dimension
        return arr

    def predict(self, img_path):            # Run inference on the image and return prediction
        inp = self.preprocess(img_path)                                     # Preprocess the image
        input_index = self.input_details[0]["index"]                        # Get input tensor index
        self.interpreter.set_tensor(input_index, inp)                       # Set input tensor
        self.interpreter.invoke()                                           # Run inference
        output_index = self.output_details[0]["index"]                      # Get output tensor index
        out = self.interpreter.get_tensor(output_index)                     # Get output tensor      
        probs = out[0]                                                      # Extract probabilities
        pred_idx = int(np.argmax(probs))                                    # Predicted class index
        confidence = float(np.max(probs))                                   # Confidence of prediction
        return {"index": pred_idx, "confidence": confidence, "raw": probs.tolist()}     # Return prediction dict