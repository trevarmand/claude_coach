#!/usr/bin/env python3
"""Parse a .fit file and output ride metrics as JSON."""

import json
import math
import sys
from pathlib import Path

from fitparse import FitFile


def semicircles_to_degrees(value):
    """Convert Garmin semicircle units to decimal degrees."""
    if value is None:
        return None
    return value * (180.0 / 2**31)


def parse_fit(filepath):
    ff = FitFile(str(filepath))

    # --- Session summary ---
    session = {}
    for msg in ff.get_messages("session"):
        session = {f.name: f.value for f in msg.fields}
        break  # Only one session expected

    # --- Lap data ---
    laps = []
    for msg in ff.get_messages("lap"):
        lap = {f.name: f.value for f in msg.fields}
        laps.append({
            "lap": len(laps) + 1,
            "duration_s": lap.get("total_timer_time"),
            "distance_km": round(lap["total_distance"] / 1000, 2) if lap.get("total_distance") else None,
            "avg_power_w": lap.get("avg_power"),
            "max_power_w": lap.get("max_power"),
            "avg_hr_bpm": lap.get("avg_heart_rate"),
            "max_hr_bpm": lap.get("max_heart_rate"),
            "avg_cadence_rpm": lap.get("avg_cadence"),
            "avg_speed_kph": round(lap["enhanced_avg_speed"] * 3.6, 1) if lap.get("enhanced_avg_speed") else None,
            "total_ascent_m": lap.get("total_ascent"),
            "total_descent_m": lap.get("total_descent"),
            "calories": lap.get("total_calories"),
        })

    # --- Per-second records ---
    records = []
    for msg in ff.get_messages("record"):
        rec = {f.name: f.value for f in msg.fields}
        records.append(rec)

    # --- Compute metrics from records ---
    powers = [r["power"] for r in records if r.get("power") is not None]
    heart_rates = [r["heart_rate"] for r in records if r.get("heart_rate") is not None]
    cadences = [r["cadence"] for r in records if r.get("cadence") is not None]
    speeds = [r["enhanced_speed"] for r in records if r.get("enhanced_speed") is not None]
    temperatures = [r["temperature"] for r in records if r.get("temperature") is not None]

    # Normalized Power (30s rolling average of power, raised to 4th, averaged, then 4th root)
    np_value = None
    if len(powers) >= 30:
        rolling = []
        for i in range(29, len(powers)):
            window_avg = sum(powers[i - 29:i + 1]) / 30
            rolling.append(window_avg ** 4)
        np_value = round((sum(rolling) / len(rolling)) ** 0.25)

    duration_s = session.get("total_timer_time", 0)
    distance_m = session.get("total_distance", 0)

    summary = {
        "file": Path(filepath).name,
        "sport": session.get("sport"),
        "sub_sport": session.get("sub_sport"),
        "start_time": str(session.get("start_time")),
        "duration_s": duration_s,
        "duration_hms": f"{int(duration_s // 3600)}:{int((duration_s % 3600) // 60):02d}:{int(duration_s % 60):02d}" if duration_s else None,
        "distance_km": round(distance_m / 1000, 2) if distance_m else None,
        "total_ascent_m": session.get("total_ascent"),
        "total_descent_m": session.get("total_descent"),
        "calories": session.get("total_calories"),
        "avg_speed_kph": round(session["enhanced_avg_speed"] * 3.6, 1) if session.get("enhanced_avg_speed") else None,
        "max_speed_kph": round(session["enhanced_max_speed"] * 3.6, 1) if session.get("enhanced_max_speed") else None,
        "power": {
            "avg_w": session.get("avg_power"),
            "max_w": session.get("max_power"),
            "normalized_w": np_value,
        } if powers else None,
        "heart_rate": {
            "avg_bpm": session.get("avg_heart_rate"),
            "max_bpm": session.get("max_heart_rate"),
        } if heart_rates else None,
        "cadence": {
            "avg_rpm": session.get("avg_cadence"),
            "max_rpm": session.get("max_cadence"),
        } if cadences else None,
        "temperature": {
            "avg_c": round(sum(temperatures) / len(temperatures), 1),
            "min_c": min(temperatures),
            "max_c": max(temperatures),
        } if temperatures else None,
        "num_laps": len(laps),
        "num_records": len(records),
        "laps": laps,
    }

    return summary


