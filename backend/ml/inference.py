import joblib
import time
import os

class MLPredictor:
    def __init__(self, model_path='models/thermal_model.joblib'):
        self.model = None
        if os.path.exists(model_path):
            try: self.model = joblib.load(model_path)
            except: pass

    def predict(self, features, current_temp, current_power):
        start = time.perf_counter()
        if self.model is None or features is None:
            preds_t = [current_temp + i * 0.1 for i in range(1, 6)]
            preds_p = [current_power + i * 1.0 for i in range(1, 6)]
            return preds_t, preds_p, (time.perf_counter() - start) * 1000
            
        try:
            pred = self.model.predict(features)[0]
            preds_t, preds_p = pred[:5].tolist(), pred[5:].tolist()
        except:
            preds_t = [current_temp + i * 0.1 for i in range(1, 6)]
            preds_p = [current_power + i * 1.0 for i in range(1, 6)]
            
        return preds_t, preds_p, (time.perf_counter() - start) * 1000
