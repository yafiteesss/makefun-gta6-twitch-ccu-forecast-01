"""Forecast launch-day Twitch viewers hour by hour, from past big launches.

The entry point is `python3 main.py`. It reads every `<id>.in` case file in
the input directory (``$MAKEFUN_INPUT_DIR``, else ``/input``) and writes one
``<id>.out`` forecast per case to the output directory (``$MAKEFUN_OUTPUT_DIR``,
else ``/output``). Each output holds five quantiles of the category's viewer
count for each of hours 2..24 of the release day (UTC).

Method, in short: the forecast is anchored on the case's hour-1 print and
shaped by the release-day curves of past big launches ("comparables") that
shipped with the case. For every comparable we take its release-day hourly
curve, expressed as ratios to its own hour-1 print. Only launches whose
hour-1 print is already substantial count as donors: a launch that unlocked
late in the day has a near-empty hour 1, so its ratios explode and say
nothing about a launch whose first hour is already busy. For each forecast
hour we fit a weighted line through the donors' log-ratios against their
log hour-1 print -- big launches peak early and fade, small ones ramp up
through the day, and the line captures that -- and read it off at the
case's own hour-1 print (clamped to the donors' range, so an unprecedented
print cannot extrapolate wildly). The spread for the hour comes from the
donors' residual scatter around that line, floored so it never collapses.
Where donors are too few, the forecast falls back to persistence with a
wide spread. Everything is standard library only, deterministic, and fast.
"""

import json
import math
import os
import statistics
from datetime import datetime
from pathlib import Path

INPUT_DIR = Path(os.environ.get("MAKEFUN_INPUT_DIR", "/input"))
OUTPUT_DIR = Path(os.environ.get("MAKEFUN_OUTPUT_DIR", "/output"))

# The quantile levels the contest scores, in the order each row lists them.
LEVELS = [0.05, 0.25, 0.5, 0.75, 0.95]
# Standard normal quantiles at those levels.
Z = [-1.645, -0.674, 0.0, 0.674, 1.645]

# Donor rules: a comparable only shapes the curve when its hour-1 print is
# already a real audience, not a pre-unlock trickle.
MIN_DONOR_HOUR1 = 1000.0
MIN_DONOR_HOUR1_SHARE_OF_PEAK = 0.20
MIN_DONORS_FOR_FIT = 5

# Fit knobs, tuned on leave-one-out scoring over the comparables (see
# BUILD_NOTES.md): shrink the fitted log-ratio a little toward persistence,
# ridge the slope a little toward flat, and widen the residual spread a
# touch so the 90% band covers about nine hours in ten. The spread
# multiplier went from 1.0 to 1.1 after the first validation run: the
# leave-one-out loss was unchanged, but 90% coverage rose from 0.882 to
# 0.915 -- closer to the honest 0.90 -- and the big-launch loss improved
# slightly (0.2081 to 0.2072).
SHRINK = 0.9
RIDGE = 2.0
SIGMA_FLOOR = 0.25
SIGMA_CAP = 1.2
SIGMA_MULT = 1.1
FALLBACK_SIGMA = 0.6


def _parse_time(text):
    """An ISO 8601 timestamp into a datetime (handles the trailing Z)."""
    return datetime.fromisoformat(text.replace("Z", "+00:00"))


def _round2(value):
    """Round to 2 decimals, half up; whole numbers come back as ints."""
    scaled = value * 100.0
    whole = math.floor(scaled)
    if scaled - whole >= 0.5:
        whole += 1
    out = whole / 100.0
    return int(out) if out.is_integer() else out


def _donor_weight(comp):
    """How much a comparable's curve should count.

    Console-only launches are the closest analogues to a console-only,
    single-player release, so they count double; always-online and
    multiplayer-heavy launches count half. Anything else counts once.
    """
    platforms = (comp.get("platforms") or "").lower()
    weight = 2.0 if "pc" not in platforms else 1.0
    name = (comp.get("name") or "").lower()
    multiplayer = (
        "call of duty", "battlefield", "halo", "marvel rivals",
        "helldivers", "arc raiders", "marathon", "forza",
        "monster hunter", "diablo",
    )
    if any(tag in name for tag in multiplayer):
        weight *= 0.5
    return weight


