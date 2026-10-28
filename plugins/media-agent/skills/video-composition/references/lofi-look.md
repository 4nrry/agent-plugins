# Lo-fi tape look

A VHS treatment over 3D plates or flat graphics. It also hides a low render
sample count, so a 540×960 EEVEE plate at 8 samples passes as 1080×1920.
Values below come from one series (Sinal Público, 2026-10), applied per frame
in numpy on the low-resolution plate before upscaling.

| Step | Value |
|---|---|
| Upscale | ×2 nearest neighbour, never smoothed |
| Tint | RGB × (0.97, 0.99, 1.03) |
| Bloom | pixels above 0.6, ×2.5, Gaussian blur 6 px (3 px at half size), added at 0.35 |
| Grain | Gaussian σ 0.032 per pixel, the same on all channels |
| Banding | quantize to 32 levels with a 4×4 Bayer dither |
| Chroma | shift R and B horizontally by 3 + 12·g px (g = glitch strength 0–1) |
| Scanlines | odd rows × 0.8; interlace on odd frames |
| Tracking | a horizontal tear every 2.5 s for 4 frames, band 20 + 70·g px, offset up to ±34·g px |
| Vignette | `1 - 0.5·r³`, clamped at 0.3 |

Cuts and pacing:

- Hard cut: 4 frames of static around it, weights 0.25, 0.6, 0.7, 0.3 from
  two frames before to one after, with the `static` effect from the `audio`
  skill (`scripts/sfx-synth.py static`).
- A soft wobble (glitch 0.25 for 3 frames) where the sound has static and the
  picture does not cut.
- Never open on black: frames 0–3 carry a strong tracking glitch over the
  first image.
- Keep text and captions outside the effect, drawn after it, or the grain and
  chroma shift make small type unreadable.
