# makefun-gta6-twitch-ccu-forecast-01

[![make.fun · gta6-twitch-ccu-forecast-01](https://make.fun/badge/gta6-twitch-ccu-forecast-01.svg)](https://make.fun/bounty/gta6-twitch-ccu-forecast-01?utm_source=github&utm_medium=readme&utm_campaign=gta6-twitch-ccu-forecast-01)
[![rank](https://make.fun/badge/gta6-twitch-ccu-forecast-01/yafiteesss/makefun-gta6-twitch-ccu-forecast-01/rank.svg)](https://make.fun/bounty/gta6-twitch-ccu-forecast-01/leaderboard?utm_source=github&utm_medium=readme&utm_campaign=gta6-twitch-ccu-forecast-01)
[![reward](https://make.fun/badge/gta6-twitch-ccu-forecast-01/yafiteesss/makefun-gta6-twitch-ccu-forecast-01/reward.svg)](https://make.fun/bounty/gta6-twitch-ccu-forecast-01?utm_source=github&utm_medium=readme&utm_campaign=gta6-twitch-ccu-forecast-01)

A Python program that forecasts Grand Theft Auto VI's launch-day Twitch
viewers hour by hour. It anchors on the case's hour-1 print and shapes the
day from the release-day curves of past big launches shipped with the case:
for each forecast hour it fits a weighted line through the comparables'
log-ratios (hourly viewers over their own hour-1 print) against their log
hour-1 print -- big launches peak early and fade, small ones ramp up
through the day -- reads it off at the case's own hour-1 print, and takes
the spread from the donors' residual scatter around that line. Only
launches whose hour-1 print is already substantial count as donors, so a
launch that unlocked late in the day cannot distort the curve. Python 3.13
standard library only, no network, deterministic.

## Run it

```sh
MAKEFUN_INPUT_DIR=input MAKEFUN_OUTPUT_DIR=out python3 main.py
```

That reads every `*.in` case in `input/` and writes one `<id>.out` forecast
per case to `out/`: 23 rows, hours 2 to 24, five quantiles each.

See [BUILD_NOTES.md](BUILD_NOTES.md) for the method and local validation
numbers.

---

Built for the [gta6-twitch-ccu-forecast-01 bounty on make.fun](https://make.fun/bounty/gta6-twitch-ccu-forecast-01?ref=tgs239he).
