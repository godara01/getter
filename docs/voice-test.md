# Voice test

The phase 0 voice test decides two things: whether to keep LiveKit, and which speech-to-text
and text-to-speech vendors to use. It needs a real five minute spoken call with real vendor
accounts, so it cannot be run from the repo alone. This kit does the parts that can be built
ahead: a way to join a room and a scorecard that turns the measurements into a verdict.

## What you need from Sanket

- A LiveKit Cloud project (the free tier is enough) with its URL, API key and API secret.
- Accounts and API keys for the speech vendors to compare (for example Deepgram for
  speech-to-text, Cartesia or ElevenLabs for text-to-speech) and one model provider.
- Add them as environment secrets. Never paste them into chat.

## Run the call

1. Set `GETTER_LIVEKIT_URL`, `GETTER_LIVEKIT_API_KEY` and `GETTER_LIVEKIT_API_SECRET` on the
   API. As an admin, `POST /admin/voice/token` returns `{url, room, identity, token}`: a
   15 minute token that lets one participant join one room.
2. Start a LiveKit Agents voice agent in that room with the interviewer prompt and one vendor
   combination (STT, model, TTS). Have a spoken conversation for five minutes, answering
   like a candidate: some short replies, some long ones.
3. From the agent's metrics, note for every reply the milliseconds spent in each stage:
   waiting to be sure you stopped speaking (`endpointing_ms`), the final transcript
   (`stt_ms`), the model's first token (`llm_first_token_ms`), the first audio from text to
   speech (`tts_first_audio_ms`), and network round trips (`network_ms`). Leave out a stage
   you could not measure; it counts as zero.
4. Note the totals for the call: audio minutes sent to STT, model input and output tokens,
   and characters sent to TTS.
5. Write them with the vendors' current list prices as one JSON file per setup. The format
   is in [voice-test/example-measurement.json](voice-test/example-measurement.json). That
   file is an illustration, not a real call.

## Read the result

```
cd services/api
uv run python -m getter_api.voice setup-a.json setup-b.json
```

The table shows, for each setup, the median and 95th percentile delay between the candidate
finishing and the reply starting, the cost per minute and the projected cost of a 40 minute
interview, the slowest stage and the cost split, and pass or fail.

The thresholds are proposals, to be changed by Sanket with `--p50-ms`, `--p95-ms` and
`--max-inr-per-minute`:

| Measure | Proposed limit | Why |
| --- | --- | --- |
| Median delay | 1.5 seconds | Longer feels like a bad phone line |
| 95th percentile delay | 3 seconds | An occasional slow reply is tolerable |
| Cost | INR 10 a minute (about INR 400 for 40 minutes) | The top of the voice range in the [technical plan](technical-plan.md) |

Decision rule: keep LiveKit if at least one setup passes. If none does, the usual fixes are a
faster first-token model for live turns, a cheaper text-to-speech vendor, or interviews that
are text-first with voice later. Record the outcome in
[goals-and-decisions.md](goals-and-decisions.md).
