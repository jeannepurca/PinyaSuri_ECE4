# classifier.py
import numpy as np
from PIL import Image
import tflite_runtime.interpreter as tflite
import logging

logger = logging.getLogger("Classifier")

class TFLiteClassifier:
    def __init__(self, model_path: str, input_size=(224,224)):
        self.model_path = model_path
        self.input_size = input_size
        self.interpreter = tflite.Interpreter(model_path=self.model_path)
        self.interpreter.allocate_tensors()
        # get input/output details
        self.input_details = self.interpreter.get_input_details()
        self.output_details = self.interpreter.get_output_details()
        logger.info(f"Loaded TFLite model: {model_path}")

    def preprocess(self, img_path):
        img = Image.open(img_path).convert("RGB").resize(self.input_size)
        arr = np.array(img).astype(np.float32)
        # Example normalization: [0,255] -> [0,1]. Adjust to how your model was trained.
        arr = arr / 255.0
        arr = np.expand_dims(arr, axis=0)
        return arr

    def predict(self, img_path):
        inp = self.preprocess(img_path)
        input_index = self.input_details[0]["index"]
        self.interpreter.set_tensor(input_index, inp)
        self.interpreter.invoke()
        output_index = self.output_details[0]["index"]
        out = self.interpreter.get_tensor(output_index)
        # out shape depends on model; for classification softmax, pick argmax
        probs = out[0]
        pred_idx = int(np.argmax(probs))
        confidence = float(np.max(probs))
        return {"index": pred_idx, "confidence": confidence, "raw": probs.tolist()}
