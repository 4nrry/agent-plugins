---
name: audio
description: Makes and fixes audio for video — music generated at the exact length of the cut, generated or synthesized sound effects, noise removal, captions from real speech, word times for a voice-over. Use for a soundtrack, generated music, SFX, cleaning a noisy recording, subtitles for a real recording, word-by-word captions, or a named tool (ElevenLabs, ACE-Step, WhisperX). Library music and effects, stock footage and photos are in stock-media; narration is in voice.
---

# Audio for video

Voice-over is in the `voice` skill. Music, effects, footage and photos taken
from a library, and the license and credit rules for anything you did not
make, are in the `stock-media` skill. The rules below hold for any provider;
how to run each one is in `references/`:
[elevenlabs.md](references/elevenlabs.md) (SFX, music, cleanup,
transcription, dubbing, untested), [xai.md](references/xai.md) (transcription),
[local-stt.md](references/local-stt.md) (transcription and word alignment on
your own GPU) and [local-music.md](references/local-music.md) (music on
your own GPU).

## Music

- Use a music generator only where its terms allow commercial use. The ones
  checked: ElevenLabs ([elevenlabs.md](references/elevenlabs.md)) and ACE-Step
  ([local-music.md](references/local-music.md)) allow it, with the limits
  those files give; Google Flow Music has published no commercial terms.
- Make it the length of the cut. Generate at that length, or generate 40 s and
  loop with a 2 s crossfade: long generations degrade toward the end.
- For institutional pieces: instrumental, no drums, slow, minimal.
- Music at 0.5 alone, about 0.16 under the voice, with a ~0.35 s ramp.

## Sound effects

- Short, concrete prompts: "soft click pop for UI element appearing", not
  "a nice sound".
- Normalize effects with the music, not louder than the voice.
- Room, phone or radio effects are the last step.
- **Synthesized** effects need no license: `scripts/sfx-synth.py list` shows
  static, ticks, thuds, impacts, rain, wind, lamp hum, typing, a heartbeat
  and a TV switching off, made from a seed (same seed, same file). It needs
  numpy.
  Abstract or lo-fi pieces can use them for every effect.

## Fixing real recordings

- **Noise:** isolate the voice from a phone recording with street or fan
  noise before anything else.
- **Captions:** speech-to-text with word timings, for audio you did not
  generate. It rewrites numbers and currency and can drop a leading
  conjunction: review before burning in.
- **Word times for known text:** a voice-over's words are already known;
  align that text to the audio instead of transcribing it
  ([local-stt.md](references/local-stt.md)). Captions that light the spoken
  word need these times.
- **Another language:** for a generated voice-over, translate the voice JSON
  and generate the TTS again (captions stay exact). Dub only real speech that
  cannot be re-recorded.
- **A brand voice** is designed from a description; never imitate a real
  person.
