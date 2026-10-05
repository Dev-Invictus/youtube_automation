"""
make_broll_jagannath.py
Devotional motion graphics for the Jagannath explainer. Drawn in code, so there
is no stock footage and nothing to license.

Usage:
    python make_broll_jagannath.py
    python make_broll_jagannath.py --preview
"""
import argparse
import json
import math
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

W, H, FPS = 1920, 1080, 30

NIGHT_TOP = (26, 12, 34)
NIGHT_BOTTOM = (68, 24, 20)
DAWN_TOP = (54, 22, 46)
DAWN_BOTTOM = (188, 86, 32)
SAFFRON = (222, 108, 30)
GOLD = (240, 196, 88)
DEEP_GOLD = (176, 128, 40)
CREAM = (255, 244, 224)
MUTED = (226, 190, 152)
MAROON = (86, 30, 28)
FLAME = (255, 206, 120)
WHITE = (255, 252, 246)

FONT_PATHS = [
    ("/usr/share/fonts/truetype/noto/NotoSansDevanagari-Bold.ttf", None),
    ("/usr/share/fonts/truetype/noto/NotoSerifDevanagari-Bold.ttf", None),
    ("/usr/share/fonts/truetype/noto/NotoSansDevanagari-Regular.ttf", None),
    ("C:/Windows/Fonts/Nirmala.ttc", 0),
    ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", None),
]

_gradients: dict[tuple, Image.Image] = {}


def _font(size: int):
    for path, index in FONT_PATHS:
        if not Path(path).exists():
            continue
        try:
            return ImageFont.truetype(path, size=size) if index is None else ImageFont.truetype(path, size=size, index=index)
        except OSError:
            continue
    return ImageFont.load_default()


def _mix(a, b, t):
    t = max(0.0, min(1.0, t))
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def _ease(t):
    t = max(0.0, min(1.0, t))
    return t * t * (3 - 2 * t)


def _gradient(top, bottom):
    key = (top, bottom)
    if key not in _gradients:
        im = Image.new("RGB", (W, H))
        d = ImageDraw.Draw(im)
        for y in range(H):
            d.line([(0, y), (W, y)], fill=_mix(top, bottom, y / H))
        _gradients[key] = im
    return _gradients[key].copy()


def _centered(draw, text, font, cx, y, fill):
    l, t, r, b = draw.textbbox((0, 0), text, font=font)
    draw.text((cx - (r - l) / 2, y - (b - t) / 2), text, font=font, fill=fill)


def _glow(draw, cx, cy, radius, color, bg, rings=40):
    for i in range(rings, 0, -1):
        r = radius * i / rings
        shade = _mix(bg, color, (1 - i / rings) ** 1.6)
        draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=shade)


def _mandala(draw, cx, cy, radius, turn, color):
    for i in range(24):
        a = turn + i * math.pi / 12
        x1, y1 = cx + math.cos(a) * radius * 0.55, cy + math.sin(a) * radius * 0.55
        x2, y2 = cx + math.cos(a) * radius, cy + math.sin(a) * radius
        draw.line([(x1, y1), (x2, y2)], fill=color, width=3)
    draw.ellipse([cx - radius * 0.52, cy - radius * 0.52, cx + radius * 0.52, cy + radius * 0.52],
                 outline=color, width=3)


def _lotus(draw, cx, cy, size, color):
    for i in range(9):
        a = math.pi + i * math.pi / 8
        dx, dy = math.cos(a) * size * 0.75, math.sin(a) * size * 0.45
        draw.ellipse([cx + dx - size * 0.22, cy + dy - size * 0.34,
                      cx + dx + size * 0.22, cy + dy + size * 0.34], fill=color)
    draw.ellipse([cx - size * 0.9, cy - size * 0.12, cx + size * 0.9, cy + size * 0.22], fill=_mix(color, MAROON, 0.4))


