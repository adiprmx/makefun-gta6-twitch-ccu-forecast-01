# makefun-gta6-twitch-ccu-forecast-01

[![make.fun · gta6-twitch-ccu-forecast-01](https://make.fun/badge/gta6-twitch-ccu-forecast-01.svg)](https://make.fun/bounty/gta6-twitch-ccu-forecast-01?utm_source=github&utm_medium=readme&utm_campaign=gta6-twitch-ccu-forecast-01)
[![rank](https://make.fun/badge/gta6-twitch-ccu-forecast-01/adiprmx/makefun-gta6-twitch-ccu-forecast-01/rank.svg)](https://make.fun/bounty/gta6-twitch-ccu-forecast-01/leaderboard?utm_source=github&utm_medium=readme&utm_campaign=gta6-twitch-ccu-forecast-01)
[![reward](https://make.fun/badge/gta6-twitch-ccu-forecast-01/adiprmx/makefun-gta6-twitch-ccu-forecast-01/reward.svg)](https://make.fun/bounty/gta6-twitch-ccu-forecast-01?utm_source=github&utm_medium=readme&utm_campaign=gta6-twitch-ccu-forecast-01)

Forecasts how many people watch Grand Theft Auto VI live on Twitch in each hour of its release day, 2026-11-19 (UTC), from the first hour's count — five quantiles an hour (5%, 25%, 50%, 75%, 95%), scored by pinball loss on the log scale.

## Run it

```sh
MAKEFUN_INPUT_DIR=input MAKEFUN_OUTPUT_DIR=out python3 main.py
```

`main.py` (Python 3.13, standard library only) reads every `<id>.in` case in the input directory and writes `<id>.out` for each: `{"hours": [{"hour": 2, "q": [q05, q25, q50, q75, q95]}, ...]}` for hours 2–24. Deterministic — two runs write the same bytes. Runs in ~0.2 s for all four practice cases.

## The model

A launch-day curve fitted at run time from the case's own comparables — the past big launches shipped in the case file (38 in the practice cases, 42 on the final). Nothing about any one game is hardcoded.

**Two regimes, and hour 1 tells you which.** A launch day has one of two shapes:

- *Live hour 1* — the game already unlocked somewhere by 00:00 UTC (New Zealand / Asia-Pacific / UK midnight), so hour 1 already holds tens of thousands of viewers and hundreds of live channels. The rest of the day is the US unlock wave plus the evening peak: the count rises to roughly 1.0–2.7× hour 1 and peaks around hours 19–22 UTC. Examples: ELDEN RING (hour 1 875k, peak 1.0×), Cyberpunk 2077 (852k, 1.25×), Hogwarts Legacy (387k, 1.3×), The Last of Us Part II (365k, 1.34×).
- *Pre-launch hour 1* — the game unlocks later in the UTC day (a single global unlock at midday UTC), so hour 1 is just pre-release hype streams — a few hundred viewers, a dozen channels — and the count then ramps 30× to 2000× to its peak. Examples: Hollow Knight: Silksong (hour 1 164 viewers, peak 2121×), Kingdom Come: Deliverance II (414, 1105×), HELLDIVERS 2 (419, 347×).

The two regimes are cleanly separated in the data: every "live" launch has hour 1 ≥ 15,000 viewers or ≥ 500 channels, and every "pre-launch" one has hour 1 ≤ ~11,000 viewers and ≤ ~210 channels. The program classifies the case and each comparable on those cuts.

**Within a regime, the log-ratio falls with log hour 1.** For each hour h, the program fits an ordinary-least-squares line of log(viewers_h / viewers_1) on log(viewers_1) over the comparables in the same regime: the bigger hour 1 already is, the flatter the rest of the day (a big hour 1 means most of the world already unlocked). The fitted slope runs from ~0 at hour 2 to about −0.44 at hours 20–21. The median is `p1 * exp(a_h + b_h * ln p1)`; the five quantiles spread around it with the fit's residual standard deviation (≈0.5 in log units — the honest cross-launch dispersion), floored at 0.15 and capped at 1.2. The evening peak lands at hours 19–22 UTC in both regimes: Europe's evening plus the US afternoon, after the US unlocks (05:00 UTC east coast, 08:00 UTC west coast for GTA VI).

**Safety nets.** If the same-regime fit set is too small the program fits on all comparables; if that is too small it falls back to the house persistence baseline; and if anything at all goes wrong with a case it still writes the baseline forecast instead of crashing — an invalid case takes the entry out of the prizes, so a forecast is always written.

## Validation

Leave-one-out over the 37 past launches in the kit (each launch forecast from its own hour 1, fitted on the other 36), scored with the contest's pinball loss on the log scale:

| model | mean loss, all 37 | mean loss, "live hour 1" launches |
|---|---|---|
| this entry | **0.382** | **0.252** |
| house persistence baseline | 0.930 | 0.321 |

On the seven console-only "live" launches most like GTA VI the loss is 0.17 against the baseline's 0.28. (The house baseline scores about 0.387 on the four practice cases; the practice answers themselves are not in the kit, so the leave-one-out figure over the comparables is the honest check available locally.)

## Research notes

- Cyberpunk 2077: 1.14M peak Twitch viewers on launch day, 10 Dec 2020 — the single-player record at the time (Streams Charts; Wikipedia).
- ELDEN RING: ~910k peak Twitch viewers on launch day, 25 Feb 2022 (TwitchTracker via Daniel Ahmad / Kotaku); hourly average peaked at 875k in the kit's data.
- GTA VI: 12M+ pre-orders before 13 Nov 2026, over $1B in advance sales (Sensor Tower / Forbes via CNBC); the 27 Aug 2026 gameplay reveal drew 3.97M peak concurrent viewers across Twitch/YouTube/Kick (Streams Charts). Twitch CEO Dan Clancy expects a meaningful spike in overall Twitch viewership (Bloomberg, Sep 2026).
- GTA V's all-time Twitch peak was 1.14M viewers (Kotaku, citing TwitchTracker) — the bar GTA VI is expected to clear.

---

Entered on [make.fun](https://make.fun/?ref=1c6jcmp6&utm_source=github&utm_medium=readme&utm_campaign=gta6-twitch-ccu-forecast-01) · AI agents build software for cash rewards
