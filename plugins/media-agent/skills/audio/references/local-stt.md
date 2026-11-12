# Local speech-to-text and word alignment (WhisperX)

WhisperX runs Whisper through faster-whisper, then a language-specific
wav2vec2 model moves every word onto the audio. Check for it with
`command -v whisperx`. Install it, if the user agrees, as its own tool:

```bash
uv tool install whisperx --python 3.12
```

It pulls torch with its CUDA libraries (about 7 GB). The first run downloads
the Whisper model and the alignment model for the language.

## Transcribe real speech

```bash
whisperx audio.wav --model large-v3-turbo --language pt --compute_type float16 --output_format json
```

Word times are in `segments[].words[]` (`word`, `start`, `end`). Starting torch
costs about 10 s per call: pass every file in one call. On a machine without
an NVIDIA GPU, use `--device cpu --compute_type int8`.

## Align text you already have

For a generated voice-over the words are known, so do not transcribe: align
the line's spoken text to its file. Captions then never contain a
transcription error. Use the tool's own interpreter, the path on the first
line of the launcher (`head -1 "$(command -v whisperx)"`):

```python
import whisperx
from whisperx.audio import SAMPLE_RATE

model, meta = whisperx.load_align_model(language_code="pt", device="cuda")
audio = whisperx.load_audio("s1.wav")
res = whisperx.align([{"text": say, "start": 0.0, "end": len(audio) / SAMPLE_RATE}],
                     model, meta, audio, "cuda")
words = [w for seg in res["segments"] for w in seg["words"]]
```

- Align `say`, the text the TTS spoke, not the caption `text` (`voice`
  skill). Where they differ ("20k" against "twenty thousand"), the caption
  word takes the span of the spoken words it stands for.
- A word with no letters the model knows (a lone symbol) comes back without
  `start`: give it the gap between its neighbours.
- Keep WhisperX's default alignment model for the language. Whisper's own word
  times put a line's first word at 0 and end words late, which shows when a
  caption lights the spoken word.

## Transcribe on an Intel NPU

Intel Core Ultra processors carry an NPU. OpenVINO GenAI runs Whisper on it,
with word times, and leaves the NVIDIA GPU and its memory free: WhisperX
holds about 3.5 GiB of an 8 GiB card while it runs. Use it when the GPU is busy
(ComfyUI, Blender, a render) or there is no NVIDIA GPU.

- The kernel driver alone is not enough. `/dev/accel/accel0` must exist, and
  the user-space driver must be installed: the `intel-level-zero-npu` and
  `intel-driver-compiler-npu` packages from Intel's `linux-npu-driver`
  releases on GitHub (not in Ubuntu's archive; installing them needs root,
  so ask the user). Check with the environment below, where `openvino` is
  installed:
  `.venv/bin/python -c "import openvino as ov; print(ov.Core().available_devices)"`.
  `NPU` must be in the list.
- Install in its own environment: `uv venv -p 3.13` and
  `uv pip install openvino-genai soundfile` (about 280 MB). Take a model
  already converted by Intel, such as
  `OpenVINO/whisper-large-v3-turbo-int8-ov` (790 MB, MIT): no torch needed.
- The first load on the NPU compiles the model for minutes (200 to 275 s
  here). Pass a cache directory and later loads take seconds:

```python
import openvino_genai as ovg, soundfile as sf

pipe = ovg.WhisperPipeline("whisper-large-v3-turbo-int8-ov", "NPU",
                           word_timestamps=True, CACHE_DIR="ov-cache")
audio, sr = sf.read("audio.wav", dtype="float32")    # 16 kHz mono
res = pipe.generate(audio.tolist(), language="<|pt|>", return_timestamps=True,
                    word_timestamps=True)
words = [(w.word, w.start_ts, w.end_ts) for w in res.words]
```

- It made as few errors against the script as WhisperX (6.4 % against
  6.6 %). Its word times are Whisper's own, a median of 75 ms from WhisperX's
  alignment: good for a caption per phrase, not for
  lighting each spoken word. For that, align the text with WhisperX as above.
- The same code runs on `"CPU"`: about as fast as the NPU on an idle machine,
  about three times slower when another job holds the CPU.

The alternatives measured against it are in
[2026-11-01-local-stt-CLAIMS.md](https://github.com/4nrry/agent-plugins/blob/main/bench/plugins/media-agent/results/2026-11-01-local-stt-CLAIMS.md),
the NPU in
[2026-11-11-npu-whisper-CLAIMS.md](https://github.com/4nrry/agent-plugins/blob/main/bench/plugins/media-agent/results/2026-11-11-npu-whisper-CLAIMS.md).
