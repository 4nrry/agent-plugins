#!/usr/bin/env python3
"""Pack cut-out frames (RGBA PNGs) into what a web page loads.

  cutout_pack.py pack CUTDIR -o char.webp [--width 400] [--fps N] [--pingpong]
                 [--drop-last] [--still char-still.webp]
                 [--sprite sheet.webp --css sheet.css]
  cutout_pack.py split PROPS.png -o DIR --names kelp1,kelp2,kelp3 [--max-side 760]
  cutout_pack.py sheet CUTDIR [CUTDIR ...] -o sheet.jpg [--bg '#08384C'] [--n 6]
  cutout_pack.py --self-test

pack   crops every frame to ONE box (the union of all frames' alpha boxes), so the
       subject does not jitter, then writes an animated WebP with alpha. --still
       writes frame 1 in the same box, for prefers-reduced-motion. --sprite writes
       a grid sheet and --css the steps() rules that play it. Without --fps it
       plays at the rate cutout-frames.sh extracted the frames at (its record
       beside CUTDIR), or 10 when there is none. --drop-last leaves out the last
       frame, for a cycle trimmed so that it ends on the pose it starts with.
split  cuts one matted image of several separate props into one file per prop,
       left to right, by the empty columns between them.
sheet  lays sample frames over the page's background colour, to check edges and
       count limbs before the animation goes into a page.

Needs Pillow for everything but --self-test, which checks the arithmetic.
"""
import argparse
import math
import re
import sys
from pathlib import Path

WEBP_MAX_SIDE = 16383


def union_box(boxes, size, pad=6):
    """One crop box holding every frame's subject, padded and clamped to the frame."""
    boxes = [b for b in boxes if b]
    if not boxes:
        raise ValueError("every frame is fully transparent")
    w, h = size
    return (max(0, min(b[0] for b in boxes) - pad), max(0, min(b[1] for b in boxes) - pad),
            min(w, max(b[2] for b in boxes) + pad), min(h, max(b[3] for b in boxes) + pad))


def pingpong(n):
    """Frame order that plays forward then back without repeating either end."""
    return list(range(n)) + list(range(n - 2, 0, -1))


def marker_fps(text):
    """The rate in cutout-frames.sh's record ("CLIP SIZE MTIME fps=N [trim]"), or
    None. The last fps= wins: the clip's own name comes first and may hold one."""
    found = re.findall(r"(?:^| )fps=(\S+)", text)
    if not found:
        return None
    num, _, den = found[-1].partition("/")
    try:
        fps = float(num) / (float(den) if den else 1)
    except (ValueError, ZeroDivisionError):
        return None
    return fps if fps > 0 and math.isfinite(fps) else None


def runs(values, min_len, threshold=3):
    """Start/end of each stretch above threshold that is at least min_len long."""
    out, start = [], None
    for i, v in enumerate(list(values) + [0]):
        if v > threshold and start is None:
            start = i
        elif v <= threshold and start is not None:
            if i - start >= min_len:
                out.append((start, i))
            start = None
    return out


