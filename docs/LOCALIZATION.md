# Localization audit — 2026-10-26

[Official Voice language list](https://dev.meta.ai/docs/speech-to-text) verifies the STT column only. [Android TTS](https://developer.android.com/reference/android/speech/tts/TextToSpeech) requires checking `isLanguageAvailable(Locale)` and the installed engine/voice. No universal device voice promise is possible. Spark multilingual competence must be evaluated per task; no inspected source guarantees every target language.

This is a capability plan, not a shipping support list. The local React UI now has centralized English and Spanish resources; this is not a claim of native Android localization. `Planned` is not `UI ONLY`; `FULL` requires reviewed UI, measured AI and device verification. Status remains EXPERIMENTAL until implementation/evaluation. The three excluded STT languages are UNSUPPORTED for that capability, not for the entire future product.

| Language | Locale | UI | Spark | Voice documented | Android TTS | RTL | Sign support | Overall now |
|---|---|---|---|---|---|---|---|---|
| English | en-US | implemented locally | quality unmeasured | yes; one synthetic relay test passed | Android pending; browser voice varies | no | none | PARTIAL |
| Spanish | es-EC | implemented locally | synthetic scene test passed only | yes; not benchmarked | Android pending; browser voice varies | no | LSEC research only | PARTIAL |
| Portuguese | pt-BR, pt-PT | planned | unmeasured | yes | device check | no | none | EXPERIMENTAL |
| Mandarin | zh-CN | planned | unmeasured | yes | device check | no | none | EXPERIMENTAL |
| Korean | ko-KR | planned | unmeasured | yes | device check | no | none | EXPERIMENTAL |
| Japanese | ja-JP | planned | unmeasured | yes | device check | no | none | EXPERIMENTAL |
| Thai | th-TH | planned | unmeasured | yes | device check | no | none | EXPERIMENTAL |
| Indonesian | id-ID | planned | unmeasured | yes | device check | no | none | EXPERIMENTAL |
| Russian | ru-RU | planned | unmeasured | UNSUPPORTED | device check | no | none | EXPERIMENTAL |
| French | fr-FR | planned | unmeasured | yes | device check | no | none | EXPERIMENTAL |
| German | de-DE | planned | unmeasured | yes | device check | no | none | EXPERIMENTAL |
| Italian | it-IT | planned | unmeasured | yes | device check | no | none | EXPERIMENTAL |
| Arabic | ar | planned | unmeasured | yes | device check | yes | none | EXPERIMENTAL |
| Haitian Creole | ht-HT | planned | unmeasured | UNSUPPORTED | device check | no | none | EXPERIMENTAL |
| Ukrainian | uk-UA | planned | unmeasured | UNSUPPORTED | device check | no | none | EXPERIMENTAL |
| Hebrew | he-IL | planned | unmeasured | yes | device check | yes | none | EXPERIMENTAL |
| Hindi | hi-IN | planned | unmeasured | yes | device check | no | none | EXPERIMENTAL |
| Turkish | tr-TR | planned | unmeasured | yes | device check | no | none | EXPERIMENTAL |
| Vietnamese | vi-VN | planned | unmeasured | yes | device check | no | none | EXPERIMENTAL |

## Implementation contract

Central resource keys for UI, errors, screen reader labels and AAC; English fallback must be visibly identified. Preserve distinct language tags and source message language. User locale outranks autodetection. Format dates/numbers with locale and explicit timezone. React uses logical CSS and document `dir`; Compose uses start/end and layout direction. Show captions in spoken language; never silently translate family messages. Spoken-language support gives no sign-language support.

Acceptance: dynamic English/Spanish switching, Arabic/Hebrew layout tests without pretending translation completeness, long-string/zoom checks, per-device TTS availability and offline voice behavior. Only promote each capability after a recorded evaluation.
