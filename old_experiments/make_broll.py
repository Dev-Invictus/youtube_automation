"""
make_broll.py
Generates on-topic B-roll clips locally with Pillow + ffmpeg. No stock footage,
no API keys, no licensing questions.

Usage:
    python make_broll.py                  # render mp4 clips into clips/generated
    python make_broll.py --preview        # write one PNG per clip (no ffmpeg needed)
    python make_broll.py --out clips/x    # choose output folder
"""
import argparse
import json
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

W, H, FPS = 1920, 1080, 30

BG = (13, 17, 23)
PANEL = (22, 27, 34)
LINE = (48, 54, 61)
FG = (230, 237, 243)
MUTED = (139, 148, 158)
ACCENT = (63, 185, 80)
WARN = (248, 81, 73)

STAGES = ["Commit", "Build", "Test", "Deploy"]
KEYWORDS = [
    "Continuous Integration",
    "Continuous Delivery",
    "Automated tests",
    "Merge early, merge often",
    "Ship without the all-nighter",
]
TERMINAL_LINES = [
    "$ git push origin main",
    "  pipeline triggered",
    "  build passed  42s",
    "  128 tests passed  1m 09s",
    "  deployed to production",
]
OLD_WAY = ["Merge once a week", "All-night releases", "Bugs found days later", "Everyone stressed"]
NEW_WAY = ["Merge many times a day", "Tests on every push", "Failures caught in minutes", "Releases are boring"]
BENEFITS = [("Speed", "ship many times a day"), ("Reliability", "tests on every change"), ("Calm", "small, low-risk releases")]
YAML_LINES = [
    "name: CI",
    "on: [push]",
    "",
    "jobs:",
    "  test:",
    "    runs-on: ubuntu-latest",
    "    steps:",
    "      - uses: actions/checkout@v4",
    "      - run: pip install -r requirements.txt",
    "      - run: pytest -q",
]

FONT_DIRS = [
    "/usr/share/fonts/truetype/dejavu",
    "/usr/share/fonts/truetype/liberation",
    "C:/Windows/Fonts",
]
BOLD_NAMES = ["DejaVuSans-Bold.ttf", "LiberationSans-Bold.ttf", "arialbd.ttf", "segoeuib.ttf"]
REGULAR_NAMES = ["DejaVuSans.ttf", "LiberationSans-Regular.ttf", "arial.ttf", "segoeui.ttf"]
MONO_NAMES = ["DejaVuSansMono.ttf", "LiberationMono-Regular.ttf", "consola.ttf", "cour.ttf"]


def _font(size: int, bold: bool = False, mono: bool = False):
    names = MONO_NAMES if mono else (BOLD_NAMES if bold else REGULAR_NAMES)
    for directory in FONT_DIRS:
        for name in names:
            candidate = Path(directory) / name
            if candidate.exists():
                return ImageFont.truetype(str(candidate), size)
    return ImageFont.load_default()


def _ease(t: float) -> float:
    """Smoothstep, so motion starts and ends gently."""
    t = max(0.0, min(1.0, t))
    return t * t * (3 - 2 * t)


def _mix(a, b, t: float):
    t = max(0.0, min(1.0, t))
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def _centered(draw, text, font, cx, y, fill):
    left, top, right, bottom = draw.textbbox((0, 0), text, font=font)
    draw.text((cx - (right - left) / 2, y - (bottom - top) / 2), text, font=font, fill=fill)


def _check(draw, x, y, size, color):
    draw.line(
        [(x, y + size * 0.55), (x + size * 0.38, y + size * 0.9), (x + size, y)],
        fill=color,
        width=max(3, int(size * 0.18)),
        joint="curve",
    )


def _cross(draw, x, y, size, color):
    w = max(3, int(size * 0.16))
    draw.line([(x, y), (x + size, y + size)], fill=color, width=w)
    draw.line([(x + size, y), (x, y + size)], fill=color, width=w)


def _dots(draw, spacing, drift):
    for y in range(-spacing, H + spacing, spacing):
        for x in range(-spacing, W + spacing, spacing):
            px, py = x + drift, y + drift * 0.4
            draw.ellipse([px - 2, py - 2, px + 2, py + 2], fill=(28, 34, 43))


