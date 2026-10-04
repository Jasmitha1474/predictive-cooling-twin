import numpy as np

class FeatureEngineer:
    def __init__(self, window_size=10):
        self.window_size = window_size
        self.history = {}

    def update(self, node_id, state):
        if node_id not in self.history:
            self.history[node_id] = {'power': [], 'utilization': [], 'temperature': [], 'memory': [], 'clock': []}
        hist = self.history[node_id]
        hist['power'].append(state['gpu_power'])
        hist['utilization'].append(state['gpu_utilization'])
        hist['temperature'].append(state['gpu_temperature'])
        hist['memory'].append(state['gpu_memory'])
        hist['clock'].append(state['gpu_clock'])
        for k in hist.keys():
            if len(hist[k]) > self.window_size: hist[k].pop(0)

    def get_features(self, node_id, current_state):
        hist = self.history.get(node_id, {})
        if not hist or len(hist['power']) < 2: return None
        p, t, u, m, c = hist['power'], hist['temperature'], hist['utilization'], hist['memory'], hist['clock']
        features = [
            current_state['gpu_power'], current_state['gpu_temperature'], current_state['gpu_utilization'],
            current_state['gpu_memory'], current_state['gpu_clock'],
            np.mean(p), np.max(p), np.mean(u),
            t[-1] - t[-2], p[-1] - p[-2], m[-1] - m[-2], c[-1] - c[-2]
        ]
        return np.array(features).reshape(1, -1)
