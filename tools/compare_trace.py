"""Compare a user-supplied reference trace with one exported runner (SI units).

Reference JSON: {"samples": [{"time": 0.0, "distance": 0.0, "speed": 3.0,
"hp": 2800.0}, ...]}. Missing quantities are not inferred. No game connection.
"""
from __future__ import annotations
import argparse
import bisect
import json
import math
from pathlib import Path


def compare(reference: dict, result: dict, runner_index: int = 0) -> dict:
    frames = result["frames"]
    times = [f["time"] for f in frames]
    if not times or any(not math.isfinite(t) for t in times) or any(a >= b for a, b in zip(times, times[1:])):
        raise ValueError("Simulation timestamps must be finite and strictly increasing")
    if not frames or not 0 <= runner_index < len(frames[0]["runners"]):
        raise ValueError("Invalid runner index")
    errors = {key: [] for key in ("distance", "speed", "hp")}
    skipped = 0
    samples = reference.get("samples")
    if not isinstance(samples, list) or not samples:
        raise ValueError("Reference must contain a nonempty samples array")
    previous = -math.inf
    for sample in samples:
        t = sample["time"]
        if not math.isfinite(t) or t <= previous:
            raise ValueError("Reference timestamps must be finite and strictly increasing")
        previous = t
        if t < times[0] or t > times[-1]:
            skipped += 1
            continue
        i = min(bisect.bisect_right(times, t) - 1, len(times) - 1)
        j = min(i + 1, len(times) - 1)
        fraction = (t - times[i]) / (times[j] - times[i]) if i != j else 0
        for key in errors:
            if key in sample:
                value = sample[key]
                if not math.isfinite(value):
                    raise ValueError("Reference values must be finite")
                a, b = frames[i]["runners"][runner_index][key], frames[j]["runners"][runner_index][key]
                errors[key].append(a + (b - a) * fraction - value)
    metrics = {key: {"samples": len(e), "mae": sum(abs(x) for x in e) / len(e),
                     "rmse": math.sqrt(sum(x*x for x in e) / len(e)), "max_abs": max(abs(x) for x in e)}
               for key, e in errors.items() if e}
    if not metrics:
        raise ValueError("No overlapping samples with distance, speed, or hp")
    return {"runner_index": runner_index, "model": result.get("model"), "metrics": metrics,
            "out_of_range_samples": skipped, "note": "No time alignment or units conversion was applied."}


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("reference", type=Path)
    p.add_argument("simulation", type=Path)
    p.add_argument("--runner", type=int, default=0)
    p.add_argument("--output", type=Path)
    args = p.parse_args()
    report = compare(json.loads(args.reference.read_text(encoding="utf-8-sig")), json.loads(args.simulation.read_text(encoding="utf-8-sig")), args.runner)
    content = json.dumps(report, indent=2, ensure_ascii=False, allow_nan=False)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(content, encoding="utf-8")
    print(content)
