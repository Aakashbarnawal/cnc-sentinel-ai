"""Background Managed Simulator Service for Digital Twin Machines."""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional

from simulator.engine import TelemetrySimulator, BACKEND_MACHINE_TYPE_MAP
from backend.schemas import TelemetryCreate, PredictionRequest
from backend.services.telemetry_service import create_telemetry_reading
from backend.services.prediction_service import predict_machine_failure
from backend.services.diagnostic_service import evaluate_equipment_diagnostics
from backend.services.telegram_service import send_machine_alert
from backend.services.email_service import send_machine_email_alert

logger = logging.getLogger(__name__)

# Default Default Virtual Machines to initialize
DEFAULT_VIRTUAL_MACHINES = [
    {"machine_id": "SN-CNC-001", "machine_type": "CNC", "degradation_profile": "stable_normal"},
    {"machine_id": "SN-PRN-002", "machine_type": "3D_Printer", "degradation_profile": "gradual_degrade"},
    {"machine_id": "SN-MTR-003", "machine_type": "ELECTRIC_MOTOR", "degradation_profile": "stable_normal"},
    {"machine_id": "SN-PMP-004", "machine_type": "PUMP_COMPRESSOR", "degradation_profile": "rapid_degrade_failure"},
]


class SimulationManager:
    """Manager for virtual machine simulation background tasks."""

    def __init__(self):
        self.simulators: Dict[str, TelemetrySimulator] = {}
        self.is_running: bool = False
        self.speed_factor: float = 1.0
        self.base_interval_sec: float = 2.0
        self._task: Optional[asyncio.Task] = None
        self._db: Any = None
        
        # Pre-populate default virtual machines
        for vm in DEFAULT_VIRTUAL_MACHINES:
            self.add_virtual_machine(
                machine_id=vm["machine_id"],
                machine_type=vm["machine_type"],
                scenario=vm["degradation_profile"],
            )

    def add_virtual_machine(
        self,
        machine_id: str,
        machine_type: str = "CNC",
        scenario: str = "normal",
        initial_health: float = 95.0,
    ) -> TelemetrySimulator:
        """Register a new virtual machine digital twin."""
        sim = TelemetrySimulator(
            machine_id=machine_id,
            machine_type=machine_type,
            initial_health=initial_health,
            degradation_profile="stable_normal" if scenario == "normal" else scenario,
        )
        self.simulators[machine_id] = sim
        if self._db is not None:
            self.ensure_virtual_machines_registered(self._db)
        return sim

    def ensure_virtual_machines_registered(self, db: Any):
        """Ensure all managed virtual machines are idempotently registered in db['machines']."""
        if db is None:
            return
        from backend.schemas import MachineCreate
        from backend.services.telemetry_service import register_machine

        for m_id, sim in list(self.simulators.items()):
            try:
                existing = db["machines"].find_one({"machine_id": m_id})
                if not existing:
                    backend_type = BACKEND_MACHINE_TYPE_MAP.get(sim.machine_type, "CNC")
                    m_create = MachineCreate(machine_id=m_id, machine_type=backend_type)
                    register_machine(m_create, db)
                    logger.info(f"Registered virtual machine '{m_id}' ({backend_type}) in database.")
            except Exception as e:
                logger.warning(f"Could not auto-register virtual machine '{m_id}': {e}")

    def remove_virtual_machine(self, machine_id: str) -> bool:
        """Remove a virtual machine from simulation."""
        if machine_id in self.simulators:
            del self.simulators[machine_id]
            return True
        return False

    def set_machine_scenario(self, machine_id: str, scenario: str) -> bool:
        """Update operational scenario for a specific machine."""
        if machine_id in self.simulators:
            self.simulators[machine_id].set_scenario(scenario)
            return True
        return False

    def set_speed(self, speed_factor: float):
        """Set simulation speed multiplier (e.g. 0.5x, 1.0x, 2.0x, 5.0x)."""
        self.speed_factor = max(0.1, min(10.0, float(speed_factor)))

    def get_status(self) -> Dict[str, Any]:
        """Return current status overview of all virtual machine simulators."""
        active_list = []
        for m_id, sim in self.simulators.items():
            active_list.append({
                "machine_id": m_id,
                "machine_type": sim.machine_type,
                "backend_type": sim.backend_type,
                "health_index": round(sim.health_index, 1),
                "scenario": sim._determine_scenario(sim.health_index),
                "degradation_profile": sim.degradation_profile,
                "hours": round(sim.hours, 1),
                "tool_wear": round(sim.tool_wear, 1),
            })
        return {
            "is_running": self.is_running,
            "speed_factor": self.speed_factor,
            "base_interval_sec": self.base_interval_sec,
            "effective_interval_sec": round(self.base_interval_sec / self.speed_factor, 2),
            "machine_count": len(self.simulators),
            "machines": active_list,
        }

    async def start_simulation(self, db: Any):
        """Start or resume background simulation loop."""
        self._db = db
        self.ensure_virtual_machines_registered(db)
        if not self.is_running:
            self.is_running = True
            loop = asyncio.get_running_loop()
            self._task = loop.create_task(self._run_loop())
            logger.info("Simulation loop started.")


    def stop_simulation(self):
        """Stop background simulation loop."""
        self.is_running = False
        if self._task and not self._task.done():
            self._task.cancel()
            self._task = None
        logger.info("Simulation loop stopped.")

    async def _run_loop(self):
        """Background loop executing simulator step and backend ingestion."""
        while self.is_running:
            try:
                now_utc = datetime.now(timezone.utc)
                for machine_id, sim in list(self.simulators.items()):
                    reading = sim.step(current_time=now_utc)

                    # Persist telemetry reading to MongoDB if DB is attached
                    if self._db is not None:
                        try:
                            # Map to TelemetryCreate schema
                            backend_type = BACKEND_MACHINE_TYPE_MAP.get(sim.machine_type, "CNC")
                            t_create = TelemetryCreate(
                                machine_id=reading["machine_id"],
                                timestamp=reading["timestamp"],
                                machine_type=backend_type,
                                temp=reading["temp"],
                                vibration=reading["vibration"],
                                current=reading["current"],
                                rpm=reading["rpm"],
                                hours=reading["hours"],
                                workload=reading["workload"],
                                tool_wear=reading["tool_wear"],
                                health_index=reading["health_index"],
                                scenario=reading["scenario"],
                            )
                            create_telemetry_reading(t_create, self._db)
                        except Exception as ex:
                            # Log duplicate timestamp or ingestion warning silently
                            pass

                        # Evaluate equipment diagnostics
                        diag = evaluate_equipment_diagnostics(
                            equipment_type=sim.machine_type,
                            temp=reading["temp"],
                            vibration=reading["vibration"],
                            current=reading["current"],
                            rpm=reading["rpm"],
                            tool_wear=reading["tool_wear"],
                        )

                        # Trigger Telegram and Email alerts if severity is WARNING or CRITICAL
                        if diag["severity"] in ("WARNING", "CRITICAL"):
                            send_machine_alert(
                                machine_id=sim.machine_id,
                                equipment_type=sim.machine_type,
                                severity=diag["severity"],
                                scenario=reading["scenario"],
                                temp=reading["temp"],
                                vibration=reading["vibration"],
                                current=reading["current"],
                                rpm=reading["rpm"],
                                health_index=reading["health_index"],
                                suspected_issue=diag["primary_suspected_issue"],
                                recommended_action=diag["recommended_action"],
                                timestamp_str=reading["timestamp"].strftime("%Y-%m-%d %H:%M:%S UTC"),
                            )
                            send_machine_email_alert(
                                machine_id=sim.machine_id,
                                equipment_type=sim.machine_type,
                                severity=diag["severity"],
                                scenario=reading["scenario"],
                                temp=reading["temp"],
                                vibration=reading["vibration"],
                                current=reading["current"],
                                rpm=reading["rpm"],
                                health_index=reading["health_index"],
                                suspected_issue=diag["primary_suspected_issue"],
                                recommended_action=diag["recommended_action"],
                                timestamp_str=reading["timestamp"].strftime("%Y-%m-%d %H:%M:%S UTC"),
                            )

                # Calculate sleep interval according to speed factor
                sleep_sec = max(0.2, self.base_interval_sec / self.speed_factor)
                await asyncio.sleep(sleep_sec)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in simulation loop: {e}")
                await asyncio.sleep(2.0)


# Global Singleton Manager Instance
simulation_manager = SimulationManager()
