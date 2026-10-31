"""Opt-in actual Meta caption test via the local authenticated WebSocket relay.

Captions have no synthetic path: the relay accepts only a profile whose person granted microphone_local and
meta_voice (care.consent) on a local server in real-data mode. Use a local test person and a WAV of synthetic
speech; set AINGEL_SMOKE_PROFILE to that profile id.
"""

import asyncio
import json
import os
from pathlib import Path
import wave

import httpx
from websockets.asyncio.client import connect


async def main():
    project = Path(__file__).resolve().parents[2]
    account = json.loads((project / ".local" / "demo-accounts.json").read_text())[
        "accounts"
    ][0]
    with httpx.Client(base_url="http://127.0.0.1:8010") as client:
        csrf = client.get("/api/v1/auth/session/").json()["csrf"]
        response = client.post(
            "/api/v1/auth/login/", json=account, headers={"X-CSRFToken": csrf}
        )
        if response.status_code != 200 or response.json().get("mfa_required"):
            raise RuntimeError(
                "Synthetic account requires an available session without a pending MFA challenge"
            )
        cookie = f"sessionid={client.cookies['sessionid']}"
    del account
    final = []
    partials = 0
    with wave.open(str(project / ".local" / "caption-fixture.wav"), "rb") as audio:
        if (audio.getframerate(), audio.getnchannels(), audio.getsampwidth()) != (
            24000,
            1,
            2,
        ):
            raise RuntimeError("Expected mono 24kHz PCM16 synthetic WAV")
        seconds = audio.getnframes() / 24000
        async with connect(
            "ws://127.0.0.1:8010/ws/captions/",
            origin="http://127.0.0.1:5173",
            additional_headers={"Cookie": cookie},
            open_timeout=10,
        ) as ws:
            await ws.send(
                json.dumps({"type": "start", "locale": "en-US", "profile": os.environ["AINGEL_SMOKE_PROFILE"]})
            )
            ack = json.loads(await asyncio.wait_for(ws.recv(), 30))
            if ack.get("type") != "ready":
                raise RuntimeError("Caption relay rejected the session")

            async def receive():
                nonlocal partials
                async for raw in ws:
                    event = json.loads(raw)
                    if event.get("type") == "error":
                        raise RuntimeError("Caption relay error")
                    if event.get("type") == "transcript":
                        partials += 1
                    if event.get("type") == "speechComplete":
                        final.append(event.get("transcript", ""))

            receiver = asyncio.create_task(receive())
            while frame := audio.readframes(1920):
                await ws.send(frame)
                await asyncio.sleep(len(frame) / 48000)
            await ws.send(json.dumps({"type": "stop"}))
            await asyncio.wait_for(receiver, 30)
    result = {
        "fixture": "OS-synthesized English speech, original test script; no microphone or personal audio",
        "expected_script": "This is a synthetic test. The blue square is on the left.",
        "transport": "Django session -> local WebSocket relay -> actual Meta Voice Transcribe",
        "model": "muse-voice-transcribe-1.0",
        "audio_seconds": round(seconds, 3),
        "partial_events": partials,
        "completed_turns": final,
        "success": bool(final),
    }
    (project / "docs" / "CAPTIONS_SMOKE_RESULT.json").write_text(
        json.dumps(result, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(result))
    return 0 if final else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