def _diya(draw, cx, cy, size, flicker):
    draw.ellipse([cx - size, cy, cx + size, cy + size * 0.8], fill=MAROON)
    draw.ellipse([cx - size * 0.72, cy - size * 0.12, cx + size * 0.72, cy + size * 0.42], fill=(126, 52, 34))
    h = size * (1.5 + 0.28 * flicker)
    draw.polygon([(cx, cy - h), (cx - size * 0.34, cy - size * 0.05), (cx + size * 0.34, cy - size * 0.05)], fill=FLAME)
    draw.polygon([(cx, cy - h * 0.6), (cx - size * 0.16, cy - size * 0.05), (cx + size * 0.16, cy - size * 0.05)], fill=WHITE)


def _chakra(draw, cx, cy, r, turn, color):
    draw.ellipse([cx - r, cy - r, cx + r, cy + r], outline=color, width=6)
    draw.ellipse([cx - r * 0.2, cy - r * 0.2, cx + r * 0.2, cy + r * 0.2], fill=color)
    for i in range(8):
        a = turn + i * math.pi / 4
        draw.line([(cx + math.cos(a) * r * 0.2, cy + math.sin(a) * r * 0.2),
                   (cx + math.cos(a) * r, cy + math.sin(a) * r)], fill=color, width=4)


def _deity(draw, cx, cy, r, face, eye, halo=True):
    if halo:
        draw.ellipse([cx - r * 1.42, cy - r * 1.42, cx + r * 1.42, cy + r * 1.42], outline=DEEP_GOLD, width=3)

    crown_base = cy - r * 0.78
    draw.polygon([(cx - r * 0.86, crown_base), (cx + r * 0.86, crown_base), (cx, crown_base - r * 0.72)], fill=GOLD)
    draw.polygon([(cx - r * 0.52, crown_base), (cx + r * 0.52, crown_base), (cx, crown_base - r * 0.42)], fill=SAFFRON)
    draw.ellipse([cx - r * 0.1, crown_base - r * 0.86, cx + r * 0.1, crown_base - r * 0.66], fill=CREAM)

    draw.rounded_rectangle([cx - r, crown_base, cx + r, cy + r * 1.02], radius=int(r * 0.52), fill=face)

    er = r * 0.33
    ey = cy + r * 0.08
    for dx in (-r * 0.38, r * 0.38):
        draw.ellipse([cx + dx - er, ey - er, cx + dx + er, ey + er], fill=WHITE)
        draw.ellipse([cx + dx - er * 0.55, ey - er * 0.55, cx + dx + er * 0.55, ey + er * 0.55], fill=eye)

    tilak_top = crown_base + r * 0.12
    draw.arc([cx - r * 0.2, tilak_top, cx + r * 0.2, tilak_top + r * 0.42], start=20, end=160, fill=CREAM, width=5)
    draw.line([(cx, tilak_top + r * 0.04), (cx, tilak_top + r * 0.3)], fill=SAFFRON, width=5)

    draw.arc([cx - r * 0.3, cy + r * 0.48, cx + r * 0.3, cy + r * 0.86], start=15, end=165, fill=MAROON, width=6)


def _temple(draw, cx, base, scale, color):
    w = 150 * scale
    h = 420 * scale
    draw.polygon([(cx - w, base), (cx + w, base), (cx + w * 0.62, base - h * 0.62), (cx - w * 0.62, base - h * 0.62)], fill=color)
    draw.polygon([(cx - w * 0.62, base - h * 0.62), (cx + w * 0.62, base - h * 0.62), (cx, base - h)], fill=color)
    draw.rectangle([cx - 5 * scale, base - h - 60 * scale, cx + 5 * scale, base - h], fill=GOLD)
    draw.polygon([(cx + 5 * scale, base - h - 58 * scale), (cx + 95 * scale, base - h - 40 * scale),
                  (cx + 5 * scale, base - h - 18 * scale)], fill=SAFFRON)


