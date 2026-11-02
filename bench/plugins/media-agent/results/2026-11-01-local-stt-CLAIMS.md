# Batch 2026-11-01-local-stt — claims

**Notes, not run records.** Source of `skills/audio/references/local-stt.md`
(media-agent 0.16.0). Measured on 2026-11-01 on an RTX 4070 Laptop 8 GB with
WhisperX 3.8.6 (faster-whisper 1.2.1, torch 2.8.0), on the 82 voice lines of
the owner's private channel repository: ElevenLabs TTS in
Brazilian Portuguese, 48 kHz mono, 7.7 min in all, each with its script text.
n=1 per method.

**How timing was scored.** No hand labels. Reference points come from the
waveform (10 ms RMS frames): where the voice comes back after a pause of
60 ms or more (17 pauses; 6 of 120 ms or more), where it stops before one,
and where each line's voice starts at -25 dB from its peak. Every line opens
with about 60 ms at -35 dB before the voice. Medians of the absolute error:

| Method | First word | Voice back after pause | End before pause | Words under 20 ms | Time for 82 lines |
|---|---|---|---|---|---|
| WhisperX align, `jonatasgrosman/wav2vec2-large-xlsr-53-portuguese` (default) | 20 ms (+10 signed) | 19–28 ms | 13–18 ms | 0.8 % | 8.8 s |
| WhisperX align, `jonatasgrosman/wav2vec2-xls-r-1b-portuguese` | 30 ms (+30) | 23–29 ms | 26–34 ms | 1.6 % | 21.4 s |
| `Qwen/Qwen3-ForcedAligner-0.6B` (`qwen-asr` 0.0.6) | 60 ms (−60) | 40–60 ms | 15–20 ms | 4.0 % | 4.6 s |
| `nvidia/parakeet-tdt-0.6b-v3` own word times (NeMo 3.0.0) | 70 ms (−70) | 20–30 ms | 90–95 ms | 0.1 % | 3.7 s |
| faster-whisper `large-v3-turbo` own word times | 70 ms (−70) | 50–80 ms | 50–85 ms | 0.4 % | 28.7 s (transcribing) |

- The two wav2vec2 models and Qwen aligned the script text; Parakeet and
  turbo transcribed, and their words were mapped onto the script.
- Qwen and Parakeet return times in 80 ms steps. NeMo Forced Aligner is
  documented for CTC models; Parakeet v3 is TDT, so it was not used.
- Load times, first run with download: xlsr-53 27 s, xls-r 1B 82 s
  (7.2 GB on disk), Qwen 35 s, Parakeet 61 s.
- Transcription error against the scripts, numbers written as digits counted
  as errors: turbo 11.4 %, WhisperX with turbo 11.3 %, faster-whisper `small`
  12.4 %.
- With few pause references the timing columns show a direction, not a
  ranking with confidence.
