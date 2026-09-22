"""Machine Telemetry Digital Twin Simulation Engine.

Generates realistic time-series sensor telemetry for CNC Machines, Industrial 3D Printers,
Motors, Pumps, Fans, Conveyors, and Gearboxes.
Simulates physical parameter correlations (temperature, vibration, current, RPM, operating hours,
workload, tool wear) under 4 operational scenarios:
- 'normal'
- 'degrading'
- 'near_failure'
- 'sensor_anomaly'

Ground Truth Isolation Rule:
`health_index` and `scenario` are simulator ground-truth indicators ONLY.
They MUST NOT be used as input features for machine learning models predicting failure.
"""

from datetime import datetime, timedelta, timezone
import math
import random
from typing import Dict, Any, List, Optional, Set

from config.schema import (
    SensorData,
    ALLOWED_SCENARIOS,
    ALLOWED_MACHINE_TYPES,
    DEFAULT_VALIDATION_LIMITS,
)

# Extended Equipment Categories Mapping
SUPPORTED_SIMULATOR_EQUIPMENT: Set[str] = {
    "CNC",
    "3D_Printer",
    "ELECTRIC_MOTOR",
    "PUMP_COMPRESSOR",
    "HVAC_FAN",
    "CONVEYOR",
    "GEARBOX",
}

# Backend Type Mapping (maps extended categories to backend-supported MachineType schema)
BACKEND_MACHINE_TYPE_MAP: Dict[str, str] = {
    "CNC": "CNC",
    "3D_Printer": "3D_Printer",
    "ELECTRIC_MOTOR": "CNC",
    "PUMP_COMPRESSOR": "CNC",
    "HVAC_FAN": "3D_Printer",
    "CONVEYOR": "CNC",
    "GEARBOX": "CNC",
}


