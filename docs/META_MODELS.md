# Meta model audit — 2026-10-26

Official documentation inspected in Edge: [overview](https://dev.meta.ai/docs/overview), [models](https://dev.meta.ai/docs/models), [pricing](https://dev.meta.ai/docs/pricing-rate-limits), [images](https://dev.meta.ai/docs/image-understanding), [segmentation](https://dev.meta.ai/docs/media-segmentation), [speech](https://dev.meta.ai/docs/speech-to-text).

## Verified catalog and proposed use

| Component | Exact ID / surface | Input → output | AINGEL decision |
|---|---|---|---|
| Spark | `muse-spark-1.3` | text/image/video/PDF; audio caveat → text | P0 scene reasoning and bounded tools. Send voice through STT; raw audio understanding is degraded on 1.3. |
| Wonder | `muse-wonder-1.0` (preview) | multimodal → text | Optional evaluation only; justify cost/latency before adopting. |
| Voice | `muse-voice-transcribe-1.0` | audio → transcript | P0 live captions; never speech synthesis. |
| SAM | `sam-3.1` | noun phrase + image/video → boxes/masks | P0 object grounding. Special-token output needs official parsing guidance; do not assume JSON boxes. |
| Image | `muse-image-1.0` | text/image → image | P2 routine cards only. |
| Glimmer | self-hosted family; exact checkpoint selection pending | text/image → text | Halo research. No hosted API ID; hardware feasibility unmeasured. |
| Muse Code | developer CLI, not a runtime model ID | coding workflow | Optional development tool; not installed or claimed as used. |

Spark and Wonder context: 1,048,576 tokens. All hosted calls use `https://api.meta.ai/v1`; reasoning/segmentation use `/responses`; image generation/editing use `/images/generations` and `/images/edits`. Voice uses `/asr/transcribe` or `wss://api.meta.ai/v1/asr/realtime`.

## Prices and team limits

USD, observed date above; not a spending authorization. Spark Standard per million input/cached/output tokens: 1.25 / 0.15 / 4.25. Wonder: 4 / 0.20 / 20. Voice: 0.18/hour. Image: 0.01/image. SAM: 2.50/1,000 images; 0.20/1,000 video frames, minimum 50 billed frames/clip. Standard Spark/Wonder/SAM: 3,000 RPM; Spark/Wonder 4M TPM. Image 150 RPM. Voice 256 concurrent / 16,000 starts per hour. Actual account limits still need a real API response.

## Privacy and availability

Standard model IDs avoid Contributor training consent according to the pricing docs. Contributor IDs explicitly opt into content use for training. **Account billing separately warns that free-credit content may improve products.** Do not treat Standard selection as sufficient clearance for personal content while those credits are active. Initial live tests: synthetic/non-sensitive inputs only. Retention and geographic policy still require dedicated review; no ZDR promise is made.

## Wire contracts verified

For a scene request, send a user message with `input_text` plus `input_image.image_url` containing an inline data URL to `/responses`. Supported image upload formats include JPEG/PNG/WebP; upstream inline cap is 50 MB and 50 images/request. AINGEL will deliberately cap a request at one 5 MiB image, re-encode and strip metadata.

Voice WebSocket authorization belongs in the first JSON handshake (`authorization.accessToken`), not an HTTP header. Stream mono signed PCM16 at 16/24 kHz in real time; partial text replaces previous partials. `speechComplete` finalizes turns in ENDPOINTING mode. Files require PCM WAV, max 32 MB / 10 minutes. Sessions max 60 minutes. No word timestamps, confidence, sound alarms or emotion detection.

Language claims and device TTS are tracked in [LOCALIZATION.md](LOCALIZATION.md). Spark per-language quality is not yet benchmarked.

## Minimal request shape (not a recorded successful call)

```python
# Server only. HTTP client posts to https://api.meta.ai/v1/responses.
payload = {
    "model": "muse-spark-1.3",
    "input": [{"role": "user", "content": [
        {"type": "input_text", "text": "Describe visible objects briefly in Spanish."},
        {"type": "input_image", "image_url": "data:image/png;base64,<synthetic-image>"},
    ]}],
}
```

Official SDK examples support OpenAI-compatible clients configured to Meta's base URL. Compatibility is not OpenAI inference. We will start with direct HTTP to keep provider boundaries explicit. No API key has been created, retrieved or placed in this repository.
