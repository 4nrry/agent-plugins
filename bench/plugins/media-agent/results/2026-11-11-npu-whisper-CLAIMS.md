# Batch 2026-11-11-npu-whisper — claims

**Notes, not run records.** Source of the "Transcribe on an Intel NPU"
section of `skills/audio/references/local-stt.md` (media-agent 0.22.1).
Measured on 2026-11-11 on an Intel Core Ultra 9 185H (Meteor Lake, NPU
`8086:7d1d`) beside an RTX 4070 Laptop 8 GB, Ubuntu 26.10, kernel 7.3.

**Setup.** The kernel's `intel_vpu` driver and its firmware were already
loaded; OpenVINO listed only `CPU` and `GPU` (the GPU device it found was the
RTX 4070, not the integrated Arc). After installing `intel-level-zero-npu`
and `intel-driver-compiler-npu` 1.38.0 (Intel's `linux-npu-driver` release
for Ubuntu 26.04; 140 MB on disk by apt's count; the firmware package was
left out) it listed `NPU` as "Intel(R) AI Boost". OpenVINO 2026.4.1 and OpenVINO GenAI
2026.4.1.0 from PyPI in a Python 3.13 environment (283 MB),
`OpenVINO/whisper-large-v3-turbo-int8-ov` (790 MB). WhisperX 3.8.6 with
`large-v3-turbo`, float16, as in `local-stt.md`.

**Audio.** 29 lines of Brazilian Portuguese written for the test and spoken
by Kokoro (`pm_alex`), joined into one 152 s file at 16 kHz mono: synthetic
speech, with the script as reference. Two OpenVINO runs per load, the faster
one reported; one WhisperX call per row.

**Idle machine.**

| Path | Time for 152 s | Load | Errors against the script | GPU memory |
|---|---|---|---|---|
| WhisperX on the RTX 4070, with word alignment | 34.3 s (whole call) | in the call | 6.6 % (29 of 440 words) | 3,538 MiB above the 191 MiB before the call |
| WhisperX, `--no_align` | 16.1 s (whole call) | in the call | — | — |
| OpenVINO on the CPU, word times on | 43.0 s | 1.3 s | 6.4 % (28 of 440) | none |
| OpenVINO on the NPU, word times on | 38.7 s | 200 s (compiling) | 6.4 % (28 of 440) | none |

**With another job on the CPU.** Two Blender renders from another session
held the CPU (load average about 41 on 22 threads; the GPU idle):

| Path | Time for 152 s | Load |
|---|---|---|
| WhisperX on the RTX 4070, with word alignment | 65.2 s (whole call) | in the call |
| OpenVINO on the CPU | 182.9 s | 12.7 s |
| OpenVINO on the NPU, first load filling the cache | 69.3 s | 275 s |
| OpenVINO on the NPU, cache filled | 66.4 s | 6.6 s |

The NPU process still used 12.5 to 19.6 s of CPU time per run. The compile
cache took 2.0 GB.

- Errors: lowercase, punctuation dropped, a digit where the script spells
  the number counted as an error, as in `2026-11-01-local-stt-CLAIMS.md`.
  CPU and NPU texts were not byte-identical but scored the same.
- Word times: OpenVINO's (Whisper's own, `word_timestamps=True`) matched to
  WhisperX's aligned words by edit-distance alignment on equal words. Start
  difference over 426 words: median 75 ms, 90th percentile 207 ms (NPU) and
  208 ms (CPU).
- WhisperX's times are the shell's wall clock around each call and were not
  saved to a file; they include torch start-up (about 10 s, from
  `local-stt.md`, not measured here). OpenVINO's run times exclude its load.
- GPU memory: `nvidia-smi` sampled every 0.5 s during one WhisperX call with
  alignment; peak 3,729 MiB against 191 MiB before it.

**Not measured.** Real recordings; other model sizes or fp16; WhisperX's
alignment model on the CPU or NPU next to OpenVINO's transcription; the
integrated Arc GPU (its compute runtime is not installed); power draw; the
firmware package from the same release. n=1 per row, and the loaded case
depended on another session's jobs, so its rows show a direction, not a
ranking with confidence.
