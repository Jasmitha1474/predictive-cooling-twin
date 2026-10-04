import numpy as np
from config import Config

class ThermalEngine:
    def __init__(self):
        self.dt = 1.0 / Config.SIMULATION_TICK_RATE
        self.c_th = Config.C_THERMAL

    def calculate_q_cool(self, flow_rate, t_gpu, t_coolant, valve_effectiveness):
        cooling_capacity = (flow_rate / Config.MAX_FLOW_RATE) * Config.MAX_COOLING_POWER * valve_effectiveness
        delta_t_factor = max(0.0, (t_gpu - t_coolant) / 50.0)
        return cooling_capacity * delta_t_factor

    def step(self, t_gpu, p_gpu, flow_rate, t_coolant, valve_effectiveness):
        def derivative(t):
            q_cool = self.calculate_q_cool(flow_rate, t, t_coolant, valve_effectiveness)
            return (p_gpu - q_cool) / self.c_th

        k1 = derivative(t_gpu)
        k2 = derivative(t_gpu + 0.5 * self.dt * k1)
        k3 = derivative(t_gpu + 0.5 * self.dt * k2)
        k4 = derivative(t_gpu + self.dt * k3)

        t_new = t_gpu + (self.dt / 6.0) * (k1 + 2*k2 + 2*k3 + k4)
        return max(Config.T_AMBIENT, t_new)
