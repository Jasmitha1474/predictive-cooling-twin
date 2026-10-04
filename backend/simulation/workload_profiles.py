import time
import math
import random
from config import Config

class WorkloadProfile:
    def __init__(self, profile_type):
        self.profile_type = profile_type
        self.types = ['NORMAL', 'MODERATE', 'HIGH_GPU', 'CNN_TRAINING', 'TRANSFORMER_INFERENCE', 'CUDA_MATMUL', 'BURST', 'CUSTOM']

    def get_telemetry(self, t):
        base_util, base_power, base_mem, base_clock = 0.0, 0.0, 0.0, 300
        
        if self.profile_type == 'NORMAL':
            base_util = 40.0 + 5.0 * math.sin(t / 10.0) + random.uniform(-2, 2)
            base_power = 200.0 + 20.0 * math.sin(t / 10.0)
            base_mem = 30.0 + random.uniform(-1, 1)
            base_clock = 1200 + int(random.uniform(-50, 50))
        elif self.profile_type == 'MODERATE':
            base_util = 60.0 + 10.0 * math.sin(t / 15.0) + random.uniform(-3, 3)
            base_power = 400.0 + 30.0 * math.sin(t / 15.0)
            base_mem = 50.0 + random.uniform(-2, 2)
            base_clock = 1500 + int(random.uniform(-50, 50))
        elif self.profile_type == 'HIGH_GPU':
            base_util = 95.0 + random.uniform(-2, 2)
            base_power = 850.0 + random.uniform(-20, 20)
            base_mem = 80.0 + random.uniform(-2, 2)
            base_clock = 1900 + int(random.uniform(-20, 20))
        elif self.profile_type == 'CNN_TRAINING':
            cycle = t % 60
            if cycle < 50:
                base_util, base_power = 98.0 + random.uniform(-1, 1), 900.0 + random.uniform(-10, 10)
            else:
                base_util, base_power = 70.0 + random.uniform(-5, 5), 600.0 + random.uniform(-20, 20)
            base_mem, base_clock = 95.0 + random.uniform(-1, 1), 1950
        elif self.profile_type == 'TRANSFORMER_INFERENCE':
            base_util = 50.0 + 40.0 * math.sin(t / 2.0)**2 + random.uniform(-5, 5)
            base_power = 300.0 + 500.0 * math.sin(t / 2.0)**2
            base_mem, base_clock = 60.0 + random.uniform(-5, 5), 1700 + int(random.uniform(-100, 100))
        elif self.profile_type == 'CUDA_MATMUL':
            base_util, base_power, base_mem, base_clock = 100.0, 950.0, 75.0, 1800
        elif self.profile_type == 'BURST':
            is_burst = (int(t) % 20) < 5
            base_util = 100.0 if is_burst else 10.0 + random.uniform(-2, 2)
            base_power = 950.0 if is_burst else 150.0 + random.uniform(-10, 10)
            base_mem = 40.0 if is_burst else 20.0
            base_clock = 1900 if is_burst else 800
        else:
            base_util = 50.0 + random.uniform(-5, 5)
            base_power = 350.0 + random.uniform(-10, 10)
            base_mem, base_clock = 40.0, 1400

        return {
            'utilization': max(0.0, min(100.0, base_util)),
            'power': max(50.0, min(Config.MAX_GPU_POWER, base_power)),
            'memory': max(0.0, min(100.0, base_mem)),
            'clock': base_clock
        }
