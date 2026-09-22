"""Command-Line Interface for Synthetic Telemetry Generation.

Usage Example:
    python -m simulator.generate_data --machines 6 --samples-per-machine 500 --seed 42 --output data/raw/simulated_telemetry.csv
"""

import argparse
import csv
import os
import sys
from collections import Counter
from datetime import datetime
from typing import List, Dict, Any

from config.schema import SensorData, validate_telemetry_dict
from simulator.engine import generate_telemetry_dataset


def parse_args() -> argparse.Namespace:
    """Parse command line arguments for telemetry data generator."""
    parser = argparse.ArgumentParser(
        description="Generate synthetic machine telemetry dataset for CNC machines and 3D printers."
    )
    parser.add_argument(
        "--machines",
        type=int,
        default=6,
        help="Total number of machines to simulate (default: 6)",
    )
    parser.add_argument(
        "--samples-per-machine",
        type=int,
        default=500,
        help="Number of time-series samples per machine (default: 500)",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed for exact reproducibility (default: 42)",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="data/raw/simulated_telemetry.csv",
        help="Output CSV file path (default: data/raw/simulated_telemetry.csv)",
    )
    parser.add_argument(
        "--interval-seconds",
        type=int,
        default=60,
        help="Sampling interval in seconds between readings (default: 60)",
    )

    args = parser.parse_args()

    # CLI Validation
    if args.machines < 1:
        parser.error(f"--machines must be at least 1, got {args.machines}")
    if args.samples_per_machine < 1:
        parser.error(f"--samples-per-machine must be at least 1, got {args.samples_per_machine}")
    if args.interval_seconds < 1:
        parser.error(f"--interval-seconds must be at least 1, got {args.interval_seconds}")

    return args


def generate_and_save(
    machines: int = 6,
    samples_per_machine: int = 500,
    seed: int = 42,
    output_path: str = "data/raw/simulated_telemetry.csv",
    interval_seconds: int = 60,
) -> Dict[str, Any]:
    """Generate telemetry dataset, validate against schema, and save to CSV.
    
    Returns:
        Summary metrics dictionary.
    """
    print(f"Generating synthetic telemetry: {machines} machines, {samples_per_machine} samples/machine, seed={seed}...")

    raw_records = generate_telemetry_dataset(
        num_machines=machines,
        samples_per_machine=samples_per_machine,
        seed=seed,
        sampling_interval_sec=interval_seconds,
    )

    # 1. Validate every record using SensorData Pydantic schema
    validation_failures = 0
    for idx, rec in enumerate(raw_records):
        is_valid, err = validate_telemetry_dict(rec, require_full_schema=True)
        if not is_valid:
            validation_failures += 1
            print(f"Validation error at record {idx}: {err}", file=sys.stderr)

    if validation_failures > 0:
        raise ValueError(f"Dataset generation failed: {validation_failures} records failed schema validation!")

    # 2. Check duplicate machine/timestamp pairs
    seen_keys = set()
    duplicate_count = 0
    for rec in raw_records:
        key = (rec["machine_id"], rec["timestamp"])
        if key in seen_keys:
            duplicate_count += 1
        seen_keys.add(key)

    # 3. Create output directory if missing
    output_dir = os.path.dirname(os.path.abspath(output_path))
    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir, exist_ok=True)

    # 4. Write records to CSV using canonical field order
    field_names = SensorData.all_field_names()
    with open(output_path, mode="w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=field_names)
        writer.writeheader()
        for rec in raw_records:
            row = rec.copy()
            # Serialize datetime to ISO string
            if isinstance(row["timestamp"], datetime):
                row["timestamp"] = row["timestamp"].strftime("%Y-%m-%dT%H:%M:%SZ")
            writer.writerow(row)

    # 5. Compute summary metrics
    machine_counts = Counter([r["machine_id"] for r in raw_records])
    type_counts = Counter([r["machine_type"] for r in raw_records])
    scenario_counts = Counter([r["scenario"] for r in raw_records])

    sensor_numeric_fields = ["temp", "vibration", "current", "rpm", "hours", "workload", "tool_wear", "health_index"]
    min_max_stats = {}
    for f_name in sensor_numeric_fields:
        vals = [r[f_name] for r in raw_records]
        min_max_stats[f_name] = {"min": min(vals), "max": max(vals)}

    summary = {
        "output_path": output_path,
        "total_rows": len(raw_records),
        "total_columns": len(field_names),
        "machines": machines,
        "samples_per_machine": samples_per_machine,
        "rows_per_machine": dict(machine_counts),
        "type_counts": dict(type_counts),
        "scenario_counts": dict(scenario_counts),
        "validation_failures": validation_failures,
        "duplicate_records": duplicate_count,
        "min_max_stats": min_max_stats,
    }

    return summary


def main():
    """CLI execution entrypoint."""
    args = parse_args()
    summary = generate_and_save(
        machines=args.machines,
        samples_per_machine=args.samples_per_machine,
        seed=args.seed,
        output_path=args.output,
        interval_seconds=args.interval_seconds,
    )

    print("\n" + "=" * 80)
    print("TELEMETRY SIMULATOR GENERATION COMPLETE")
    print("=" * 80)
    print(f"Output Path         : {summary['output_path']}")
    print(f"Total Records       : {summary['total_rows']} rows x {summary['total_columns']} columns")
    print(f"Validation Failures : {summary['validation_failures']}")
    print(f"Duplicate Records   : {summary['duplicate_records']}")
    print("\nRows Per Machine:")
    for m_id, count in summary['rows_per_machine'].items():
        print(f"  - {m_id:<15}: {count} rows")
    print("\nMachine Type Breakdown:")
    for m_type, count in summary['type_counts'].items():
        print(f"  - {m_type:<15}: {count} rows")
    print("\nScenario Breakdown:")
    for scenario, count in summary['scenario_counts'].items():
        print(f"  - {scenario:<15}: {count} rows")
    print("\nNumeric Sensor Min/Max Range:")
    for f_name, stats in summary['min_max_stats'].items():
        print(f"  - {f_name:<15}: min={stats['min']}, max={stats['max']}")
    print("=" * 80 + "\n")


if __name__ == "__main__":
    main()
