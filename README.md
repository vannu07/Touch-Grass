# Last Light

A twenty-minute walk for the last light of the day.

You tell it where the door is and what the sky looks like. It answers with a ticket: **leave by 17:42, walk west, four things to do with your eyes and hands, phone in a pocket that is not your hand.** Then the screen goes dark on purpose.

This is a submission for [Hacktoberfest Open-Source AI Challenge: Week 1 — Touch Grass](https://dev.to/challenges/hacktoberfest-week1-2026-10-05).

## Why this, and not another bird app

The trail this week is already full of offline bird identifiers and frost-date garden planners. Those are good ideas. They also keep you looking at a phone.

Last Light is the other direction. The model work happens **before you leave**. The artefact is a stub you can print. Pocket mode is a countdown and a heading. There is no chat. There is no species list. If you cannot name the bird, that is the point.

## What it does

1. Computes **sunset, golden hour, and the sun's azimuth** from latitude and longitude. No weather API, no map tiles.
2. Scores whether tonight is worth going with **TabPFN** (Prior Labs), trained on 1,400 synthetic dusk-walk rows whose hidden recipe is temperature, rain, wind, minutes-to-sunset, and foliage season. A ridge regression sits next to it as a check. The page shows both MAEs.
3. Writes the ticket copy with **Gemma** when Ollama, Groq, or Google's Gemma endpoint is available. If none of those are up, the **field recipes** write the ticket themselves. They are not a broken fallback. They are the offline voice of the product.
4. Optionally reads the ticket aloud (ElevenLabs if a key is present, otherwise the browser's own voice) so the phone can go away.

Location is used once, to issue the ticket. Field notes stay in `localStorage`.

## Run it

Python 3.11+ (3.12 is what the Dockerfile uses).

```bash
python -m pip install -r requirements.txt
python -m pytest
python -m uvicorn lastlight.app:app --reload --port 8765
```

Open [http://127.0.0.1:8765](http://127.0.0.1:8765).

The first TabPFN fit downloads weights and can take a minute on CPU. `/api/health` reports `engine: loading` until that finishes. Tickets still issue; they wait on the fit.

### Optional Gemma

```bash
ollama pull gemma3:4b
# then, in .env or the shell:
set OLLAMA_MODEL=gemma3:4b
```

Without Ollama, copy still works. The ticket footer will say `field recipes · offline`.

### Optional voice

Set `ELEVENLABS_API_KEY`. If it is missing, **Read it aloud** uses the browser.

## Tests that do not need a model

```bash
python -m pytest -q
```

Sun times for Delhi in October, dataset shape, and the hidden rainfall penalty. The TabPFN backtest runs when the server starts and is printed in the log:

```
[lastlight] go-engine tabpfn  tabpfn_mae=… ridge_mae=… mean_mae=… n_test=…
```

## Deploy

`render.yaml` is a Blueprint for a Python web service. `Dockerfile` is the same app on 3.12-slim. You do not need a GPU.

## What this is not

- Not a chatbot.
- Not a trail map.
- Not medical or safety advice. If it is actually dark and the street is not yours to walk, do not go.
- The climate table is generated from a physical recipe so TabPFN can be scored against a known process. It is not NOAA station data.

## Licence

MIT. See `LICENSE`.
