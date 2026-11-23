# Batch 2026-11-23-blender-jpeg-metadata — claims

**Notes, not run records.** Behind the 3d-scenes rule that plates and every
frame a model looks at stay PNG (media-agent 0.33.1). n=1 per item. They
support "this file carries these segments"; they do not show which segment
makes Gemini refuse the request.

**The refusal (reported, not re-run here)**
- 2026-11-18, OpenBot agents on Gemini through the Antigravity runtime: after
  an agent read a `.jpg` written by Blender with its file tool, every
  following request in the turn returned `400 INVALID_ARGUMENT`, on Gemini 4
  Carbon, 4 Argon and 3.8 Flash; it stopped two agents four times in one
  production. The same frame stripped of Blender's metadata passed, as did a
  PNG from Blender, a JPEG from ffmpeg and a JPEG re-saved by Pillow.

**What Blender writes (measured 2026-11-23, Blender 5.3.0, factory settings,
Workbench, 64×64)**
- JPEG: APP0 JFIF; APP1 `NeoGeo` (Blender's private block, not Exif); seven
  COM segments `Blender:File`, `Date`, `Time`, `Frame`, `Camera`, `Scene`,
  `RenderTime`; APP2 ICC profile.
- PNG: colour chunks (cICP, iCCP with the ICC profile, sRGB, gAMA, cHRM),
  oFFs, pHYs, one eXIf chunk and the same seven keys as tEXt chunks.

**What each conversion keeps of the Blender JPEG**
- `mogrify -strip`: APP0 only.
- `vips copy` to PNG: one eXIf chunk (resolution, orientation) and pHYs; no
  comments, no `NeoGeo`, no ICC profile.
- `vips copy` to JPEG: one Exif APP1.
- Pillow 12.3.0 `save()` to JPEG: APP0 and one COM, the last Blender comment
  (`Blender:RenderTime`); `NeoGeo` and ICC dropped. To PNG: the ICC profile
  (iCCP) only; no eXIf, no text chunks.
- ImageMagick `magick in.jpg out.png`: the `NeoGeo` bytes as a
  `Raw profile type app1` tEXt chunk, the ICC profile and the Blender comment
  as zTXt, plus dates.
- ffmpeg to JPEG: APP0 and its own COM (`Lavc63.1.102`).

**Reading**
- A Pillow re-save that kept one `Blender:` comment passed on 2026-11-18, so a
  single comment does not explain the refusal. The JPEGs that passed (Pillow,
  ffmpeg, stripped) carry neither the `NeoGeo` APP1 nor an ICC profile; the
  Blender PNG that passed carries the ICC profile, as iCCP, and the seven keys
  as tEXt. In the JPEG the candidates are the `NeoGeo` APP1, the ICC profile
  as APP2, or the count of COM segments. Not tested against Gemini here.