def frame_title(t: float, duration: float, title: str, subtitle: str) -> Image.Image:
    """Title card with a slow push-in and an accent bar that draws itself."""
    p = t / duration
    scale = 1.0 + 0.05 * _ease(p)
    big = Image.new("RGB", (int(W * scale), int(H * scale)), BG)
    d = ImageDraw.Draw(big)
    sw, sh = big.size

    for i in range(0, sh, 120):
        d.line([(0, i), (sw, i)], fill=(18, 23, 31), width=1)

    bar_h = int(sh * 0.62 * _ease(min(1.0, p * 2.2)))
    d.rectangle([int(sw * 0.07), int(sh * 0.2), int(sw * 0.07) + 14, int(sh * 0.2) + bar_h], fill=ACCENT)

    d.text((int(sw * 0.11), int(sh * 0.34)), title, font=_font(int(96 * scale), bold=True), fill=FG)
    d.text((int(sw * 0.11), int(sh * 0.50)), subtitle, font=_font(int(46 * scale)), fill=MUTED)

    left = (sw - W) // 2
    top = (sh - H) // 2
    return big.crop((left, top, left + W, top + H))


def frame_pipeline(t: float, duration: float) -> Image.Image:
    """Four stage cards that light up in sequence and get a checkmark."""
    im = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(im)

    card_w, card_h, gap = 360, 240, 60
    total = len(STAGES) * card_w + (len(STAGES) - 1) * gap
    x0 = (W - total) // 2
    y0 = (H - card_h) // 2

    per_stage = duration / (len(STAGES) + 0.5)
    active = t / per_stage

    _centered(d, "CI/CD pipeline", _font(52, bold=True), W // 2, int(H * 0.18), FG)

    for i, stage in enumerate(STAGES):
        x = x0 + i * (card_w + gap)
        done = active > i + 1
        live = i <= active <= i + 1
        outline = ACCENT if (done or live) else LINE
        width = 6 if live else 3
        d.rounded_rectangle([x, y0, x + card_w, y0 + card_h], radius=22, fill=PANEL, outline=outline, width=width)
        _centered(d, stage, _font(46, bold=True), x + card_w // 2, y0 + card_h // 2 - 14, FG if (done or live) else MUTED)
        if done:
            _check(d, x + card_w // 2 - 22, y0 + card_h - 74, 44, ACCENT)

        if i < len(STAGES) - 1:
            ax = x + card_w + 12
            ay = y0 + card_h // 2
            lit = active > i + 1
            d.line([(ax, ay), (ax + gap - 24, ay)], fill=ACCENT if lit else LINE, width=4)
            tip = ax + gap - 24
            d.polygon([(tip, ay - 11), (tip, ay + 11), (tip + 16, ay)], fill=ACCENT if lit else LINE)

    return im


def frame_progress(t: float, duration: float) -> Image.Image:
    """A single pipeline bar filling left to right with a percentage."""
    im = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(im)

    p = _ease(t / duration)
    bar_w, bar_h = int(W * 0.72), 44
    x0 = (W - bar_w) // 2
    y0 = H // 2 - bar_h // 2

    _centered(d, "Every push runs the pipeline", _font(54, bold=True), W // 2, int(H * 0.28), FG)

    d.rounded_rectangle([x0, y0, x0 + bar_w, y0 + bar_h], radius=bar_h // 2, fill=PANEL)
    if p > 0:
        d.rounded_rectangle([x0, y0, x0 + int(bar_w * p), y0 + bar_h], radius=bar_h // 2, fill=ACCENT)

    for i, stage in enumerate(STAGES):
        sx = x0 + int(bar_w * (i / (len(STAGES) - 1)))
        reached = p >= i / (len(STAGES) - 1)
        d.ellipse([sx - 9, y0 + bar_h // 2 - 9, sx + 9, y0 + bar_h // 2 + 9], fill=FG if reached else LINE)
        _centered(d, stage, _font(34, bold=reached), sx, y0 + bar_h + 56, FG if reached else MUTED)

    _centered(d, f"{int(p * 100)}%", _font(72, bold=True), W // 2, int(H * 0.72), ACCENT)
    return im


def frame_keywords(t: float, duration: float) -> Image.Image:
    """Drifting dot grid with one keyword crossfaded at a time."""
    im = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(im)
    _dots(d, 90, (t * 26) % 90)

    slot = duration / len(KEYWORDS)
    idx = min(len(KEYWORDS) - 1, int(t / slot))
    local = (t - idx * slot) / slot
    fade = _ease(min(1.0, local * 4)) * (1 - _ease(max(0.0, (local - 0.75) * 4)))

    _centered(d, KEYWORDS[idx], _font(64, bold=True), W // 2, H // 2, _mix(BG, FG, fade))
    d.rectangle([W // 2 - 90, int(H * 0.62), W // 2 + 90, int(H * 0.62) + 5], fill=ACCENT)
    return im


def frame_terminal(t: float, duration: float) -> Image.Image:
    """Fake terminal: a push command, then pipeline output arriving line by line."""
    im = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(im)

    pw, ph = int(W * 0.74), int(H * 0.62)
    x0, y0 = (W - pw) // 2, (H - ph) // 2
    d.rounded_rectangle([x0, y0, x0 + pw, y0 + ph], radius=18, fill=PANEL, outline=LINE, width=3)
    d.rectangle([x0 + 3, y0 + 3, x0 + pw - 3, y0 + 54], fill=(30, 36, 45))
    for i, color in enumerate(((246, 106, 98), (236, 190, 86), (99, 196, 112))):
        d.ellipse([x0 + 26 + i * 34, y0 + 20, x0 + 40 + i * 34, y0 + 34], fill=color)

    mono = _font(38, mono=True)
    per_line = duration / (len(TERMINAL_LINES) + 1.2)
    for i, text in enumerate(TERMINAL_LINES):
        start = i * per_line
        if t < start:
            break
        shown = text if t > start + per_line * 0.6 else text[: max(1, int(len(text) * (t - start) / (per_line * 0.6)))]
        ty = y0 + 100 + i * 66
        if i == 0:
            d.text((x0 + 40, ty), shown, font=mono, fill=FG)
        else:
            if t > start + per_line * 0.55:
                _check(d, x0 + 44, ty + 8, 26, ACCENT)
            d.text((x0 + 96, ty), shown, font=mono, fill=MUTED if i == 1 else FG)

    if int(t * 2) % 2 == 0:
        last = min(len(TERMINAL_LINES) - 1, int(t / per_line))
        d.rectangle([x0 + 40, y0 + 100 + last * 66 + 46, x0 + 62, y0 + 100 + last * 66 + 50], fill=ACCENT)
    return im


def frame_compare(t: float, duration: float) -> Image.Image:
    """Old manual workflow on the left, CI/CD on the right, items fading in."""
    im = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(im)

    d.line([(W // 2, int(H * 0.22)), (W // 2, int(H * 0.86))], fill=LINE, width=2)
    _centered(d, "Manual releases", _font(46, bold=True), int(W * 0.27), int(H * 0.2), WARN)
    _centered(d, "With CI/CD", _font(46, bold=True), int(W * 0.73), int(H * 0.2), ACCENT)

    item_font = _font(38)
    per_item = duration / (len(OLD_WAY) + 1.5)
    for i in range(len(OLD_WAY)):
        fade = _ease((t - i * per_item) / max(0.4, per_item * 0.8))
        if fade <= 0:
            continue
        y = int(H * 0.34) + i * 96
        _cross(d, int(W * 0.10), y + 6, 26, _mix(BG, WARN, fade))
        d.text((int(W * 0.14), y), OLD_WAY[i], font=item_font, fill=_mix(BG, MUTED, fade))
        _check(d, int(W * 0.56), y + 6, 28, _mix(BG, ACCENT, fade))
        d.text((int(W * 0.60), y), NEW_WAY[i], font=item_font, fill=_mix(BG, FG, fade))
    return im


def frame_benefits(t: float, duration: float) -> Image.Image:
    """Three benefit cards sliding up one after another."""
    im = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(im)
    _dots(d, 120, (t * 14) % 120)

    _centered(d, "Why teams rely on it", _font(52, bold=True), W // 2, int(H * 0.2), FG)

    card_w, card_h, gap = 440, 300, 70
    total = len(BENEFITS) * card_w + (len(BENEFITS) - 1) * gap
    x0 = (W - total) // 2
    per_card = duration / (len(BENEFITS) + 1.0)

    for i, (head, sub) in enumerate(BENEFITS):
        fade = _ease((t - i * per_card) / max(0.4, per_card * 0.9))
        if fade <= 0:
            continue
        x = x0 + i * (card_w + gap)
        y = int(H * 0.36) + int(40 * (1 - fade))
        d.rounded_rectangle([x, y, x + card_w, y + card_h], radius=24,
                            fill=_mix(BG, PANEL, fade), outline=_mix(BG, ACCENT, fade * 0.9), width=3)
        d.rectangle([x + 34, y + 42, x + 34 + int(70 * fade), y + 48], fill=_mix(BG, ACCENT, fade))
        d.text((x + 34, y + 84), head, font=_font(52, bold=True), fill=_mix(BG, FG, fade))
        d.text((x + 34, y + 164), sub, font=_font(32), fill=_mix(BG, MUTED, fade))
    return im


def frame_branches(t: float, duration: float) -> Image.Image:
    """Commit graph: a feature branch splits off main and merges back."""
    im = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(im)

    _centered(d, "Small changes, merged often", _font(50, bold=True), W // 2, int(H * 0.2), FG)

    main_y = int(H * 0.62)
    feat_y = int(H * 0.42)
    x_start, x_end = int(W * 0.12), int(W * 0.88)
    p = _ease(t / duration)
    head = x_start + int((x_end - x_start) * p)

    d.line([(x_start, main_y), (x_end, main_y)], fill=LINE, width=6)
    d.line([(x_start, main_y), (head, main_y)], fill=ACCENT, width=6)
    d.text((x_start - 10, main_y + 40), "main", font=_font(32, mono=True), fill=MUTED)

    split = x_start + int((x_end - x_start) * 0.25)
    merge = x_start + int((x_end - x_start) * 0.72)
    if head > split:
        tip = min(head, merge)
        d.line([(split, main_y), (split + 70, feat_y)], fill=ACCENT if head > split + 70 else LINE, width=5)
        d.line([(split + 70, feat_y), (max(split + 70, tip - 70), feat_y)], fill=ACCENT, width=5)
        if head > merge:
            d.line([(merge - 70, feat_y), (merge, main_y)], fill=ACCENT, width=5)
        d.text((split + 80, feat_y - 62), "feature", font=_font(32, mono=True), fill=MUTED)

    for i in range(7):
        cx = x_start + int((x_end - x_start) * (i / 6))
        if cx <= head:
            d.ellipse([cx - 13, main_y - 13, cx + 13, main_y + 13], fill=ACCENT)
            d.ellipse([cx - 6, main_y - 6, cx + 6, main_y + 6], fill=BG)
    for i in range(3):
        cx = split + 120 + i * 150
        if cx < min(head, merge - 80):
            d.ellipse([cx - 11, feat_y - 11, cx + 11, feat_y + 11], fill=ACCENT)
            d.ellipse([cx - 5, feat_y - 5, cx + 5, feat_y + 5], fill=BG)
    return im


def frame_yaml(t: float, duration: float) -> Image.Image:
    """A workflow file typing itself out."""
    im = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(im)

    pw, ph = int(W * 0.66), int(H * 0.72)
    x0, y0 = (W - pw) // 2, (H - ph) // 2
    d.rounded_rectangle([x0, y0, x0 + pw, y0 + ph], radius=18, fill=PANEL, outline=LINE, width=3)
    d.rectangle([x0 + 3, y0 + 3, x0 + pw - 3, y0 + 52], fill=(30, 36, 45))
    d.text((x0 + 26, y0 + 12), ".github/workflows/ci.yml", font=_font(28, mono=True), fill=MUTED)

    mono = _font(32, mono=True)
    total_chars = sum(len(line) for line in YAML_LINES) or 1
    budget = int(total_chars * min(1.0, t / (duration * 0.8)))

    for i, line in enumerate(YAML_LINES):
        if budget <= 0:
            break
        shown = line[:budget]
        budget -= len(line)
        color = ACCENT if shown.strip().startswith("- ") else FG
        d.text((x0 + 40, y0 + 80 + i * 48), shown, font=mono, fill=color)
        d.text((x0 - 46, y0 + 80 + i * 48), f"{i + 1:>2}", font=mono, fill=LINE)
    return im


def render(name: str, maker, duration: float, out_dir: Path, preview: bool) -> Path:
    if preview:
        path = out_dir / f"{name}.png"
        maker(duration * 0.7, duration).save(path)
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


def generate_broll(script_path="script_input.json", out="clips/generated", preview=False):
    title, subtitle = "CI/CD", "Explained Simply"
    path = Path(script_path)
    if path.exists():
        data = json.loads(path.read_text(encoding="utf-8"))
        raw = data.get("title", title)
        if "?" in raw:
            head, _, tail = raw.partition("?")
            title, subtitle = head.strip(" What is"), tail.strip() or subtitle
        else:
            title = raw

    out_dir = Path(out)
    out_dir.mkdir(parents=True, exist_ok=True)

    plan = [
        ("01_title", lambda t, d: frame_title(t, d, title, subtitle), 9.0),
        ("02_pipeline", frame_pipeline, 15.0),
        ("03_progress", frame_progress, 12.0),
        ("04_keywords", frame_keywords, 16.0),
        ("05_terminal", frame_terminal, 17.0),
        ("06_compare", frame_compare, 15.0),
        ("07_benefits", frame_benefits, 13.0),
        ("08_branches", frame_branches, 14.0),
        ("09_yaml", frame_yaml, 18.0),
    ]

    written = []
    for name, maker, duration in plan:
        written.append(render(name, maker, duration, out_dir, preview))
        print(f"wrote {written[-1]}")
    return written


def main():
    ap = argparse.ArgumentParser(description="Generate B-roll clips for the current script.")
    ap.add_argument("--script", default="script_input.json")
    ap.add_argument("--out", default="clips/generated")
    ap.add_argument("--preview", action="store_true", help="write PNG stills instead of mp4")
    args = ap.parse_args()
    generate_broll(script_path=args.script, out=args.out, preview=args.preview)


if __name__ == "__main__":
    main()
