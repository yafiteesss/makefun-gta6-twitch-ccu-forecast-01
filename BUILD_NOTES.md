# Build notes — gta6-twitch-ccu-forecast-01

## Method

The forecast is anchored on the case's hour-1 print `p1` and shaped by the
past big launches shipped with the case ("comparables"):

1. **Donors.** A comparable counts only if its release-day hour-1 print is
   already a real audience: at least 1,000 viewers and at least 20% of its
   own release-day peak. Launches that unlocked late in the day (hour 1
   near-empty, ratios exploding to 100x-2000x) are excluded. The Grand Theft
   Auto VI category's own pre-release history is skipped the same way (no
   release-day hours). Typically ~24-29 of the 38-42 comparables qualify.
2. **Shape.** For each forecast hour h = 2..24, a weighted ridge regression
   of `log(viewers_h / viewers_1)` on `log(viewers_1)` across the donors,
   read off at the case's own log hour-1 print (clamped to the donors'
   range, so an unprecedented print cannot extrapolate). Big launches peak
   early and fade; small ones ramp up through the day; the line captures
   that scale dependence. Console-only launches weigh 2x, multiplayer-heavy
   ones 0.5x. The fitted log-ratio is shrunk 10% toward persistence (0).
3. **Spread.** Per-hour sigma is the donors' residual standard deviation
   around the fit, x1.1, floored at 0.25 and capped at 1.2 in log units.
   Quantiles: `p1 * exp(median + z_tau * sigma)`, clamped to (0, 1e9] and
   non-decreasing, rounded half-up to 2 decimals.
4. **Fallbacks.** Too few donors for an hour -> their median log-ratio with
   a wide spread (0.6); no donors at all -> persistence with a wide spread.
   Hour-1 print below 1 counts as 1.

Single `main.py`, Python 3.13 standard library only, no network, no
randomness.

## Local validation

Scoring is mean pinball loss on the log scale (the contest's metric).
Leave-one-out over the comparables: each comparable becomes a pseudo-case
(its release-day hour-1 as the print, its hours 2-24 as the answer, donors
= the case's other comparables). The shipped `main.py` itself is imported
and scored, so these numbers describe the code as submitted, not a copy.

| | loss | typical miss | 90% coverage |
|---|---|---|---|
| This entry, all LOO targets (n=24) | **0.1966** | 38.8% | 0.915 |
| House baseline, same targets | 0.2652 | ~83% | ~0.76 |
| This entry, big launches p1 >= 100k (n=16) | **0.2072** | — | — |
| House baseline, big launches | 0.2611 | — | — |

For reference, the house baseline scores ~0.387 on the four practice cases
per the kit; the LOO baseline is lower (0.265) because the LOO targets are
the filtered, well-behaved launches. Either way this entry beats the
baseline by roughly 20-26% in loss on the same targets.

Practice cases (p00-p03): all 4 outputs valid shape (23 rows, hours 2-24,
five finite non-decreasing quantiles in (0, 1e9]), byte-identical across two
runs, ~0.06 s per case (limit 8 s).

## Improvement iteration

- **v1** (spread multiplier 1.0): LOO loss 0.1966 / big-launch 0.2081,
  90% coverage 0.882.
- **v2** (spread multiplier 1.1, the shipped version): LOO loss 0.1966 /
  big-launch 0.2072, 90% coverage 0.915 — coverage now close to the honest
  0.90 at no loss cost. Adopted.
- Tried and rejected on the same LOO: a second predictor (donor unlock
  hour) — loss worsened to 0.231; restricting donors to early-unlock
  launches — worsened to 0.228-0.240; clamping the fitted median to the
  plain donor median — no change; kernel-weighted median instead of the
  regression — 0.209; blending kernel + regression — 0.200.

## Known weaknesses

- The model only sees hour 1 and the comparables; it cannot use the final
  case's live `streams` / `categories_hourly` data, which are null in
  practice and untested.
- Idiosyncratic launches still miss badly (e.g. Monster Hunter Wilds LOO
  loss 0.49, Starfield 0.34 — both worse than baseline): a launch whose
  unlock or ramp timing differs from its scale-implied shape is not
  corrected by any feature the case carries at hour 1.
- Per-hour median log errors on big launches are small (mostly within
  +/-0.1) except hours 10-11, where the forecast median runs ~0.2 log
  units high (the midday dip is deeper than the fit expects).
- GTA VI's hour-1 print will likely exceed every donor's (max 875k); the
  fit is clamped to the donors' range, so the shape used is that of the
  largest donors — a reasonable but untested extrapolation.
- Practice-case answers are not in the kit, so the four practice cases
  could only be checked for validity/determinism/runtime, not scored.
