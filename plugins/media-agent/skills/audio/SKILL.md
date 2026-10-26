---
name: audio
description: Gets music, sound effects and audio fixes for video under commercial licenses — exact-length music, SFX, stock audio with credits, noise removal, transcription of real speech, dubbing. Use for a soundtrack, royalty-free music, SFX, CC0 or CC-BY credits, or a named source (ElevenLabs, ACE-Step, Freesound).
---

# Audio for video

Voice-over is in the `voice` skill. The rules below hold for any provider; how
to run each one is in `references/`:
[elevenlabs.md](references/elevenlabs.md) (SFX, music, cleanup,
transcription, dubbing), [xai.md](references/xai.md) (transcription),
[local-music.md](references/local-music.md) (music on
your own GPU) and [stock.md](references/stock.md) (libraries and their
licenses).

## Licenses

- "Copyright free" does not exist; a license that allows your use does. Every
  service shows the media for free and keeps the condition in its terms: check
  commercial use, the platforms allowed, and credit.
- CC-BY needs credit per item, visible in the piece or its description. Keep a
  `CREDITS.json` beside the files with id, author, license and URL.
- A license filter in a search API trusts what uploaders declared: open the
  item's page before using it.

## Music

- Google Flow Music (Lyria 3.5) publishes no commercial terms yet: not for a
  commercial piece.
- Make it the length of the cut. Generate at that length, or generate 40 s and
  loop with a 2 s crossfade: long generations degrade toward the end.
- For institutional pieces: instrumental, no drums, slow, minimal.
- Music at 0.5 alone, about 0.16 under the voice, with a ~0.35 s ramp.

## Sound effects

- Short, concrete prompts: "soft click pop for UI element appearing", not
  "a nice sound".
- Normalize effects with the music, not louder than the voice.
- Room, phone or radio effects are the last step.

## Fixing real recordings

- **Noise:** isolate the voice from a phone recording with street or fan
  noise before anything else.
- **Captions:** speech-to-text with word timings, for audio you did not
  generate. It rewrites numbers and currency and can drop a leading
  conjunction: review before burning in.
- **Another language:** for a generated voice-over, translate the voice JSON
  and generate the TTS again (captions stay exact). Dub only real speech that
  cannot be re-recorded.
- **A brand voice** is designed from a description; never imitate a real
  person.
