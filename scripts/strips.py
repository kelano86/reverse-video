"""Dense frame strips for reading motion. Every frame across a short window, numbered, with a bar under
each one showing how much changed since the frame before. Point it at a moment the boards flagged (a
title flying in, a transition, a zoom, a graphic building) to read the duration in frames, the easing
and any overshoot.

Usage: python -I strips.py <workdir> <start>[,<start>...] [--dur 1.0] [--fps 0] [--crop x,y,w,h] [--width 200]
  start    seconds (12.4) or m:ss (0:12.4), the window's first frame
  --dur    window length in seconds (default 1.0)
  --fps    sampling rate; 0 = the video's own frame rate (default)
  --crop   a normalised region x,y,w,h (0-1) to zoom on one element
  --width  width of each frame in the sheet
Writes img/strip_<start>.jpg and prints a reading of the motion: when it starts, peaks and settles,
and whether the change is front-loaded (ease-out), back-loaded (ease-in), even (linear) or has a
second bump (overshoot or bounce)."""
import argparse
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import decode, even, font, probe  # noqa: E402

BG, INK, DIM = (20, 19, 18), (236, 232, 224), (150, 145, 138)


def secs(s):
    if ":" in s:
        m, x = s.split(":", 1)
        return int(m) * 60 + float(x)
    return float(s)


def reading(diff, fps):
    if len(diff) < 4 or diff.max() <= 0.002:
        return "no real motion in this window"
    pk = int(diff.argmax())
    thr = 0.12 * diff.max()
    act = np.where(diff > thr)[0]
    a, b = int(act[0]), int(act[-1])
    span = diff[a:b + 1]
    n = len(span)
    third = max(1, n // 3)
    first, last = span[:third].sum(), span[-third:].sum()
    if n <= 2:
        shape = "a single-frame change (a cut or a pop)"
    elif first > 1.6 * last:
        shape = "front-loaded: fast start, slow settle (ease-out)"
    elif last > 1.6 * first:
        shape = "back-loaded: slow start, fast finish (ease-in)"
    else:
        shape = "even: ease-in-out or linear"
    # a second bump after the main one, separated by a dip, reads as overshoot or bounce
    bumps = [i for i in range(a + 1, b) if diff[i] > diff[i - 1] and diff[i] >= diff[i + 1] and diff[i] > 0.3 * diff.max()]
    extra = " Second bump after the peak: overshoot/settle or a bounce." if len([x for x in bumps if x > pk + 1]) else ""
    return (f"motion from f{a} to f{b} ({(b - a + 1) / fps:.2f}s, {b - a + 1} frames), peak at f{pk}; {shape}.{extra}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("workdir")
    ap.add_argument("starts")
    ap.add_argument("--dur", type=float, default=1.0)
    ap.add_argument("--fps", type=float, default=0)
    ap.add_argument("--crop", default=None)
    ap.add_argument("--width", type=int, default=200)
    a = ap.parse_args()
    wd = Path(a.workdir)
    mp4 = wd / "video.mp4"
    P = probe(mp4)
    fps = a.fps or P["fps"] or 30
    W, H = P["width"], P["height"]
    crop = ""
    cw, ch = W, H
    if a.crop:
        x, y, w, h = [float(v) for v in a.crop.split(",")]
        cw, ch = even(w * W), even(h * H)
        crop = f"crop={cw}:{ch}:{int(x * W)}:{int(y * H)},"
    fw = a.width
    fh = even(fw * ch / cw)
    (wd / "img").mkdir(exist_ok=True)
    for s in a.starts.split(","):
        t0 = secs(s)
        frames = list(decode(mp4, f"fps={fps},{crop}scale={fw}:{fh}:flags=lanczos", fw, fh, "rgb24", ss=t0, t=a.dur))
        if not frames:
            print(f"{s}: no frames")
            continue
        g = [f.astype(np.float32).mean(2) for f in frames]
        diff = np.array([0.0] + [float(np.abs(g[i] - g[i - 1]).mean() / 255) for i in range(1, len(g))])
        text = reading(diff, fps)
        cols = 10 if fw <= 220 else 6
        bar_h, lab_h, pad = 30, 22, 6
        rows = (len(frames) + cols - 1) // cols
        Wd = cols * (fw + pad) + pad
        Hd = 70 + rows * (fh + bar_h + lab_h + pad) + pad
        im = Image.new("RGB", (Wd, Hd), BG)
        d = ImageDraw.Draw(im)
        d.text((pad, 8), f"{s} + {a.dur:g}s at {fps:g} fps" + (f", crop {a.crop}" if a.crop else ""), fill=INK, font=font(18, True))
        d.text((pad, 34), text, fill=DIM, font=font(14))
        mx = max(diff.max(), 1e-6)
        for i, fr in enumerate(frames):
            x = pad + (i % cols) * (fw + pad)
            y = 70 + (i // cols) * (fh + bar_h + lab_h + pad)
            im.paste(Image.fromarray(fr), (x, y))
            bh = int(diff[i] / mx * (bar_h - 4))
            d.rectangle([x, y + fh + bar_h - bh, x + fw - 1, y + fh + bar_h], fill=(240, 180, 60))
            d.text((x + 2, y + fh + bar_h + 3), f"f{i}  +{i / fps:.2f}s", fill=INK, font=font(13))
        out = wd / "img" / f"strip_{t0:07.2f}s.jpg".replace(":", "-")
        im.save(out, quality=88)
        print(f"{out}: {text}")


if __name__ == "__main__":
    main()
