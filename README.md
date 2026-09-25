# NAVI

A personal Navi: one persistent digital being that lives with you across your phone, watch and computer.
It knows you, grows with you, helps you, and is on your side. Inspired by the Operator ↔ NetNavi bond from *Mega Man Battle Network*.

> **One Navi. One identity. Everywhere. Growing together.**

## Contents

| Path | What |
|---|---|
| [`mockups/index.html`](mockups/index.html) | First UI mockups (open in a browser) |
| [`docs/01-senses-and-brain.md`](docs/01-senses-and-brain.md) | How the Navi knows things: senses per platform, perception filter, AI engine (Hebrew) |

## Status

Planning. Product Bible (topics 1–15) closed; next step is the first Android vertical slice.

## Run Navi Space (3D + brain + voice)

```bash
pip install edge-tts          # free Hebrew neural voice (he-IL-AvriNeural)
node brain/server.mjs         # → http://localhost:8765/preview/
```

- Brain: Claude API (`claude-opus-5`) when `ANTHROPIC_API_KEY` is set, otherwise Codex CLI on your ChatGPT account.
- Voice tuning: `NAVI_VOICE`, `NAVI_VOICE_PITCH` (default `+35Hz`), `NAVI_VOICE_RATE` (default `+8%`).
- Mic uses the browser's speech recognition (`he-IL`) — works in Chrome.
