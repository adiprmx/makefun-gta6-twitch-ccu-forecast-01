"""Forecast GTA VI's launch-day Twitch viewers hour by hour (program/v1).

The model: a launch-day curve fitted at run time from the case's own
comparables, the past big launches shipped in the case file.

What the data says (38 past launches, SullyGnome hourly Twitch category
averages, analysed in the build session; see README for the numbers):
  * A launch day has one of two shapes, and hour 1 tells you which.
    - "Live hour 1": the game already unlocked somewhere by 00:00 UTC
      (New Zealand / Asia-Pacific / UK midnight), so hour 1 already holds
      tens of thousands of viewers and hundreds of live channels. The rest
      of the day is the US unlock wave plus the evening peak: the count
      rises to roughly 1.0-2.7x hour 1 and peaks around hours 19-22 UTC.
      Examples: ELDEN RING (hour 1 875k, peak 1.0x), Cyberpunk 2077
      (852k, 1.25x), God of War Ragnarok (270k), Hogwarts Legacy (387k,
      1.3x), The Last of Us Part II (365k, 1.34x).
    - "Pre-launch hour 1": the game unlocks later in the UTC day
      (a single global unlock at midday UTC), so hour 1 is just pre-release
      hype streams -- a few hundred viewers, a dozen channels -- and the
      count then ramps 30x to 2000x to its peak. Examples: Hollow Knight:
      Silksong (hour 1 164 viewers, peak 2121x), Kingdom Come:
      Deliverance II (414, 1105x), HELLDIVERS 2 (419, 347x).
    The two regimes are cleanly separated in the data: every "live"
    launch has hour 1 >= 15,000 viewers or >= 500 channels, and every
    "pre-launch" one has hour 1 <= ~11,000 viewers and <= ~210 channels.
  * Within a regime, the log-ratio log(viewers_h / viewers_1) falls
    almost linearly with log(viewers_1): the bigger hour 1 already is,
    the flatter the rest of the day (a big hour 1 means most of the world
    already unlocked). The fitted slope runs from ~0 at hour 2 to about
    -0.44 at hours 20-21. The residual spread around that line is about
    0.5 in log units -- that is the honest cross-launch dispersion, and
    it sets the quantile spread.
  * The evening peak lands at hours 19-22 UTC in both regimes: Europe's
    evening plus the US afternoon, after the US unlocks (05:00 UTC east
    coast, 08:00 UTC west coast for GTA VI).

The forecast, for each hour h = 2..24:
  median  = p1 * exp(a_h + b_h * ln p1)
  q_tau   = median * exp(z_tau * sd_h)
where p1 is hour 1's print, a_h and b_h are the ordinary-least-squares
fit of log(viewers_h / viewers_1) on log(viewers_1) over the comparables
in the same regime as this case, sd_h is the residual standard
deviation of that fit (floored at 0.15, capped at 1.2), and z_tau is the
standard normal's quantile at each scored level. Nothing is hardcoded
about any one game: the fit is recomputed from the comparables in
whatever case the grader hands the program, so the four practice
launches join the fit set on the final case. If the fit set is too
small the program falls back to the house persistence baseline, and if
anything at all goes wrong with a case it still writes that baseline
rather than crashing -- an invalid case takes the entry out of the
prizes, so a forecast is always written.

Leave-one-out check over the 37 past launches in the kit (each launch
forecast from its own hour 1, fitted on the other 36): mean pinball
loss 0.38 overall and 0.25 on the "live hour 1" launches -- the regime
GTA VI and all four practice launches are in -- against 0.93 / 0.32
for the house persistence baseline on the same launches. On the seven
console-only "live" launches most like GTA VI the loss is 0.17
against the baseline's 0.28.

Standard library only, deterministic (no randomness, no wall clock,
no network): two runs on the same case write the same bytes.
"""

import json
import math
import os
import sys
from datetime import datetime
from pathlib import Path

# The grader's -P leaves /bot off sys.path: put it back first, so a
# module shipped beside this file would import. (This entry is one file.)
sys.path.insert(0, str(Path(__file__).resolve().parent))

INPUT_DIR = Path(os.environ.get("MAKEFUN_INPUT_DIR", "/input"))
OUTPUT_DIR = Path(os.environ.get("MAKEFUN_OUTPUT_DIR", "/output"))