class TelemetrySimulator:
    """Digital twin telemetry simulator for individual virtual equipment instances."""

    def __init__(
        self,
        machine_id: str,
        machine_type: str = "CNC",
        initial_hours: float = 100.0,
        initial_health: float = 95.0,
        initial_tool_wear: float = 5.0,
        degradation_profile: str = "stable_normal",
        random_state: Optional[random.Random] = None,
    ):
        """Initialize simulator instance for a specific machine.
        
        Args:
            machine_id: Unique identifier (e.g. 'CNC-001', 'PRINTER-3D-01').
            machine_type: Category identifier ('CNC', '3D_Printer', 'ELECTRIC_MOTOR', etc.).
            initial_hours: Starting operating hours.
            initial_health: Starting health score (0.0 to 100.0).
            initial_tool_wear: Starting component/tool wear (0.0 to 100.0).
            degradation_profile: 'stable_normal', 'gradual_degrade', 'rapid_degrade_failure', or 'sensor_anomaly'.
            random_state: Isolated random instance.
        """
        if machine_type not in ALLOWED_MACHINE_TYPES and machine_type not in SUPPORTED_SIMULATOR_EQUIPMENT:
            raise ValueError(f"Invalid machine_type '{machine_type}'. Must be one of {sorted(list(ALLOWED_MACHINE_TYPES | SUPPORTED_SIMULATOR_EQUIPMENT))}")

        self.machine_id = machine_id
        self.machine_type = machine_type
        self.backend_type = BACKEND_MACHINE_TYPE_MAP.get(machine_type, "CNC") if machine_type in BACKEND_MACHINE_TYPE_MAP else machine_type
        self.hours = float(initial_hours)
        self.health_index = float(initial_health)
        self.tool_wear = float(initial_tool_wear)
        self.degradation_profile = degradation_profile
        self.rng = random_state or random.Random()
        self.step_count = 0

    def set_scenario(self, profile_name: str):
        """Update simulation scenario dynamically ('normal', 'degrading', 'near_failure', 'sensor_anomaly')."""
        valid_profiles = {"stable_normal", "gradual_degrade", "rapid_degrade_failure", "sensor_anomaly", "normal", "degrading", "near_failure"}
        if profile_name in valid_profiles:
            if profile_name == "normal":
                self.degradation_profile = "stable_normal"
            elif profile_name == "degrading":
                self.degradation_profile = "gradual_degrade"
            elif profile_name == "near_failure":
                self.degradation_profile = "rapid_degrade_failure"
            else:
                self.degradation_profile = profile_name

    def _determine_scenario(self, health: float) -> str:
        """Map health index and profile to scenario string."""
        if self.degradation_profile == "sensor_anomaly":
            return "degrading"
        if health > 70.0:
            return "normal"
        elif health >= 40.0:
            return "degrading"
        else:
            return "near_failure"

    def step(self, current_time: datetime, sampling_interval_sec: int = 60) -> Dict[str, Any]:
        """Generate next time-series telemetry reading for this machine."""
        self.step_count += 1
        hours_delta = sampling_interval_sec / 3600.0
        self.hours += hours_delta

        # 1. Workload sinusoidal cycle with gaussian noise
        cycle_phase = (self.step_count * 0.1) % (2 * math.pi)
        base_workload = 60.0 + 25.0 * math.sin(cycle_phase)
        workload = max(10.0, min(95.0, base_workload + self.rng.gauss(0, 3.0)))

        # 2. Degradation physics based on active profile
        workload_factor = workload / 100.0
        if self.degradation_profile in ("stable_normal", "normal"):
            health_decay = (0.005 + 0.005 * workload_factor) + self.rng.gauss(0, 0.002)
            wear_increase = (0.01 + 0.01 * workload_factor) + abs(self.rng.gauss(0, 0.002))
        elif self.degradation_profile in ("gradual_degrade", "degrading"):
            health_decay = (0.08 + 0.05 * workload_factor) + self.rng.gauss(0, 0.01)
            wear_increase = (0.08 + 0.06 * workload_factor) + abs(self.rng.gauss(0, 0.01))
        elif self.degradation_profile in ("rapid_degrade_failure", "near_failure"):
            health_decay = (0.18 + 0.12 * workload_factor) + self.rng.gauss(0, 0.02)
            wear_increase = (0.16 + 0.12 * workload_factor) + abs(self.rng.gauss(0, 0.02))
        elif self.degradation_profile == "sensor_anomaly":
            health_decay = 0.02
            wear_increase = 0.02
        else:
            health_decay = 0.05
            wear_increase = 0.05

        self.health_index = max(1.0, min(100.0, self.health_index - health_decay))
        self.tool_wear = max(0.0, min(99.0, self.tool_wear + wear_increase))
        scenario = self._determine_scenario(self.health_index)

        # Degradation factor (0.0 = brand new, 1.0 = total failure)
        degrad = (100.0 - self.health_index) / 100.0

        # 3. Equipment-specific physics models
        m_type = self.backend_type.upper()
        
        if m_type == "3D_PRINTER":
            base_temp = 55.0
            temp = base_temp + (workload * 0.30) + (degrad * 38.0) + self.rng.gauss(0, 1.0)
            base_vib = 0.4
            vibration = base_vib + (workload * 0.008) + (degrad ** 2) * 5.5 + abs(self.rng.gauss(0, 0.08))
            current = 3.5 + (workload * 0.06) + (degrad * 8.5) + self.rng.gauss(0, 0.25)
            target_rpm = 3000
            rpm = int(target_rpm - (workload * 4.0) - (degrad * 400.0) + self.rng.gauss(0, 15.0))
        else:  # Default CNC Milling Machine
            temp = 42.0 + (workload * 0.25) + (degrad * 45.0) + self.rng.gauss(0, 1.2)
            vibration = 1.2 + (workload * 0.015) + (degrad ** 2) * 18.0 + abs(self.rng.gauss(0, 0.2))
            current = 12.0 + (workload * 0.22) + (degrad * 25.0) + self.rng.gauss(0, 0.8)
            rpm = int(12000 - (workload * 10.0) - (degrad * 1500.0) + self.rng.gauss(0, 45.0))

        # Sensor Anomaly Noise Spikes under anomaly scenario
        if self.degradation_profile == "sensor_anomaly":
            spike_type = self.rng.choice(["temp_spike", "vib_spike", "current_spike", "rpm_drop"])
            if spike_type == "temp_spike":
                temp += self.rng.uniform(25.0, 40.0)
            elif spike_type == "vib_spike":
                vibration += self.rng.uniform(8.0, 12.0)
            elif spike_type == "current_spike":
                current += self.rng.uniform(15.0, 25.0)
            elif spike_type == "rpm_drop":
                rpm = max(100, rpm - int(self.rng.uniform(800, 1500)))

        # Clamp values within validation bounds
        temp = max(DEFAULT_VALIDATION_LIMITS["temp"]["min"], min(DEFAULT_VALIDATION_LIMITS["temp"]["max"], round(temp, 2)))
        vibration = max(DEFAULT_VALIDATION_LIMITS["vibration"]["min"], min(DEFAULT_VALIDATION_LIMITS["vibration"]["max"], round(vibration, 3)))
        current = max(DEFAULT_VALIDATION_LIMITS["current"]["min"], min(DEFAULT_VALIDATION_LIMITS["current"]["max"], round(current, 2)))
        rpm = max(int(DEFAULT_VALIDATION_LIMITS["rpm"]["min"]), min(int(DEFAULT_VALIDATION_LIMITS["rpm"]["max"]), int(rpm)))
        hours = max(DEFAULT_VALIDATION_LIMITS["hours"]["min"], min(DEFAULT_VALIDATION_LIMITS["hours"]["max"], round(self.hours, 3)))
        workload = max(DEFAULT_VALIDATION_LIMITS["workload"]["min"], min(DEFAULT_VALIDATION_LIMITS["workload"]["max"], round(workload, 1)))
        tool_wear = max(DEFAULT_VALIDATION_LIMITS["tool_wear"]["min"], min(DEFAULT_VALIDATION_LIMITS["tool_wear"]["max"], round(self.tool_wear, 2)))
        health_index = max(DEFAULT_VALIDATION_LIMITS["health_index"]["min"], min(DEFAULT_VALIDATION_LIMITS["health_index"]["max"], round(self.health_index, 2)))

        return {
            "machine_id": self.machine_id,
            "timestamp": current_time,
            "machine_type": self.backend_type,
            "temp": temp,
            "vibration": vibration,
            "current": current,
            "rpm": rpm,
            "hours": hours,
            "workload": workload,
            "tool_wear": tool_wear,
            "health_index": health_index,
            "scenario": scenario,
        }


