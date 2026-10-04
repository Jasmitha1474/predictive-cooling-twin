import time
from config import Config
from .thermal_engine import ThermalEngine
from .workload_profiles import WorkloadProfile
from .cooling_system import CoolingSystem

class Node:
    def __init__(self, rack_id, node_id):
        self.rack_id = rack_id
        self.node_id = node_id
        self.workload = WorkloadProfile('NORMAL')
        self.thermal = ThermalEngine()
        self.temperature = Config.T_AMBIENT
        self.state = {}

    def step(self, t, cooling_sys):
        telemetry = self.workload.get_telemetry(t)
        p_gpu = telemetry['power']
        self.temperature = self.thermal.step(
            t_gpu=self.temperature, p_gpu=p_gpu, flow_rate=cooling_sys.flow_rate,
            t_coolant=cooling_sys.coolant_supply_temp, valve_effectiveness=cooling_sys.valve_position / 100.0
        )
        self.state = {
            'workload': self.workload.profile_type,
            'gpu_utilization': telemetry['utilization'],
            'gpu_power': p_gpu,
            'gpu_memory': telemetry['memory'],
            'gpu_clock': telemetry['clock'],
            'gpu_temperature': self.temperature
        }
        return self.state

class Rack:
    def __init__(self, rack_id):
        self.rack_id = rack_id
        self.nodes = [Node(rack_id, f'GPU-{rack_id[-2:]}-{str(i+1).zfill(2)}') for i in range(Config.NODES_PER_RACK)]
        self.cooling = CoolingSystem()
        self.cooling_demand = 0.5

    def step(self, t):
        self.cooling.set_cooling(self.cooling_demand)
        self.cooling.step()
        for node in self.nodes: node.step(t, self.cooling)

class DataCenter:
    def __init__(self):
        self.racks = [Rack(f'RACK-{str(i+1).zfill(2)}') for i in range(Config.NUM_RACKS)]
        self.elapsed_time = 0.0
        self.tick_count = 0
        
    def step(self):
        self.elapsed_time += 1.0 / Config.SIMULATION_TICK_RATE
        self.tick_count += 1
        for rack in self.racks: rack.step(self.elapsed_time)