def _release_day(comp):
    """A comparable's release-day hourly viewers, keyed by UTC hour 1..24.

    Points outside the release day are ignored; a missing or non-positive
    hour simply has no entry, so sparse histories stay usable.
    """
    day_start = _parse_time(comp["day_start"])
    hours = {}
    for point in comp.get("hourly") or []:
        viewers = point.get("viewers")
        if viewers is None or viewers <= 0:
            continue
        hour = int((_parse_time(point["from"]) - day_start).total_seconds() // 3600) + 1
        if 1 <= hour <= 24:
            hours[hour] = float(viewers)
    return hours


def _collect_donors(case):
    """The usable comparables: (curve, weight) pairs with a real hour 1."""
    donors = []
    for comp in case.get("comparables") or []:
        try:
            curve = _release_day(comp)
        except (KeyError, TypeError, ValueError):
            continue
        first = curve.get(1)
        if first is None or first < MIN_DONOR_HOUR1:
            continue
        if first < MIN_DONOR_HOUR1_SHARE_OF_PEAK * max(curve.values()):
            continue
        donors.append((curve, _donor_weight(comp)))
    return donors


def _fit_hour(donors, hour, log_p1):
    """Median log-ratio and log-spread for one forecast hour.

    Returns (median_log_ratio, sigma). With enough donors this is the
    weighted ridge fit of log(viewers_h / viewers_1) on log(viewers_1),
    read off at the case's own log hour-1 print; with only a few donors
    it is their (weighted) median log-ratio; with none, persistence.
    """
    points = []
    for curve, weight in donors:
        if hour in curve and 1 in curve:
            points.append((math.log(curve[1]), math.log(curve[hour] / curve[1]), weight))
    if not points:
        return 0.0, FALLBACK_SIGMA
    if len(points) < MIN_DONORS_FOR_FIT:
        ordered = sorted(p for _, p, _ in points)
        middle = ordered[len(ordered) // 2] if len(ordered) % 2 else 0.5 * (
            ordered[len(ordered) // 2 - 1] + ordered[len(ordered) // 2]
        )
        return middle, FALLBACK_SIGMA

    total_w = sum(w for _, _, w in points)
    mean_x = sum(w * x for x, _, w in points) / total_w
    mean_y = sum(w * y for _, y, w in points) / total_w
    sxx = sum(w * (x - mean_x) ** 2 for x, _, w in points)
    sxy = sum(w * (x - mean_x) * (y - mean_y) for x, y, w in points)
    slope = sxy / (sxx + RIDGE) if sxx > 1e-9 else 0.0
    intercept = mean_y - slope * mean_x

    # Read the fit off at the case's print, clamped to the donors' range.
    xs = [x for x, _, _ in points]
    at = min(max(log_p1, min(xs)), max(xs))
    median = (intercept + slope * at) * SHRINK

    residuals = [y - (intercept + slope * x) for x, y, _ in points]
    sigma = statistics.pstdev(residuals) if len(residuals) > 1 else FALLBACK_SIGMA
    sigma = max(SIGMA_FLOOR, min(SIGMA_CAP, sigma * SIGMA_MULT))
    return median, sigma


def _hour_quantiles(p1, median_log_ratio, sigma):
    """Five quantiles for one hour, clamped and non-decreasing."""
    quantiles = []
    for z in Z:
        value = p1 * math.exp(median_log_ratio + z * sigma)
        value = min(max(value, 1.0), 1e9)
        quantiles.append(_round2(value))
    for i in range(1, len(quantiles)):
        if quantiles[i] < quantiles[i - 1]:
            quantiles[i] = quantiles[i - 1]
    return quantiles


def forecast_case(case, name):
    """Forecast hours 2..24 of one case, as the output object."""
    first = next((k for k in case.get("known") or [] if k.get("hour") == 1), None)
    if first is not None and first.get("viewers"):
        p1 = max(1.0, float(first["viewers"]))
    else:
        # No hour-1 print: fall back to the latest hourly history point.
        history = case.get("history_hourly") or []
        p1 = max(1.0, float(history[-1]["viewers"])) if history else 1.0

    donors = _collect_donors(case)
    log_p1 = math.log(p1)
    rows = []
    for row in case.get("forecast") or []:
        hour = row["hour"]
        if hour == 1:
            continue
        median, sigma = _fit_hour(donors, hour, log_p1)
        rows.append({"hour": hour, "q": _hour_quantiles(p1, median, sigma)})
    rows.sort(key=lambda r: r["hour"])
    return {"hours": rows}


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for path in sorted(INPUT_DIR.glob("*.in")):
        case = json.loads(path.read_text(encoding="utf-8"))
        forecast = forecast_case(case, path.name)
        out_path = OUTPUT_DIR / f"{path.stem}.out"
        out_path.write_text(json.dumps(forecast, separators=(",", ":")) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