def generate_telemetry_dataset(
    num_machines: int = 6,
    samples_per_machine: int = 500,
    seed: int = 42,
    sampling_interval_sec: int = 60,
    start_time: Optional[datetime] = None,
) -> List[Dict[str, Any]]:
    """Generate time-series telemetry dataset for multiple machines.
    
    Args:
        num_machines: Total number of machines to simulate (must be >= 1).
        samples_per_machine: Telemetry samples per machine (must be >= 1).
        seed: Random seed for exact reproducibility.
        sampling_interval_sec: Seconds between consecutive readings.
        start_time: Starting UTC datetime (defaults to fixed reference timestamp).
        
    Returns:
        List of telemetry dictionaries adhering to SensorData schema.
    """
    if num_machines < 1:
        raise ValueError(f"num_machines must be >= 1, got {num_machines}")
    if samples_per_machine < 1:
        raise ValueError(f"samples_per_machine must be >= 1, got {samples_per_machine}")

    rng = random.Random(seed)
    
    if start_time is None:
        start_time = datetime(2026, 10, 1, 0, 0, 0, tzinfo=timezone.utc)

    profiles = ["stable_normal", "gradual_degrade", "rapid_degrade_failure"]

    simulators: List[TelemetrySimulator] = []
    for i in range(num_machines):
        machine_type = "CNC" if i % 2 == 0 else "3D_Printer"
        
        if machine_type == "CNC":
            machine_id = f"CNC-{(i // 2) + 1:03d}"
        else:
            machine_id = f"PRINTER-3D-{(i // 2) + 1:02d}"

        profile = profiles[i % len(profiles)]
        initial_hours = 100.0 + rng.uniform(0, 500.0)
        initial_health = 95.0 + rng.uniform(-2.0, 3.0)
        initial_tool_wear = rng.uniform(2.0, 10.0)

        sim = TelemetrySimulator(
            machine_id=machine_id,
            machine_type=machine_type,
            initial_hours=initial_hours,
            initial_health=initial_health,
            initial_tool_wear=initial_tool_wear,
            degradation_profile=profile,
            random_state=random.Random(seed + i * 1000),
        )
        simulators.append(sim)

    dataset: List[Dict[str, Any]] = []

    for sim in simulators:
        current_time = start_time
        for _ in range(samples_per_machine):
            record = sim.step(current_time=current_time, sampling_interval_sec=sampling_interval_sec)
            dataset.append(record)
            current_time += timedelta(seconds=sampling_interval_sec)

    return dataset