def grid(n, frame_w, frame_h, max_cols=12):
    """Columns, rows and padding frames for a sprite sheet of n frames.

    Two steps() animations play a grid only when it is full, so a count with no
    divisor that fits WebP's 16383 px side is padded by holding the last frame.
    """
    limit = max(1, min(max_cols, WEBP_MAX_SIDE // frame_w))
    fits = [c for c in range(1, limit + 1) if n % c == 0 and (n // c) * frame_h <= WEBP_MAX_SIDE]
    if fits:
        return max(fits), n // max(fits), 0
    cols = min(limit, n)
    rows = math.ceil(n / cols)
    if rows * frame_h > WEBP_MAX_SIDE:
        raise ValueError(f"{n} frames of {frame_w}x{frame_h} do not fit one WebP sheet; lower --width or --fps")
    return cols, rows, cols * rows - n


def steps_css(name, w, h, cols, rows, fps):
    """CSS that plays a full cols x rows sheet: x steps across, y steps down."""
    row_ms = round(1000 * cols / fps)        # whole milliseconds, and the column
    all_ms = row_ms * rows                   # cycle an exact multiple: no drift
    return (f".{name}{{width:{w}px;height:{h}px;background:url(\"{name}.webp\") 0 0/{cols * w}px {rows * h}px no-repeat;"
            f"animation:{name}-x {row_ms}ms steps({cols}) infinite"
            + (f",{name}-y {all_ms}ms steps({rows}) infinite" if rows > 1 else "") + "}\n"
            f"@keyframes {name}-x{{to{{background-position-x:-{cols * w}px}}}}\n"
            + (f"@keyframes {name}-y{{to{{background-position-y:-{rows * h}px}}}}\n" if rows > 1 else "")
            + f"@media (prefers-reduced-motion:reduce){{.{name}{{animation:none}}}}\n")


def _pil():
    try:
        from PIL import Image
    except ImportError:
        sys.exit("cutout_pack: Pillow is not installed (pip install pillow)")
    return Image


def _clean(im, floor):
    """RGBA with faint alpha dropped: what a matting model leaves of the studio shadow."""
    im = im.convert("RGBA")
    im.putalpha(im.getchannel("A").point(lambda v: 0 if v < floor else v))
    return im


def natural(path):
    """Sort key that puts f2 before f10 and f1000 after f999."""
    return [int(t) if t.isdigit() else t for t in re.split(r"(\d+)", Path(path).name)]


def css_name(sprite):
    """The sheet's stem, when it can be a CSS class and the CSS can point at it."""
    p = Path(sprite)
    return p.stem if p.suffix == ".webp" and re.fullmatch(r"[A-Za-z_][A-Za-z0-9_-]*", p.stem) else None


def hex_rgb(text):
    """(r, g, b) from #rgb or #rrggbb, or None."""
    t = text.lstrip("#")
    if len(t) == 3:
        t = "".join(c * 2 for c in t)
    if not re.fullmatch(r"[0-9A-Fa-f]{6}", t):
        return None
    return tuple(int(t[i:i + 2], 16) for i in (0, 2, 4))


def column_runs(alpha_bytes, width, min_len):
    """Props by column: a column counts when ANY pixel in it is opaque, so a thin
    tendril or bar still belongs to its prop."""
    return runs([max(alpha_bytes[x::width]) for x in range(width)], min_len, threshold=0)


def _frames(cutdir, floor):
    Image = _pil()
    files = sorted(Path(cutdir).glob("*.png"), key=natural)
    if not files:
        sys.exit(f"cutout_pack: no PNG frames in {cutdir}")
    fr = [_clean(Image.open(f), floor) for f in files]
    odd = [f.name for f, im in zip(files, fr) if im.size != fr[0].size]
    if odd:
        sys.exit(f"cutout_pack: frames differ in size from {files[0].name} ({fr[0].size[0]}x{fr[0].size[1]}): "
                 + ", ".join(odd[:5]) + "; are two runs mixed in this directory?")
    return fr


def _parent(path):
    Path(path).parent.mkdir(parents=True, exist_ok=True)


def cmd_pack(a):
    Image = _pil()
    marker = Path(a.cutdir).resolve().parent / ".cutout-frames"
    extracted = marker_fps(marker.read_text(encoding="utf-8", errors="replace")) if marker.is_file() else None
    if a.fps is None:
        a.fps = extracted or 10
        print(f"{a.fps:g} fps, " + (f"the rate the frames were extracted at ({marker})" if extracted
                                    else "the default: no record of the extraction beside the frames"))
    elif extracted and abs(a.fps - extracted) > 1e-6:
        print(f"cutout_pack: --fps {a.fps:g}, but the frames were extracted at {extracted:g}: "
              f"the motion plays at {a.fps / extracted:.2g}x", file=sys.stderr)
    if a.fps <= 0 or a.width <= 0:
        sys.exit("cutout_pack: --fps and --width must be above zero")
    if a.css and not a.sprite:
        sys.exit("cutout_pack: --css needs --sprite: the CSS plays the sprite sheet")
    if a.sprite and not css_name(a.sprite):
        sys.exit("cutout_pack: --sprite must be NAME.webp with NAME made of letters, digits, - and _ "
                 "and not starting with a digit: it becomes the CSS class")
    fr = _frames(a.cutdir, a.alpha_floor)
    if a.drop_last:
        if len(fr) < 2:
            sys.exit("cutout_pack: --drop-last needs at least two frames")
        fr = fr[:-1]
    try:
        box = union_box([f.getchannel("A").getbbox() for f in fr], fr[0].size)
    except ValueError as e:
        sys.exit(f"cutout_pack: {e}")
    h = round(a.width * (box[3] - box[1]) / (box[2] - box[0]))
    fr = [f.crop(box).resize((a.width, h), Image.LANCZOS) for f in fr]
    seq = [fr[i] for i in pingpong(len(fr))] if a.pingpong else fr
    out = Path(a.out)
    for target in (a.out, a.still, a.sprite, a.css):
        if target:
            _parent(target)
    seq[0].save(out, "WEBP", save_all=True, append_images=seq[1:], duration=round(1000 / a.fps),
                loop=0, quality=a.quality, method=4, minimize_size=True)
    print(f"{out}: {len(seq)} frames, {a.width}x{h}, {out.stat().st_size // 1024} KB")
    if a.still:
        fr[0].save(a.still, "WEBP", quality=82, method=6)
        print(f"{a.still}: {Path(a.still).stat().st_size // 1024} KB")
    if a.sprite:
        try:
            cols, rows, padn = grid(len(seq), a.width, h)
        except ValueError as e:
            sys.exit(f"cutout_pack: {e}")
        cells = seq + [seq[-1]] * padn
        sheet = Image.new("RGBA", (cols * a.width, rows * h), (0, 0, 0, 0))
        for i, f in enumerate(cells):
            sheet.paste(f, ((i % cols) * a.width, (i // cols) * h))
        sheet.save(a.sprite, "WEBP", quality=a.quality, method=6)
        print(f"{a.sprite}: {cols}x{rows} cells, {Path(a.sprite).stat().st_size // 1024} KB"
              + (f", last frame held {padn}x to fill the grid" if padn else ""))
        if a.css:
            Path(a.css).write_text(steps_css(css_name(a.sprite), a.width, h, cols, rows, a.fps), encoding="utf-8")
            print(a.css)


def cmd_split(a):
    Image = _pil()
    im = _clean(Image.open(a.image), a.alpha_floor)
    found = column_runs(im.getchannel("A").tobytes(), im.width, a.min_width)
    names = [n.strip() for n in a.names.split(",") if n.strip()]
    if len(found) != len(names):
        sys.exit(f"cutout_pack: found {len(found)} props, {len(names)} names given; "
                 "the props must not touch or overlap side by side")
    outdir = Path(a.out)
    outdir.mkdir(parents=True, exist_ok=True)
    for (x0, x1), name in zip(found, names):
        p = im.crop((x0, 0, x1, im.height))
        p = p.crop(p.getchannel("A").getbbox())
        k = a.max_side / max(p.size)
        if k < 1:
            p = p.resize((round(p.width * k), round(p.height * k)), Image.LANCZOS)
        o = outdir / f"{name}.webp"
        p.save(o, "WEBP", quality=84, method=6)
        print(f"{o}: {p.width}x{p.height}, {o.stat().st_size // 1024} KB")


def cmd_sheet(a):
    Image = _pil()
    bg = hex_rgb(a.bg)
    if bg is None:
        sys.exit(f"cutout_pack: --bg {a.bg!r} is not #rgb or #rrggbb")
    _parent(a.out)
    cell = (360, 480)
    sheet = Image.new("RGB", (cell[0] * a.n, cell[1] * len(a.cutdirs)), bg)
    for row, d in enumerate(a.cutdirs):
        fr = _frames(d, a.alpha_floor)
        for col in range(a.n):
            f = fr[round(col * (len(fr) - 1) / max(1, a.n - 1))].copy()
            f.thumbnail(cell, Image.LANCZOS)
            sheet.paste(f, (col * cell[0] + (cell[0] - f.width) // 2, row * cell[1] + (cell[1] - f.height) // 2), f)
    sheet.save(a.out, quality=84)
    print(a.out)


def self_test():
    assert union_box([(10, 20, 50, 60), None, (5, 30, 70, 55)], (100, 80), pad=6) == (0, 14, 76, 66)
    assert union_box([(0, 0, 100, 80)], (100, 80)) == (0, 0, 100, 80)
    try:
        union_box([None, None], (10, 10))
        raise AssertionError("an all-transparent set must be refused")
    except ValueError:
        pass
    assert pingpong(4) == [0, 1, 2, 3, 2, 1]
    assert marker_fps("/w/clip.mp4 123456 1700000000 fps=12 -ss 1.45 -t 3.6") == 12
    assert marker_fps("/w/clip.mp4 123456 1700000000 fps=25/2 ") == 12.5
    assert marker_fps("/w/take fps=24 b.mp4 9 9 fps=10 ") == 10      # the clip's name is not the rate
    assert marker_fps("/w/clip.mp4 9 9") is None and marker_fps("x fps=abc") is None
    assert marker_fps("x fps=0") is None and marker_fps("x fps=1/0") is None
    assert marker_fps("x fps=inf") is None and marker_fps("x fps=nan") is None
    assert pingpong(2) == [0, 1] and pingpong(1) == [0]
    cols = [0] * 5 + [200] * 30 + [0] * 4 + [9] * 3 + [0] * 4 + [255] * 40
    assert runs(cols, 24) == [(5, 35), (46, 86)]          # the 3-wide speck is not a prop
    assert runs([0, 0, 0], 1) == []
    assert grid(36, 400, 406) == (12, 3, 0)
    assert grid(60, 400, 478) == (12, 5, 0)
    assert grid(58, 330, 717) == (12, 5, 2)               # 2 x 29 would be 20793 px tall: pad instead
    assert grid(37, 400, 406) == (1, 37, 0)               # prime, but one column still fits
    assert grid(37, 400, 800) == (12, 4, 11)              # prime and too tall: hold the last frame
    assert grid(10, 2000, 100) == (5, 2, 0)               # the width limit caps the columns at 8
    assert grid(3, 400, 400) == (3, 1, 0)
    try:
        grid(400, 400, 4000)
        raise AssertionError("a sheet taller than WebP allows must be refused")
    except ValueError:
        pass
    css = steps_css("octopus", 400, 406, 12, 3, 10)
    assert "steps(12)" in css and "steps(3)" in css and "-4800px" in css and "-1218px" in css
    assert "octopus-x 1200ms" in css and "octopus-y 3600ms" in css
    odd = steps_css("s", 100, 100, 12, 3, 7)               # 12/7 s is not a whole ms:
    assert "s-x 1714ms" in odd and "s-y 5142ms" in odd     # the long cycle is still 3 x the short one
    assert sorted(["f10.png", "f2.png", "f1000.png", "f999.png"], key=natural) == ["f2.png", "f10.png", "f999.png", "f1000.png"]
    assert css_name("out dir/sheet-2.webp") == "sheet-2"
    assert css_name("a.v2.webp") is None and css_name("2x.webp") is None and css_name("sheet.png") is None
    assert hex_rgb("#abc") == (170, 187, 204) and hex_rgb("08384C") == (8, 56, 76) and hex_rgb("#12") is None
    w, hgt = 12, 4                                          # two props; the second has a 1 px bar joining two blobs
    px = [[0] * w for _ in range(hgt)]
    for y in range(hgt):
        for x in (1, 2, 3, 6, 7, 10, 11):
            px[y][x] = 255
    px[0][8] = px[0][9] = 255
    flat = bytes(v for row in px for v in row)
    assert column_runs(flat, w, 2) == [(1, 4), (6, 12)]
    assert "octopus-y" not in steps_css("octopus", 400, 406, 12, 1, 10)
    print("self-test OK — one crop box per clip, ping-pong order, prop columns, grid sizes and steps() CSS")
    return 0


def main():
    if "--self-test" in sys.argv[1:]:
        return self_test()
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    k = sub.add_parser("pack")
    k.add_argument("cutdir"); k.add_argument("-o", "--out", required=True)
    k.add_argument("--width", type=int, default=400); k.add_argument("--fps", type=float)
    k.add_argument("--drop-last", action="store_true", help="leave out the last frame (a cycle that ends on its first pose)")
    k.add_argument("--pingpong", action="store_true"); k.add_argument("--quality", type=int, default=74)
    k.add_argument("--still"); k.add_argument("--sprite"); k.add_argument("--css")
    k.set_defaults(fn=cmd_pack)
    s = sub.add_parser("split")
    s.add_argument("image"); s.add_argument("-o", "--out", required=True); s.add_argument("--names", required=True)
    s.add_argument("--max-side", type=int, default=760); s.add_argument("--min-width", type=int, default=24)
    s.set_defaults(fn=cmd_split)
    c = sub.add_parser("sheet")
    c.add_argument("cutdirs", nargs="+"); c.add_argument("-o", "--out", required=True)
    c.add_argument("--bg", default="#08384C"); c.add_argument("--n", type=int, default=6)
    c.set_defaults(fn=cmd_sheet)
    for x in (k, s, c):
        x.add_argument("--alpha-floor", type=int, default=40, help="alpha below this becomes 0 (studio shadow residue)")
    a = p.parse_args()
    a.fn(a)
    return 0


if __name__ == "__main__":
    sys.exit(main())
