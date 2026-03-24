# analyze-ride

Analyze a cycling ride file and provide a coaching summary.

## When to use

Activate when the user:
- Asks to analyze a ride, workout, or activity file
- Drops a new .fit file into training_log/
- Asks "how was my ride?" or similar
- Asks what workout they did, or about intervals in a ride

## Steps

1. **Identify the file.** If the user specifies a file, use it. Otherwise, find the most recent file in `training_log/` by filename date (MM-DD-YYYY format).

2. **Run the parser.** Use the project's virtual environment:
   `.venv/bin/python3 tools/parse_fit.py <path> --intervals`

3. **Interpret the results as a coach.** Cover these areas:

   **Ride overview** — Duration, distance, avg/max speed. Note if indoor (virtual_activity) or outdoor.

   **Power analysis** (if available) — Average power, Normalized Power, max power. Comment on the ratio of NP to avg power (variability index) — closer to 1.0 means steadier effort.

   **Heart rate analysis** (if available) — Average and max HR. Note if HR drifted upward over the ride (cardiac drift = fatigue or dehydration).

   **Workout identification** — Based on the `intervals` field:
   - `ride_type: "intervals"` — Describe the interval structure (sets, duration, power targets, rest). Compare to common workout types (VO2max intervals, threshold blocks, over-unders, Tabata, etc.). Cross-reference the lap data with the detected efforts — laps often reveal the intended structure more clearly than the raw interval detection (e.g., 3x12min work laps with 5min rest laps).
   - `ride_type: "steady_with_surges"` — It's primarily a steady ride. Mention the surges but don't overstate them. Could be terrain-driven or spontaneous efforts.
   - `ride_type: "steady"` — Endurance/base ride. Comment on pacing consistency.

   **Environmental factors** — Note temperature if available (heat stress impacts performance and recovery demands). Flag conditions that affect fueling/hydration needs.

   **Effort assessment** — Was this easy, moderate, hard, or maximal? Use power and HR together. A 20-minute ride at 151W avg and 129 bpm avg is a lighter session. Be calibrated.

   **Coaching note** — One or two actionable observations. Examples: cadence dropped during rest periods, HR drift suggests dehydration, pacing was uneven, hydration needs in heat, etc. Keep it to 2-3 sentences max.

## Output format

Present as a concise coaching debrief, not a raw data dump. Use the numbers to support your assessment but lead with the interpretation. Keep it under 20 lines unless the user asks for more detail.

## Example

Input: 07-25-2025.fit — outdoor road ride, 1hr 18min, 34.4km, 30-36°C

> **Outdoor road ride** — 1hr 18min, 34.4 km, in serious heat (30-36°C).
>
> **Power:** 155W avg / 178W NP / 585W max. Variability index of 1.15 — not a steady ride, consistent with interval structure.
>
> **Heart rate:** 150 bpm avg / 171 max. HR climbed progressively — started around 150s in early work sets and pushed into high 160s by the third block. Combination of accumulated fatigue and heat.
>
> **Workout:** Structured interval session. Lap data tells the story — **3x12min work intervals (~195W) with 5min rest**, bookended by warmup and cooldown. The tool picked up surges within each 12-min block where power pushed 200W+ with brief dips. Final 5-min effort (lap 9, 203W) looks like a bonus kick before cooldown.
>
> **Effort:** Hard session. Avg HR of 150 across 78 minutes with peaks at 171 — solid threshold workout.
>
> **Coaching note:** Cadence was solid at 88 rpm during work intervals but dropped to low 70s during rest — try keeping legs spinning higher during recovery (85+) to clear lactate faster. In 30°C+ heat, a session like this demands 700-900ml/hr with electrolytes.

## Important

- Do NOT fabricate metrics. Only report what the tool outputs.
- Do NOT assume FTP or training zones unless the user has provided them.
- A ride without structured intervals is just a ride — don't force an interval interpretation.
- If power data is missing, analyze with HR and speed instead.
- Cross-reference lap data with interval detection — the laps often reveal the intended workout structure that the algorithm may fragment into smaller pieces.