# The quantile levels the contest scores, in the order each row lists them.
LEVELS = [0.05, 0.25, 0.5, 0.75, 0.95]
# The standard normal's quantile at each level.
Z = [-1.645, -0.674, 0, 0.674, 1.645]

# "Live hour 1" cut: a launch whose first hour already holds this many
# viewers, or this many live channels, has unlocked somewhere by 00:00
# UTC. The gap in the 38 comparables is wide (pre-launch launches top
# out at ~11,000 viewers / ~210 channels; live ones start at ~20,000
# viewers / ~600 channels), so either signal on its own separates them.
LIVE_VIEWERS = 15000
LIVE_CHANNELS = 500
# A regime fit needs at least this many launches; below it, fit on all
# comparables instead, and below 3, fall back to persistence.
MIN_FIT_CURVES = 5
MIN_CURVES_ANY = 3
# The quantile spread in log units: the residual spread of the fit,
# kept inside these bounds.
SIGMA_FLOOR = 0.15
SIGMA_CAP = 1.2
# The house baseline's spread, used only by the fallback.
BASELINE_SIGMA = 0.15


def round2(x: float) -> float | int:
    """x rounded to 2 decimals, half up, as JavaScript's Math.round(x * 100) / 100 rounds it.

    A whole number comes back as an int, so json.dumps writes 1240 where JavaScript writes 1240 (not 1240.0).
    """
    scaled = x * 100
    whole = math.floor(scaled)
    if scaled - whole >= 0.5:
        whole += 1
    value = whole / 100
    return int(value) if value.is_integer() else value


def parse_ts(text):
    """An ISO 8601 UTC timestamp into a naive datetime (all inputs are UTC)."""
    return datetime.fromisoformat(str(text).replace("Z", "+00:00"))


def is_live(h1_viewers, h1_channels):
    """True when hour 1 was already a live launch hour (see module docstring)."""
    if h1_viewers is not None and h1_viewers >= LIVE_VIEWERS:
        return True
    return h1_channels is not None and h1_channels >= LIVE_CHANNELS


def extract_curve(comp):
    """A comparable's release-day curve: (hour-1 viewers, hour-1 channels, {hour: viewers}).

    Returns None when the comparable has no usable hour-1 point (its
    release day is not in the data yet -- the GTA VI category's own
    pre-release history, for example).
    """
    try:
        day_start = parse_ts(comp["day_start"])
    except (KeyError, TypeError, ValueError):
        return None
    hours = {}
    h1_channels = None
    for row in comp.get("hourly") or []:
        try:
            when = parse_ts(row["from"])
            viewers = row["viewers"]
        except (KeyError, TypeError, ValueError):
            continue
        delta_h = (when - day_start).total_seconds() / 3600.0
        hour = int(delta_h) + 1
        if not 1 <= hour <= 24:
            continue
        if isinstance(viewers, (int, float)) and viewers > 0:
            hours[hour] = float(viewers)
        if hour == 1 and row.get("channels") is not None:
            h1_channels = row["channels"]
    if 1 not in hours or len(hours) < 10:
        return None
    return hours[1], h1_channels, hours


def pstdev(values):
    """Population standard deviation (the fit's residual spread)."""
    n = len(values)
    if n < 2:
        return 0.5
    mean = sum(values) / n
    return math.sqrt(sum((v - mean) ** 2 for v in values) / n)


