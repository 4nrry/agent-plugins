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

The alternatives measured against it are in
[2026-11-01-local-stt-CLAIMS.md](https://github.com/4nrry/agent-plugins/blob/main/bench/plugins/media-agent/results/2026-11-01-local-stt-CLAIMS.md).
