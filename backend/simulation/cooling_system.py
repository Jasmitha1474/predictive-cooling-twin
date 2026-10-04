from config import Config

class CoolingSystem:
    def __init__(self):
        self.flow_rate = 5.0
        self.valve_position = 50.0
        self.coolant_supply_temp = Config.T_COOLANT_SUPPLY
        self.target_flow_rate = 5.0
        self.target_valve_position = 50.0
        self.delay_factor = 0.1

    def step(self):
        self.flow_rate += (self.target_flow_rate - self.flow_rate) * self.delay_factor
        self.valve_position += (self.target_valve_position - self.valve_position) * self.delay_factor
        self.flow_rate = max(0.0, min(Config.MAX_FLOW_RATE, self.flow_rate))
        self.valve_position = max(0.0, min(100.0, self.valve_position))
        
    def set_cooling(self, demand_pct):
        self.target_flow_rate = demand_pct * Config.MAX_FLOW_RATE
        self.target_valve_position = demand_pct * 100.0
