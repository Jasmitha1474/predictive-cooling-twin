from config import Config

class ReactiveController:
    def __init__(self):
        self.threshold = Config.TEMP_THRESHOLD
        self.overshoot_factor = 0.05
        
    def calculate_cooling(self, nodes_state):
        max_temp = max([n['gpu_temperature'] for n in nodes_state]) if nodes_state else Config.T_AMBIENT
        if max_temp > self.threshold:
            return min(1.0, 0.5 + (max_temp - self.threshold) * self.overshoot_factor)
        return 0.3
