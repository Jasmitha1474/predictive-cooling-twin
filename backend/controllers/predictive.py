from config import Config

class PredictiveController:
    def __init__(self):
        self.threshold = Config.TEMP_THRESHOLD
        
    def calculate_cooling(self, nodes_state):
        if not nodes_state: return 0.3
        max_curr_temp = max([n['gpu_temperature'] for n in nodes_state])
        max_pred_temp = max_curr_temp
        
        for n in nodes_state:
            preds = n.get('predicted_temperatures', [])
            if preds: max_pred_temp = max(max_pred_temp, max(preds))
                
        if max_pred_temp > self.threshold:
            diff = max_pred_temp - self.threshold
            return 1.0 if diff > 5.0 else min(0.9, 0.4 + diff * 0.1)
        elif max_curr_temp > self.threshold - 5.0:
            return 0.5
        return 0.2