def fit_regression(curves):
    """Per hour, OLS of log(viewers_h / viewers_1) on log(viewers_1).

    Returns {hour: (intercept, slope, residual_sd)}. A launch that
    lacks hour h simply does not vote at that hour.
    """
    fit = {}
    for hour in range(2, 25):
        xs, ys = [], []
        for curve in curves:
            if 1 in curve and hour in curve:
                xs.append(math.log(curve[1]))
                ys.append(math.log(curve[hour] / curve[1]))
        if len(xs) < 3:
            # Too few votes at this hour: flat median, wide spread.
            ratios = ys if ys else [0.0]
            ratios.sort()
            fit[hour] = (ratios[len(ratios) // 2], 0.0, 0.5)
            continue
        n = len(xs)
        mx = sum(xs) / n
        my = sum(ys) / n
        sxx = sum((x - mx) ** 2 for x in xs)
        slope = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sxx if sxx > 0 else 0.0
        intercept = my - slope * mx
        resid = [y - (intercept + slope * x) for x, y in zip(xs, ys)]
        fit[hour] = (intercept, slope, pstdev(resid))
    return fit


def anchor(case):
    """Hour 1's print (viewers, channels) for the case being forecast.

    Falls back to the last history point, then to 1 viewer, so a case
    with a thin hour 1 still gets a forecast instead of an error.
    """
    for row in case.get("known") or []:
        if row.get("hour") == 1 and row.get("viewers") is not None:
            return max(1.0, float(row["viewers"])), row.get("channels")
    for key in ("history_hourly", "history"):
        points = case.get(key) or []
        if points:
            last = points[-1]
            if last.get("viewers"):
                return max(1.0, float(last["viewers"])), last.get("channels")
    return 1.0, None


def persistence_quantiles(p1, hour):
    """The house baseline: every hour stays at hour 1's print, spread widening like a random walk."""
    return [round2(p1 * math.exp(z * BASELINE_SIGMA * math.sqrt(hour - 1))) for z in Z]


def clamp_quantiles(values):
    """Keep five quantiles valid: finite, above 0, at most 1e9, non-decreasing."""
    out = []
    prev = 0.01
    for value in values:
        if not math.isfinite(value):
            value = prev
        value = min(max(float(value), 0.01), 1_000_000_000.0)
        if value < prev:
            value = prev
        out.append(round2(value))
        prev = float(out[-1])
    return out


def forecast_case(case, name):
    """The forecast for one case: {"hours": [{"hour": h, "q": [...]}, ...]}."""
    p1, ch1 = anchor(case)
    if case.get("levels") != LEVELS:
        raise ValueError(f"{name} asks for levels {case.get('levels')}, not {LEVELS}")

    curves = []
    for comp in case.get("comparables") or []:
        got = extract_curve(comp)
        if got is not None:
            curves.append(got)

    target_live = is_live(p1, ch1)
    same_regime = [curve for (_h1, _ch, curve) in curves if is_live(_h1, _ch) == target_live]
    use = same_regime if len(same_regime) >= MIN_FIT_CURVES else [c[2] for c in curves]
    use = [c for c in use if c]

    hours = []
    if len(use) >= MIN_CURVES_ANY:
        fit = fit_regression(use)
        log_p1 = math.log(p1)
        for row in case["forecast"]:
            hour = row["hour"]
            intercept, slope, sd = fit[hour]
            center = intercept + slope * log_p1
            sd = min(max(sd, SIGMA_FLOOR), SIGMA_CAP)
            quantiles = [p1 * math.exp(center + z * sd) for z in Z]
            hours.append({"hour": hour, "q": clamp_quantiles(quantiles)})
    else:
        for row in case["forecast"]:
            hour = row["hour"]
            hours.append({"hour": hour, "q": clamp_quantiles(persistence_quantiles(p1, hour))})
    hours.sort(key=lambda row: row["hour"])
    return {"hours": hours}


def forecast_case_safe(case, name):
    """A forecast for one case that never raises: on any failure the
    persistence baseline is written instead of nothing. An invalid
    case (missing output, crash) takes the entry out of the prizes, so
    a forecast is always better than an exception."""
    try:
        return forecast_case(case, name)
    except Exception:
        try:
            p1, _ = anchor(case)
        except Exception:
            p1 = 1.0
        hours = []
        for row in case.get("forecast") or [{"hour": h} for h in range(2, 25)]:
            hour = row["hour"]
            hours.append({"hour": hour, "q": clamp_quantiles(persistence_quantiles(p1, hour))})
        hours.sort(key=lambda row: row["hour"])
        return {"hours": hours}


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    # Every case file, in name order, so two runs write the same bytes.
    for path in sorted(INPUT_DIR.glob("*.in")):
        case = json.loads(path.read_text(encoding="utf-8"))
        forecast = forecast_case_safe(case, path.name)
        (OUTPUT_DIR / f"{path.stem}.out").write_text(
            json.dumps(forecast, separators=(",", ":")) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
