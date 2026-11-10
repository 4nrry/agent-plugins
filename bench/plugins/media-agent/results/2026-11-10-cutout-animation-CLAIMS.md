# Batch 2026-11-10-cutout-animation — claims

**Notes, not run records.** Source of `skills/cutout-animation` (media-agent
0.17.0). One private landing-page prototype with three clay characters,
measured on 2026-11-10 on an RTX 4070 Laptop 8 GB. n=1 per character; nothing
here compares this route with another.

**Clips.** One clip per character from an approved still on a grey studio
sweep, through `video-generation`'s `grok-video.sh` at `--res 720p`: all three
came back 720x960 at 24 fps, two of 6.0 s and one of 10.0 s. The three were
used as first generated; no second attempt was made, so this says nothing
about how often a clip keeps the model.

**Cut-outs.** Frames at 10 fps through `image-retouching`'s
`comfy-run.py background` (BiRefNet), with the server kept up between calls:
129 images (126 frames of 720x960 and 3 prop images up to 1568x672) in 89 s of
wall time, frame extraction included. The first call of a cold server took 23 s for one image.

| Character | Loop | Frames cut out | Packed | Animated WebP | Sprite sheet |
|---|---|---|---|---|---|
| Octopus | cycle, 3.6 s trimmed from the clip | 36 | 36 frames, 400x406 | 725 KB | 684 KB (12x3) |
| Turtle | the whole clip, 6.0 s | 60 | 60 frames, 400x478 | 1064 KB | not written |
| Seahorse | ping-pong of 3.0 s | 30 | 58 frames, 330x717 | 1539 KB | 1450 KB (12x5, last frame held twice) |

- WebP quality 74, `method=4`, `minimize_size`; the still of frame 1 is 21 to
  29 KB at quality 82.
- `cutout_pack.py pack` on the octopus frames writes the same bytes as the
  file in the prototype.
- **Sprite CSS, checked in headless Chromium.** The octopus sheet's two
  `steps()` animations were paused at 0.05, 0.55, 1.25 and 3.55 s and the
  element compared with every frame of the animated WebP: the closest frame
  was the expected one each time (0, 5, 12, 35), with a mean difference of 3.3
  to 4.4 against 10.8 or more for the next closest. The seahorse sheet, the
  one with a held frame, was not checked in a browser.
- **Props.** `split` cut one matted image of five kelp strands into five
  files and refused a seven-prop image given two names.
- `cutout-frames.sh` on 0.5 s of one clip: 5 frames in 18 s including the
  server start, the server stopped at the end, and a second run did nothing
  and started no server.
- Not measured: Safari and Firefox, a phone, a chroma key on the same clips,
  alpha video, and whether a viewer reads the 10 fps loops as stop motion.
