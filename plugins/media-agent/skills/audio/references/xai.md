# xAI transcription

Checked on 2026-10-26. xAI's speech-to-text (`grok-voice-transcribe-2.0`,
`POST /v1/stt`, word-level timestamps, 38+ languages) takes an xAI API key.

On the SuperGrok subscription there is no headless route yet: Hermes uses this
model only for voice messages in its gateway and voice mode, and `hermes chat`
has no transcription tool (`-t stt` is rejected); Grok Build and Cursor CLI
have no audio tools. For word-timed captions of real speech, use ElevenLabs'
`eleven.py stt`, or the xAI API with a key.