def detect_intervals(filepath, smooth_window=30, min_work_duration=45, min_rest_duration=20):
    """Detect structured work/rest intervals from power data.

    Conservative approach: only reports intervals when there is a clear, deliberate
    on/off pattern. Normal power fluctuations in a steady ride should NOT produce
    intervals. A ride without structured intervals returns ride_type="steady".

    An interval must be:
    - At least min_work_duration seconds of sustained elevated power
    - Significantly above the ride average (>120% of avg power)
    - Followed or preceded by a clear rest period (power drops well below average)

    The algorithm also requires at least 2 work efforts with intervening rest to
    classify as an "interval workout." A single hard effort is reported as a "sprint"
    or "surge" but the ride is still classified as steady/non-interval.
    """
    ff = FitFile(str(filepath))

    records = []
    for msg in ff.get_messages("record"):
        rec = {f.name: f.value for f in msg.fields}
        records.append({
            "timestamp": rec.get("timestamp"),
            "power": rec.get("power") or 0,
            "heart_rate": rec.get("heart_rate"),
            "cadence": rec.get("cadence"),
        })

    if len(records) < smooth_window * 2:
        return {"ride_type": "too_short", "efforts": [], "workout_summary": "Ride too short for analysis"}

    raw_powers = [r["power"] for r in records]
    nonzero_powers = [p for p in raw_powers if p > 0]
    if not nonzero_powers:
        return {"ride_type": "no_power", "efforts": [], "workout_summary": "No power data"}

    avg_power = sum(raw_powers) / len(raw_powers)

    # Smooth with 30s rolling average to ignore short spikes
    smoothed = []
    for i in range(len(raw_powers)):
        start = max(0, i - smooth_window + 1)
        smoothed.append(sum(raw_powers[start:i + 1]) / (i - start + 1))

    # Thresholds: work must be clearly above average, rest clearly below
    work_threshold = avg_power * 1.20
    rest_threshold = avg_power * 0.65

    # Classify each second
    HIGH = "high"
    LOW = "low"
    MID = "mid"
    states = []
    for p in smoothed:
        if p >= work_threshold:
            states.append(HIGH)
        elif p <= rest_threshold:
            states.append(LOW)
        else:
            states.append(MID)

    # Group into contiguous segments
    segments = []
    current = states[0]
    start_idx = 0
    for i in range(1, len(states)):
        if states[i] != current:
            segments.append({"state": current, "start": start_idx, "end": i - 1})
            current = states[i]
            start_idx = i
    segments.append({"state": current, "start": start_idx, "end": len(states) - 1})

    # Merge short gaps (<10s) between HIGH segments
    merged = []
    for seg in segments:
        if (merged
                and seg["state"] == HIGH
                and merged[-1]["state"] == HIGH
                and seg["start"] - merged[-1]["end"] <= 10):
            merged[-1]["end"] = seg["end"]
        else:
            merged.append(dict(seg))

    # Extract efforts that meet minimum duration
    def _build_effort(seg):
        interval_records = records[seg["start"]:seg["end"] + 1]
        interval_powers = [r["power"] for r in interval_records if r["power"]]
        interval_hrs = [r["heart_rate"] for r in interval_records if r["heart_rate"]]
        interval_cadences = [r["cadence"] for r in interval_records if r["cadence"]]
        return {
            "start_s": seg["start"],
            "end_s": seg["end"],
            "start_time": str(records[seg["start"]]["timestamp"]),
            "duration_s": seg["end"] - seg["start"] + 1,
            "avg_power_w": round(sum(interval_powers) / len(interval_powers)) if interval_powers else 0,
            "max_power_w": max(interval_powers) if interval_powers else 0,
            "avg_hr_bpm": round(sum(interval_hrs) / len(interval_hrs)) if interval_hrs else None,
            "max_hr_bpm": max(interval_hrs) if interval_hrs else None,
            "avg_cadence_rpm": round(sum(interval_cadences) / len(interval_cadences)) if interval_cadences else None,
        }

    work_efforts = []
    rest_periods = []
    for seg in merged:
        duration = seg["end"] - seg["start"] + 1
        if seg["state"] == HIGH and duration >= min_work_duration:
            work_efforts.append(_build_effort(seg))
        elif seg["state"] == LOW and duration >= min_rest_duration:
            rest_periods.append(_build_effort(seg))

    # Determine ride type and build summary
    # Check if work efforts have rest periods between them (true interval pattern)
    has_interval_pattern = False
    if len(work_efforts) >= 2:
        # Check that at least one rest period falls between two work efforts
        for rest in rest_periods:
            for i in range(len(work_efforts) - 1):
                if work_efforts[i]["end_s"] < rest["start_s"] < work_efforts[i + 1]["start_s"]:
                    has_interval_pattern = True
                    break
            if has_interval_pattern:
                break

    if has_interval_pattern:
        ride_type = "intervals"
        workout_summary = _describe_interval_workout(work_efforts, rest_periods)
    elif work_efforts:
        ride_type = "steady_with_surges"
        surge_descriptions = []
        for e in work_efforts:
            surge_descriptions.append(
                f"{_format_duration(e['duration_s'])} @ {e['avg_power_w']}W"
            )
        workout_summary = f"Steady ride with {len(work_efforts)} surge(s): " + ", ".join(surge_descriptions)
    else:
        ride_type = "steady"
        workout_summary = f"Steady ride — avg {round(avg_power)}W, no structured intervals detected"

    return {
        "ride_type": ride_type,
        "thresholds": {
            "work_above_w": round(work_threshold),
            "rest_below_w": round(rest_threshold),
            "avg_power_w": round(avg_power),
        },
        "efforts": work_efforts,
        "rest_periods": rest_periods,
        "workout_summary": workout_summary,
    }