def _crowd(draw, base, count, color, seedshift=0):
    for i in range(count):
        x = (i * 97 + seedshift * 37) % W
        r = 22 + (i % 3) * 6
        draw.ellipse([x - r, base - r * 2, x + r, base], fill=color)
        draw.ellipse([x - r * 0.5, base - r * 2.8, x + r * 0.5, base - r * 1.8], fill=color)


def frame_title(t, duration, title, subtitle):
    im = _gradient(NIGHT_TOP, NIGHT_BOTTOM)
    d = ImageDraw.Draw(im)
    _mandala(d, W // 2, int(H * 0.26), 130 + 6 * math.sin(t), t * 0.25, _mix(NIGHT_TOP, GOLD, 0.5))
    p = _ease(min(1.0, t / (duration * 0.4)))
    _centered(d, title, _font(66), W // 2, int(H * 0.50), _mix(NIGHT_BOTTOM, CREAM, p))
    _centered(d, subtitle, _font(40), W // 2, int(H * 0.61), _mix(NIGHT_BOTTOM, GOLD, p))
    flick = math.sin(t * 7) * 0.5 + 0.5
    _diya(d, int(W * 0.18), int(H * 0.78), 46, flick)
    _diya(d, int(W * 0.82), int(H * 0.78), 46, 1 - flick)
    _centered(d, "पुरी, ओडिशा", _font(32), W // 2, int(H * 0.88), MUTED)
    return im


def frame_meaning(t, duration):
    im = _gradient(NIGHT_TOP, MAROON)
    d = ImageDraw.Draw(im)
    _centered(d, "जगत् और नाथ", _font(58), W // 2, int(H * 0.26), GOLD)
    _centered(d, "संसार के स्वामी", _font(80), W // 2, int(H * 0.44), CREAM)
    bar = int(W * 0.46 * _ease(t / duration))
    d.rectangle([W // 2 - bar // 2, int(H * 0.56), W // 2 + bar // 2, int(H * 0.56) + 7], fill=SAFFRON)
    _lotus(d, W // 2, int(H * 0.74), 150, _mix(MAROON, SAFFRON, 0.75))
    return im


def frame_three(t, _duration):
    im = _gradient(NIGHT_TOP, MAROON)
    d = ImageDraw.Draw(im)
    _centered(d, "तीन विग्रह, एक परिवार", _font(50), W // 2, 120, CREAM)
    specs = [
        (int(W * 0.22), "बलभद्र", (246, 242, 230), (38, 44, 74)),
        (int(W * 0.50), "सुभद्रा", (238, 196, 92), (92, 42, 30)),
        (int(W * 0.78), "जगन्नाथ", (52, 38, 34), (18, 18, 18)),
    ]
    bob = math.sin(t * 1.6) * 8
    for i, (cx, name, face, eye) in enumerate(specs):
        cy = int(H * 0.50) + (bob if i % 2 == 0 else -bob)
        _deity(d, cx, cy, 145, face, eye)
        _centered(d, name, _font(42), cx, int(H * 0.80), GOLD)
    return im


def frame_temple(t, duration):
    im = _gradient(DAWN_TOP, DAWN_BOTTOM)
    d = ImageDraw.Draw(im)
    sun_y = int(H * 0.62 - H * 0.2 * _ease(t / duration))
    _glow(d, W // 2, sun_y, 240, GOLD, _mix(DAWN_TOP, DAWN_BOTTOM, sun_y / H))
    _temple(d, W // 2, int(H * 0.82), 1.25, (58, 26, 26))
    _temple(d, int(W * 0.28), int(H * 0.82), 0.7, (44, 20, 22))
    _temple(d, int(W * 0.74), int(H * 0.82), 0.62, (44, 20, 22))
    d.rectangle([0, int(H * 0.82), W, H], fill=(34, 16, 18))
    _chakra(d, int(W * 0.14), int(H * 0.22), 70, t * 0.5, _mix(DAWN_TOP, GOLD, 0.8))
    _centered(d, "श्रीमंदिर, पुरी धाम", _font(46), W // 2, int(H * 0.92), CREAM)
    return im


def frame_chardham(t, _duration):
    im = _gradient(NIGHT_TOP, NIGHT_BOTTOM)
    d = ImageDraw.Draw(im)
    _centered(d, "चार धाम", _font(54), W // 2, 120, CREAM)
    names = ["बद्रीनाथ", "द्वारका", "रामेश्वरम", "पुरी"]
    box, gap = 350, 76
    x0 = (W - (4 * box + 3 * gap)) // 2
    for i, name in enumerate(names):
        x, y = x0 + i * (box + gap), int(H * 0.36)
        live = name == "पुरी"
        pulse = 4 + int(4 * abs(math.sin(t * 2))) if live else 0
        d.rounded_rectangle([x, y, x + box, y + 300], radius=26,
                            fill=_mix(NIGHT_BOTTOM, MAROON, 0.6),
                            outline=GOLD if live else DEEP_GOLD, width=5 + pulse if live else 2)
        _temple(d, x + box // 2, y + 230, 0.42, _mix(MAROON, GOLD, 0.25) if live else (74, 34, 32))
        _centered(d, name, _font(38), x + box // 2, y + 262, CREAM if live else MUTED)
    _centered(d, "पुरी इनमें से एक है", _font(38), W // 2, int(H * 0.86), GOLD)
    return im


def frame_rath(t, duration):
    im = _gradient(DAWN_TOP, DAWN_BOTTOM)
    d = ImageDraw.Draw(im)
    _centered(d, "रथ यात्रा", _font(58), W // 2, 100, CREAM)
    p = _ease(t / duration)
    base = int(H * 0.72)
    d.rectangle([0, base, W, H], fill=(40, 18, 18))
    _crowd(d, base + 40, 18, (28, 12, 14), seedshift=1)
    x = int(-W * 0.1 + W * 0.85 * p)
    for i in range(5):
        d.line([(0, base + 24 + i * 9), (x - 60, base - 150 + i * 14)], fill=_mix(CREAM, SAFFRON, 0.35), width=3)
    d.polygon([(x, base - 250), (x + 430, base - 250), (x + 500, base), (x - 70, base)], fill=SAFFRON)
    d.polygon([(x + 40, base - 250), (x + 390, base - 250), (x + 215, base - 430)], fill=GOLD)
    for i in range(5):
        sx = x + 60 + i * 76
        d.line([(sx, base - 250), (x + 215, base - 420)], fill=_mix(GOLD, MAROON, 0.35), width=3)
    d.line([(x + 215, base - 430), (x + 215, base - 500)], fill=CREAM, width=6)
    d.polygon([(x + 218, base - 498), (x + 310, base - 474), (x + 218, base - 450)], fill=SAFFRON)
    for wx in (x + 60, x + 300):
        _chakra(d, wx + 60, base - 10, 78, -p * 12, MAROON)
    _crowd(d, base + 128, 14, (18, 8, 10), seedshift=5)
    _centered(d, "भगवान भक्तों के बीच आते हैं", _font(42), W // 2, int(H * 0.93), CREAM)
    return im


def frame_aarti(t, _duration):
    im = _gradient(NIGHT_TOP, MAROON)
    d = ImageDraw.Draw(im)
    _centered(d, "आरती और भक्ति", _font(52), W // 2, 130, GOLD)
    for row, (y, size, count) in enumerate([(int(H * 0.52), 34, 9), (int(H * 0.68), 44, 7), (int(H * 0.84), 54, 5)]):
        span = W / (count + 1)
        for i in range(count):
            flick = math.sin(t * 6 + i * 1.3 + row) * 0.5 + 0.5
            _diya(d, int(span * (i + 1)), y, size, flick)
    return im


def frame_mahaprasad(t, _duration):
    im = _gradient(NIGHT_TOP, NIGHT_BOTTOM)
    d = ImageDraw.Draw(im)
    _centered(d, "महाप्रसाद", _font(62), W // 2, 140, CREAM)
    _centered(d, "सबके लिए एक ही रसोई", _font(38), W // 2, 230, GOLD)
    rows = [(int(H * 0.72), 5, 110), (int(H * 0.55), 4, 96), (int(H * 0.40), 3, 82)]
    for y, count, size in rows:
        span = W / (count + 1)
        for i in range(count):
            cx = int(span * (i + 1))
            steam = math.sin(t * 2 + i) * 6
            d.ellipse([cx - size, y - size * 0.7, cx + size, y + size * 0.7], fill=(112, 48, 34))
            d.ellipse([cx - size, y - size * 0.95, cx + size, y - size * 0.35], fill=(146, 66, 42))
            d.arc([cx - size * 0.5, y - size * 1.9 + steam, cx + size * 0.5, y - size * 0.9 + steam],
                  start=200, end=340, fill=_mix(NIGHT_BOTTOM, CREAM, 0.5), width=4)
    return im


def frame_words(t, duration):
    im = _gradient(NIGHT_TOP, MAROON)
    d = ImageDraw.Draw(im)
    _mandala(d, W // 2, H // 2, 340, -t * 0.2, _mix(MAROON, DEEP_GOLD, 0.6))
    words = ["जय जगन्नाथ", "नवकलेवर", "छेर पाहरा", "सबका नाथ", "पुरी धाम की जय"]
    slot = duration / len(words)
    idx = min(len(words) - 1, int(t / slot))
    local = (t - idx * slot) / slot
    fade = _ease(min(1.0, local * 5)) * (1 - _ease(max(0.0, (local - 0.78) * 4.5)))
    _centered(d, words[idx], _font(76), W // 2, H // 2, _mix(MAROON, CREAM, fade))
    _lotus(d, W // 2, int(H * 0.80), 110, _mix(MAROON, SAFFRON, 0.6))
    return im


def render(name, maker, duration, out_dir, preview):
    if preview:
        path = out_dir / f"{name}.png"
        maker(duration * 0.6, duration).save(path)
        return path
    path = out_dir / f"{name}.mp4"
    cmd = [
        "ffmpeg", "-y", "-loglevel", "error",
        "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p",
        str(path),
    ]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    for n in range(int(duration * FPS)):
        proc.stdin.write(maker(n / FPS, duration).tobytes())
    proc.stdin.close()
    if proc.wait() != 0:
        raise SystemExit(f"ffmpeg failed while writing {path}")
    return path


def generate_broll(script_path="script_jagannath.json", out="clips/generated", preview=False):
    title, subtitle = "भगवान जगन्नाथ", "सरल भाषा में"
    path = Path(script_path)
    if path.exists():
        raw = json.loads(path.read_text(encoding="utf-8")).get("title", "")
        if "?" in raw:
            head, _, tail = raw.partition("?")
            title, subtitle = head.strip(), tail.strip() or subtitle
        elif raw:
            title = raw

    out_dir = Path(out)
    out_dir.mkdir(parents=True, exist_ok=True)
    for stale in list(out_dir.glob("*.mp4")) + list(out_dir.glob("*.png")):
        stale.unlink()

    plan = [
        ("01_title", lambda t, d: frame_title(t, d, title, subtitle), 11.0),
        ("02_meaning", frame_meaning, 12.0),
        ("03_three", frame_three, 14.0),
        ("04_temple", frame_temple, 13.0),
        ("05_chardham", frame_chardham, 12.0),
        ("06_rath", frame_rath, 17.0),
        ("07_aarti", frame_aarti, 13.0),
        ("08_mahaprasad", frame_mahaprasad, 13.0),
        ("09_words", frame_words, 17.0),
    ]
    written = []
    for name, maker, duration in plan:
        written.append(render(name, maker, duration, out_dir, preview))
        print(f"wrote {written[-1]}")
    return written


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--script", default="script_jagannath.json")
    ap.add_argument("--out", default="clips/generated")
    ap.add_argument("--preview", action="store_true")
    args = ap.parse_args()
    generate_broll(args.script, args.out, args.preview)


if __name__ == "__main__":
    main()