def _describe_interval_workout(work_efforts, rest_periods):
    """Describe a structured interval workout."""
    groups = _group_similar_efforts(work_efforts)

    parts = []
    for group in groups:
        n = len(group)
        g_avg_dur = sum(e["duration_s"] for e in group) / n
        g_avg_pwr = sum(e["avg_power_w"] for e in group) / n
        dur_str = _format_duration(g_avg_dur)
        parts.append(f"{n}x{dur_str} @ {round(g_avg_pwr)}W")

    if rest_periods:
        rest_durations = [r["duration_s"] for r in rest_periods]
        avg_rest = sum(rest_durations) / len(rest_durations)
        rest_str = f" with ~{_format_duration(avg_rest)} rest"
    else:
        rest_str = ""

    return " + ".join(parts) + rest_str


def _group_similar_efforts(efforts, power_tolerance=0.15, duration_tolerance=0.30):
    """Group efforts with similar power and duration."""
    if not efforts:
        return []

    groups = [[efforts[0]]]
    for e in efforts[1:]:
        matched = False
        for group in groups:
            g_avg_pwr = sum(g["avg_power_w"] for g in group) / len(group)
            g_avg_dur = sum(g["duration_s"] for g in group) / len(group)

            pwr_close = abs(e["avg_power_w"] - g_avg_pwr) / g_avg_pwr <= power_tolerance if g_avg_pwr else True
            dur_close = abs(e["duration_s"] - g_avg_dur) / g_avg_dur <= duration_tolerance if g_avg_dur else True

            if pwr_close and dur_close:
                group.append(e)
                matched = True
                break

        if not matched:
            groups.append([e])

    return groups


def _format_duration(seconds):
    """Format seconds into a human-readable string."""
    seconds = round(seconds)
    if seconds < 60:
        return f"{seconds}s"
    minutes = seconds // 60
    remaining = seconds % 60
    if remaining == 0:
        return f"{minutes}min"
    return f"{minutes}min{remaining:02d}s"


def main():
    if len(sys.argv) < 2:
        print("Usage: python parse_fit.py <file.fit> [--records] [--intervals]", file=sys.stderr)
        sys.exit(1)

    filepath = Path(sys.argv[1])
    if not filepath.exists():
        print(f"File not found: {filepath}", file=sys.stderr)
        sys.exit(1)

    include_records = "--records" in sys.argv
    include_intervals = "--intervals" in sys.argv

    result = parse_fit(filepath)

    if include_intervals:
        result["intervals"] = detect_intervals(filepath)

    if include_records:
        ff = FitFile(str(filepath))
        time_series = []
        for msg in ff.get_messages("record"):
            rec = {f.name: f.value for f in msg.fields}
            time_series.append({
                "timestamp": str(rec.get("timestamp")),
                "power_w": rec.get("power"),
                "heart_rate_bpm": rec.get("heart_rate"),
                "cadence_rpm": rec.get("cadence"),
                "speed_kph": round(rec["enhanced_speed"] * 3.6, 1) if rec.get("enhanced_speed") else None,
                "altitude_m": rec.get("enhanced_altitude"),
                "temperature_c": rec.get("temperature"),
                "lat": semicircles_to_degrees(rec.get("position_lat")),
                "lon": semicircles_to_degrees(rec.get("position_long")),
            })
        result["records"] = time_series

    print(json.dumps(result, indent=2, default=str))


if __name__ == "__main__":
    main()
