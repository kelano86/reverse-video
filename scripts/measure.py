"""Measure what a video's style is made of: format, shots and cuts, camera moves, framing, colour,
on-screen text, speech, music, sound effects and pacing. Everything a number can settle is settled
here, so the teardown argues from measurements rather than impressions.

Usage: python -I measure.py <workdir> [--stems auto|on|off] [--ocr auto|off] [--model medium]
                            [--lang en] [--vad] [--force]

<workdir> holds video.mp4 and meta.json from fetch.py. Writes into it:
  measures.json      every number (the source for summary.md and style.json)
  summary.md         the hard numbers, readable
  transcript.txt     the words with [#n] where shot n starts (work/ only: third-party text)
  onscreen_text.txt  every piece of on-screen text with its time and place
  img/               pacing map, shot boards, contact sheets, hook sheet, palette, text crops
  cache/             intermediate files (safe to delete)
Each step is cached; --force redoes them all."""
import argparse
import math
import os
import re
import sys
import time
import urllib.request
from bisect import bisect_left, bisect_right
from collections import Counter
from pathlib import Path

os.environ.setdefault("OPENCV_LOG_LEVEL", "ERROR")  # before cv2: hides a harmless DNN backend notice
import cv2
import numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import (audio_array, decode, even, find_demucs, font, hexcol, load, log, probe, run,  # noqa: E402
                    save, tc)

ap = argparse.ArgumentParser()
ap.add_argument("workdir")
ap.add_argument("--stems", default="auto", choices=["auto", "on", "off"])
ap.add_argument("--ocr", default="auto", choices=["auto", "off"])
ap.add_argument("--model", default="medium")
ap.add_argument("--lang", default=None)
ap.add_argument("--vad", action="store_true", help="Whisper voice-activity filter (off by default)")
ap.add_argument("--force", action="store_true")
args = ap.parse_args()

WD = Path(args.workdir).resolve()
MP4 = WD / "video.mp4"
C = WD / "cache"
IMG = WD / "img"
FR = WD / "frames"
for d in (C, IMG, FR):
    d.mkdir(parents=True, exist_ok=True)
ERR = []
T0 = time.time()

YUNET = Path.home() / ".cache" / "reverse-video" / "models" / "yunet.onnx"
YUNET_URL = "https://github.com/opencv/opencv_zoo/raw/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx"

CUT_COL = {"new": (235, 235, 235), "jump": (240, 180, 60), "punch": (80, 200, 230), "transition": (220, 90, 200),
           "start": (120, 120, 120)}
BG = (20, 19, 18)
INK = (236, 232, 224)
DIM = (150, 145, 138)


def cached(name):
    p = C / name
    return None if args.force else load(p)


def step(name):
    log(f"[{time.time() - T0:6.1f}s] {name}")


# ---------------------------------------------------------------- probe
P = probe(MP4)
META = load(WD / "meta.json", {}) or {}
FPS = P["fps"] if 10 <= P["fps"] <= 120 else 30.0
DUR = P["duration"]
VERT = P["height"] > P["width"]
R2 = 4 if DUR <= 90 else 2 if DUR <= 300 else 1          # frames/ rate
if VERT:
    W2, H2 = 540, even(540 * P["height"] / P["width"])
else:
    W2, H2 = even(540 * P["width"] / P["height"]), 540
W1 = 160
H1 = even(W1 * P["height"] / P["width"])


# ---------------------------------------------------------------- pass 1: every frame, small
def pass1():
    p1 = C / "pass1.npz"
    if p1.exists() and (C / "gray160.npy").exists() and not args.force:
        z = np.load(p1)
        return z["d"], z["hd"], z["luma"], int(z["n"])
    step("pass 1: every frame at 160 px (cuts, motion)")
    n_est = int(math.ceil(DUR * FPS)) + 30
    mm = np.lib.format.open_memmap(C / "gray160.npy", mode="w+", dtype=np.uint8, shape=(n_est, H1, W1))
    d, hd, luma = [], [], []
    prev = prevh = None
    n = 0
    for fr in decode(MP4, f"fps={FPS},scale={W1}:{H1}:flags=area", W1, H1, "rgb24"):
        if n >= n_est:
            break
        g = (fr[..., 0] * 0.2126 + fr[..., 1] * 0.7152 + fr[..., 2] * 0.0722).astype(np.uint8)
        mm[n] = g
        q = (fr >> 5).astype(np.int32)
        h = np.bincount((q[..., 0] * 64 + q[..., 1] * 8 + q[..., 2]).ravel(), minlength=512).astype(np.float32)
        h /= h.sum()
        gi = g.astype(np.int16)
        if prev is None:
            d.append(0.0)
            hd.append(0.0)
        else:
            d.append(float(np.abs(gi - prev).mean() / 255))
            hd.append(float(0.5 * np.abs(h - prevh).sum()))
        luma.append(float(g.mean() / 255))
        prev, prevh = gi, h
        n += 1
    mm.flush()
    del mm
    d, hd, luma = np.array(d), np.array(hd), np.array(luma)
    np.savez(p1, d=d, hd=hd, luma=luma, n=n)
    return d, hd, luma, n


D, HD, LUMA, N = pass1()
G = np.load(C / "gray160.npy", mmap_mode="r")


# ---------------------------------------------------------------- real frame rate
def real_fps():
    """Frames a second that carry new content. A 25 fps recording rendered at 60 repeats most frames;
    judged where there's movement (mean difference around the frame), so still stretches don't count."""
    if N < 20:
        return FPS
    w = max(5, int(FPS / 2))
    act = np.convolve(D, np.ones(2 * w + 1) / (2 * w + 1), mode="same")
    moving = act > 0.004
    if moving.sum() < FPS:
        return FPS
    dup = (D < 0.002) & moving
    return round(FPS * (1 - dup.sum() / moving.sum()), 1)


REAL_FPS = real_fps()
JUDDER = REAL_FPS < 0.8 * FPS
if JUDDER:
    ERR.append(f"many frames repeat the one before (new content averages ~{REAL_FPS} fps in a {FPS:g} fps file: footage "
               "shot at a lower frame rate, maybe with graphics at the full rate): cuts were judged against the other "
               "new frames only, so jump cuts inside a talking-head shot can't be told from movement and may be "
               "missed; layout and shot changes are counted")


def ecc(a, b, inits=(1.0,), iters=50):
    """Affine ECC from frame a to frame b. Returns (cc, scale, shift_x, shift_y, warp); scale > 1 = b is tighter."""
    A = np.asarray(a, np.float32) / 255
    B = np.asarray(b, np.float32) / 255
    h, w = A.shape
    cx, cy = w / 2, h / 2
    best = None
    for s0 in inits:
        warp = np.array([[s0, 0, (1 - s0) * cx], [0, s0, (1 - s0) * cy]], np.float32)
        try:
            cc, warp = cv2.findTransformECC(A, B, warp, cv2.MOTION_AFFINE,
                                            (cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, iters, 1e-5), None, 5)
        except cv2.error:
            continue
        if best is None or cc > best[0]:
            best = (cc, warp)
    if best is None:
        return None
    cc, warp = best
    s = math.sqrt(abs(np.linalg.det(warp[:, :2])))
    x2, y2 = warp @ np.array([cx, cy, 1.0])
    return float(cc), float(s), float((x2 - cx) / w), float((y2 - cy) / h), warp


# ---------------------------------------------------------------- cuts
def detect_cuts():
    c = cached("cuts.json")
    if c is not None:
        return c
    step("cuts and transitions")
    s = D * 2.0 + HD
    from numpy.lib.stride_tricks import sliding_window_view
    k = 3.5
    if JUDDER:
        # most frames repeat, so the median difference is ~0 and ordinary movement would read as a cut:
        # judge each new frame against the other new frames (tested on a 25-in-60 fps talking-head reel)
        idx = np.where(D >= 0.002)[0]
        wd = max(5, int(round(REAL_FPS * 0.4)))
        bd = np.median(sliding_window_view(np.pad(s[idx], (wd, wd), mode="edge"), 2 * wd + 1), axis=1)
        base = np.interp(np.arange(N), idx, bd)
        k = 2.5
    else:
        win = max(5, int(round(FPS * 0.4)))
        base = np.median(sliding_window_view(np.pad(s, (win, win), mode="edge"), 2 * win + 1), axis=1)
    cand = []
    for t in range(1, N):
        if s[t] < 0.06:
            continue
        hard = s[t] >= 0.5 and HD[t] >= 0.25
        rel = s[t] > k * base[t] + 0.03 and D[t] > 0.02
        if not (hard or rel):
            continue
        if s[t] < s[max(1, t - 2):min(N, t + 3)].max():
            continue
        cand.append(t)
    cuts = []
    for t in cand:
        lim = max(0.5 * s[t], 3 * base[t] + 0.02)
        a = t
        while a - 1 > 0 and s[a - 1] > lim:
            a -= 1
        b = t
        while b + 1 < N and s[b + 1] > lim:
            b += 1
        if cuts and a <= cuts[-1]["f_end"] + 1:
            if s[t] > s[cuts[-1]["f"]]:
                cuts[-1]["f"] = t
            cuts[-1]["f_end"] = max(cuts[-1]["f_end"], b)
            continue
        cuts.append({"f": t, "f_start": a, "f_end": b})
    out = []
    for c_ in cuts:
        t, a, b = c_["f"], c_["f_start"], c_["f_end"]
        span = b - a + 1
        before, after = G[max(0, a - 1)], G[min(N - 1, b + 1)]
        kind, zoom, cc = "new", None, None
        if span >= 3:
            kind = "transition"
        if HD[t] < 0.6 or span >= 3:
            r = ecc(before, after, inits=(1.0, 1.12, 1.25, 1 / 1.12, 1 / 1.25), iters=60)
            if r is not None:
                cc = r[0]
                if cc >= 0.78:
                    zoom = r[1]
                    if span < 3:
                        kind = "punch" if abs(math.log(r[1])) >= math.log(1.06) else "jump"
        flash = bool(LUMA[a:b + 1].max() > 0.85 and LUMA[max(0, a - 1)] < 0.7) if span <= 6 else False
        out.append({"t": round(t / FPS, 3), "frame": t, "frames": span, "type": kind,
                    "zoom": round(zoom, 3) if zoom else None, "match": round(cc, 3) if cc is not None else None,
                    "score": round(float(s[t]), 3), "flash": flash})
    # region cuts: changes confined to the top or bottom half (split layouts)
    reg = {"top_only": 0, "bottom_only": 0}
    cut_frames = {c_["frame"] for c_ in out}
    half = H1 // 2
    prev = None
    for t in range(0, N, 1):
        g = np.asarray(G[t], np.int16)
        if prev is not None and t not in cut_frames:
            dt = np.abs(g[:half] - prev[:half]).mean() / 255
            db_ = np.abs(g[half:] - prev[half:]).mean() / 255
            if dt > 0.12 and db_ < 0.02:
                reg["top_only"] += 1
            elif db_ > 0.12 and dt < 0.02:
                reg["bottom_only"] += 1
        prev = g
    c = {"cuts": out, "region": reg}
    save(C / "cuts.json", c)
    return c


CUTS = detect_cuts()
CUT_T = [c["t"] for c in CUTS["cuts"]]


def shots_from_cuts():
    starts = [0.0] + [c["t"] for c in CUTS["cuts"]]
    types = ["start"] + [c["type"] for c in CUTS["cuts"]]
    zooms = [None] + [c["zoom"] for c in CUTS["cuts"]]
    sh = []
    for i, st in enumerate(starts):
        en = starts[i + 1] if i + 1 < len(starts) else DUR
        if en - st <= 0:
            continue
        sh.append({"n": len(sh) + 1, "start": round(st, 3), "end": round(en, 3), "dur": round(en - st, 3),
                   "cut_in": types[i], "zoom_in": zooms[i]})
    return sh


SHOTS = shots_from_cuts()


def shot_at(t):
    i = bisect_right([s["start"] for s in SHOTS], t) - 1
    return SHOTS[max(0, i)]




# ---------------------------------------------------------------- camera
def camera():
    c = cached("camera.json")
    if c is not None:
        return c
    rate = 10 if DUR <= 180 else 5
    k = max(1, int(round(FPS / rate)))
    step(f"camera moves (ECC every {k} frames)")
    cf = sorted(c_["frame"] for c_ in CUTS["cuts"])
    spans = [(c_["frame"] - c_["frames"], c_["frame"] + c_["frames"]) for c_ in CUTS["cuts"]]
    steps = []
    m = int(0.08 * W1)
    for i in range(k, N, k):
        j = bisect_left(cf, i - k + 1)
        if j < len(cf) and cf[j] <= i:
            continue
        if any(a <= i <= b for a, b in spans):
            continue
        if D[i - k + 1:i + 1].max() < 0.002:
            steps.append([round(i / FPS, 3), 1.0, 0.0, 0.0, 0.0, 1.0])
            continue
        r = ecc(G[i - k], G[i], iters=40)
        if r is None:
            continue
        cc, s, tx, ty, warp = r
        al = cv2.warpAffine(np.asarray(G[i], np.float32), warp, (W1, H1), flags=cv2.INTER_LINEAR | cv2.WARP_INVERSE_MAP)
        res = float(np.abs(al[m:-m, m:-m] - np.asarray(G[i - k], np.float32)[m:-m, m:-m]).mean() / 255)
        steps.append([round(i / FPS, 3), round(s, 5), round(tx, 5), round(ty, 5), round(res, 5), round(cc, 4)])
    dt = k / FPS
    per = []
    for sh in SHOTS:
        st = [x for x in steps if sh["start"] < x[0] <= sh["end"]]
        if len(st) < 3 or sh["dur"] < 0.6:
            per.append({"n": sh["n"], "move": "too short"})
            continue
        good = [x for x in st if x[5] >= 0.7]
        if len(good) < 3:
            per.append({"n": sh["n"], "move": "untracked"})
            continue
        ls = np.array([math.log(x[1]) for x in good])
        tx = np.array([x[2] for x in good])
        ty = np.array([x[3] for x in good])
        res = np.array([x[4] for x in good])
        span = len(good) * dt
        zoom_rate = (math.exp(ls.sum() / span) - 1) * 100            # % per second
        pan = float(np.hypot(tx.sum(), ty.sum()) / span) * 100       # % of frame width per second
        jit = float(np.hypot(np.diff(tx).std(), np.diff(ty).std())) * 100 if len(tx) > 3 else 0.0
        snaps = [x[0] for x in good if abs(math.log(x[1])) >= math.log(1.04) and x[5] >= 0.85]
        if jit > 0.35:  # a person holding the camera: its zooms are moves, not edit decisions
            move = "handheld" + (" push/pull" if abs(zoom_rate) > 2 or snaps else "")
            snaps = []
        elif snaps:
            move = "snap zoom"
        elif zoom_rate > 0.6:
            move = "push in"
        elif zoom_rate < -0.6:
            move = "pull out"
        elif pan > 2.0:
            move = "pan/slide"
        elif jit > 0.35:
            move = "handheld"
        else:
            move = "locked"
        per.append({"n": sh["n"], "move": move, "zoom_pct_s": round(zoom_rate, 2), "pan_pct_s": round(pan, 2),
                    "jitter": round(jit, 3), "element_motion": round(float(res.mean()), 4), "snaps": snaps})
    c = {"rate": rate, "steps": steps, "shots": per}
    save(C / "camera.json", c)
    return c


# ---------------------------------------------------------------- frames on disk
def dump_frames():
    have = sorted(FR.glob("*.jpg"))
    expect = int(DUR * R2)
    if have and abs(len(have) - expect) <= 2 and not args.force:
        return have
    step(f"frames at {R2} fps, {W2}x{H2}")
    for p in have:
        p.unlink()
    run(["ffmpeg", "-y", "-v", "error", "-i", MP4, "-vf", f"fps={R2},scale={W2}:{H2}:flags=lanczos", "-q:v", "3",
         FR / "%05d.jpg"])
    hk = WD / "hook"
    hk.mkdir(exist_ok=True)
    for p in hk.glob("*.jpg"):
        p.unlink()
    run(["ffmpeg", "-y", "-v", "error", "-i", MP4, "-t", f"{min(5.0, DUR):.2f}", "-vf",
         f"fps=10,scale={even(W2 * 0.6)}:{even(H2 * 0.6)}", "-q:v", "3", hk / "%03d.jpg"])
    return sorted(FR.glob("*.jpg"))


def ftime(i):
    return i / R2


# ---------------------------------------------------------------- colour
def colour(frames):
    c = cached("colour.json")
    if c is not None:
        return c
    step("colour and palette")
    rng = np.random.default_rng(7)
    per, samples, owners = [], [], []
    for i, p in enumerate(frames):
        im = cv2.imread(str(p))
        if im is None:
            continue
        sm = cv2.resize(im, (64, max(2, int(64 * im.shape[0] / im.shape[1]))), interpolation=cv2.INTER_AREA)
        rgb = sm[..., ::-1].astype(np.float32)
        y = rgb[..., 0] * 0.2126 + rgb[..., 1] * 0.7152 + rgb[..., 2] * 0.0722
        hsv = cv2.cvtColor(sm, cv2.COLOR_BGR2HSV)
        border = np.concatenate([rgb[:3].reshape(-1, 3), rgb[-3:].reshape(-1, 3), rgb[:, :3].reshape(-1, 3),
                                 rgb[:, -3:].reshape(-1, 3)])
        per.append({"t": round(ftime(i), 2), "mean": hexcol(rgb.reshape(-1, 3).mean(0)),
                    "ground": hexcol(np.median(border, 0)), "luma": round(float(y.mean() / 255), 3),
                    "black": round(float(np.percentile(y, 3) / 255), 3), "white": round(float(np.percentile(y, 97) / 255), 3),
                    "sat": round(float(hsv[..., 1].mean() / 255), 3),
                    "warmth": round(float((rgb[..., 0] - rgb[..., 2]).mean() / 255), 3)})
        flat = (sm.reshape(-1, 3).astype(np.float32) / 255)
        pick = rng.choice(len(flat), size=min(300, len(flat)), replace=False)
        samples.append(flat[pick])
        owners += [len(per) - 1] * len(pick)
    S = np.concatenate(samples)
    lab = cv2.cvtColor(S.reshape(-1, 1, 3), cv2.COLOR_BGR2Lab).reshape(-1, 3)
    K = 8
    _, labels, centers = cv2.kmeans(lab.astype(np.float32), K, None,
                                    (cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_MAX_ITER, 40, 0.5), 3, cv2.KMEANS_PP_CENTERS)
    labels = labels.ravel()
    bgr = cv2.cvtColor(centers.reshape(-1, 1, 3).astype(np.float32), cv2.COLOR_Lab2BGR).reshape(-1, 3)
    shares = np.bincount(labels, minlength=K) / len(labels)
    pal = []
    for k in np.argsort(-shares):
        L, a, b = centers[k]
        chroma = float(math.hypot(a, b))
        pal.append({"hex": hexcol(bgr[k][::-1] * 255), "share": round(float(shares[k]), 3),
                    "lightness": round(float(L), 1), "chroma": round(chroma, 1),
                    "role": "accent" if chroma > 35 and shares[k] < 0.15 else ("neutral" if chroma < 12 else "colour")})
    own = np.array(owners)
    for i in range(len(per)):
        lb = labels[own == i]
        if len(lb):
            per[i]["cluster"] = int(np.bincount(lb, minlength=K).argmax())
    lum = np.array([x["luma"] for x in per])
    c = {"palette": pal, "frames": per,
         "luma_mean": round(float(lum.mean()), 3), "luma_sd_between_frames": round(float(lum.std()), 3),
         "black_level": round(float(np.median([x["black"] for x in per])), 3),
         "white_level": round(float(np.median([x["white"] for x in per])), 3),
         "saturation": round(float(np.median([x["sat"] for x in per])), 3),
         "warmth": round(float(np.median([x["warmth"] for x in per])), 3),
         "dark_frames_pct": round(float((lum < 0.25).mean() * 100), 1),
         "light_frames_pct": round(float((lum > 0.65).mean() * 100), 1)}
    grounds = Counter(x["ground"] for x in per)
    c["common_grounds"] = [g for g, _ in grounds.most_common(6)]
    save(C / "colour.json", c)
    return c


# ---------------------------------------------------------------- faces
def faces(frames):
    c = cached("faces.json")
    if c is not None:
        return c
    step("faces (YuNet)")
    if not YUNET.exists():
        try:
            YUNET.parent.mkdir(parents=True, exist_ok=True)
            urllib.request.urlretrieve(YUNET_URL, YUNET)
        except Exception as e:
            ERR.append(f"faces: no YuNet model ({e})")
            return None
    det = cv2.FaceDetectorYN.create(str(YUNET), "", (W2, H2), 0.7, 0.3, 5000)
    short = min(W2, H2)
    per = []
    for i, p in enumerate(frames):
        im = cv2.imread(str(p))
        if im is None:
            continue
        det.setInputSize((im.shape[1], im.shape[0]))
        _, f = det.detect(im)
        if f is None or not len(f):
            per.append({"t": round(ftime(i), 2), "n": 0})
            continue
        big = max(f, key=lambda r: r[2] * r[3])
        x, y, w, h = [float(v) for v in big[:4]]
        eye_y = float((big[5] + big[7]) / 2)
        per.append({"t": round(ftime(i), 2), "n": int(len(f)), "cx": round((x + w / 2) / im.shape[1], 3),
                    "cy": round((y + h / 2) / im.shape[0], 3), "eye_y": round(eye_y / im.shape[0], 3),
                    "h_short": round(h / short, 3), "w": round(w / im.shape[1], 3)})
    c = {"frames": per}
    save(C / "faces.json", c)
    return c


def size_class(hs):
    if hs is None:
        return None
    return ("extreme close-up" if hs >= 0.6 else "close-up" if hs >= 0.38 else "medium close-up" if hs >= 0.22
            else "medium" if hs >= 0.12 else "wide")


# ---------------------------------------------------------------- on-screen text
def ocr(frames):
    c = cached("ocr.json")
    if c is not None:
        return c
    if args.ocr == "off":
        return None
    try:
        from rapidocr_onnxruntime import RapidOCR
    except Exception as e:
        ERR.append(f"ocr: rapidocr not installed ({e})")
        return None
    every = max(1, math.ceil(len(frames) / 400))
    pick = list(range(0, len(frames), every))
    step(f"on-screen text (OCR on {len(pick)} frames)")
    eng = RapidOCR()
    per = []
    for i in pick:
        im = cv2.imread(str(frames[i]))
        try:
            res, _ = eng(im, use_cls=False)
        except Exception as e:
            ERR.append(f"ocr frame {i}: {e}")
            res = None
        boxes = []
        for box, text, score in res or []:
            score = float(score)
            text = str(text).strip()
            if score < 0.6 or not text:
                continue
            xs = [pt[0] for pt in box]
            ys = [pt[1] for pt in box]
            boxes.append({"text": text, "score": round(score, 2),
                          "x0": round(min(xs) / im.shape[1], 4), "x1": round(max(xs) / im.shape[1], 4),
                          "y0": round(min(ys) / im.shape[0], 4), "y1": round(max(ys) / im.shape[0], 4)})
        per.append({"t": round(ftime(i), 2), "i": i, "boxes": boxes})
    c = {"frames": per, "step_s": every / R2}
    save(C / "ocr.json", c)
    return c


def norm_text(s):
    return re.sub(r"[^A-Z0-9]+", " ", s.upper()).strip()


def text_events(oc):
    """Merge per-frame OCR boxes into events: the same text in about the same place across frames."""
    if not oc:
        return [], None
    capbox = []
    for fr in oc["frames"]:
        for b in fr["boxes"]:
            h = b["y1"] - b["y0"]
            cx = (b["x0"] + b["x1"]) / 2
            if h >= 0.022 and len(b["text"].split()) <= 7 and abs(cx - 0.5) < 0.2:
                capbox.append((b["y0"] + b["y1"]) / 2)
    band = None
    if len(capbox) >= max(3, len(oc["frames"]) * 0.15):
        hist, edges = np.histogram(capbox, bins=20, range=(0, 1))
        k = int(hist.argmax())
        band = (max(0.0, edges[k] - 0.05), min(1.0, edges[k + 1] + 0.05))
    open_ev, events = {}, []
    dt = oc.get("step_s", 1 / R2)
    for fi, fr in enumerate(oc["frames"]):
        seen = set()
        rows = {}
        for b in fr["boxes"]:
            cy = (b["y0"] + b["y1"]) / 2
            in_band = band is not None and band[0] <= cy <= band[1]
            key = ("CAP" if in_band else f"{round(cy * 10)}") + "|" + norm_text(b["text"])
            if in_band:  # a caption is everything in the band on this frame, read top to bottom
                rows.setdefault("CAP", []).append(b)
                continue
            rows[key] = [b]
        for key, bs in rows.items():
            bs = sorted(bs, key=lambda b: (round(b["y0"], 2), b["x0"]))
            text = " ".join(b["text"] for b in bs)
            k2 = (key if key != "CAP" else "CAP|" + norm_text(text))
            if not norm_text(text):
                continue
            seen.add(k2)
            box = {"x0": min(b["x0"] for b in bs), "x1": max(b["x1"] for b in bs),
                   "y0": min(b["y0"] for b in bs), "y1": max(b["y1"] for b in bs),
                   "h": float(np.median([b["y1"] - b["y0"] for b in bs])), "lines": len({round(b["y0"], 2) for b in bs})}
            if k2 in open_ev:
                open_ev[k2]["end"] = fr["t"] + dt
                open_ev[k2]["last"] = fi
            else:
                open_ev[k2] = {"start": fr["t"], "end": fr["t"] + dt, "text": text, "caption": key == "CAP",
                               "box": box, "last": fi, "frame": fr.get("i", fi)}
        for k2 in list(open_ev):
            if k2 not in seen and fi - open_ev[k2]["last"] > 1:
                events.append(open_ev.pop(k2))
    events += open_ev.values()
    for e in events:
        h = e["box"]["h"]
        e["kind"] = "caption" if e["caption"] else ("title" if h >= 0.035 and len(e["text"]) <= 40 else "ui/small" if h < 0.018 else "text")
        e["start"], e["end"] = round(e["start"], 2), round(e["end"], 2)
        for k in ("x0", "x1", "y0", "y1", "h"):
            e["box"][k] = round(e["box"][k], 4)
        e.pop("last", None)
    events.sort(key=lambda e: e["start"])
    return events, band


def glyph_pixels(im, b, out):
    """Pixels that differ from the box's surround: the text fill plus any stroke, shadow or highlight."""
    H, W = im.shape[:2]
    x0, x1 = int(b["x0"] * W), int(math.ceil(b["x1"] * W))
    y0, y1 = int(b["y0"] * H), int(math.ceil(b["y1"] * H))
    cr = im[max(0, y0 - 3):y1 + 3, max(0, x0 - 3):x1 + 3].astype(np.float32)
    if cr.shape[0] < 6 or cr.shape[1] < 6:
        return
    flat = cr.reshape(-1, 3)
    bg = np.median(np.concatenate([cr[0], cr[-1], cr[:, 0], cr[:, -1]]), 0)
    fg = flat[np.linalg.norm(flat - bg, axis=1) > 70]
    if len(fg) > 20:
        out.append(fg[np.random.default_rng(1).choice(len(fg), size=min(400, len(fg)), replace=False)])


def letter_height(crops):
    """Median height of the letters in px at 1080 wide, measured from the pixels inside each caption box,
    so it doesn't depend on how loosely the OCR draws its boxes. Rows through letters have many sharp
    left-right edges; a plate, its border or the picture behind have few. For all-caps captions this is
    the cap height; for mixed case it runs from ascender to descender."""
    hs = []
    for im, b in crops[:120]:
        H, W = im.shape[:2]
        x0, x1 = int(b["x0"] * W), int(math.ceil(b["x1"] * W))
        y0, y1 = int(b["y0"] * H), int(math.ceil(b["y1"] * H))
        cr = im[max(0, y0 - 3):y1 + 3, max(0, x0 - 3):x1 + 3].astype(np.float32)
        if cr.shape[0] < 8 or cr.shape[1] < 8:
            continue
        g = cr.mean(2) if cr.ndim == 3 else cr
        cnt = (np.abs(np.diff(g, axis=1)) > 60).sum(1)
        if cnt.max() < 6:
            continue
        rows = np.where(cnt >= 0.3 * cnt.max())[0]
        runs = np.split(rows, np.where(np.diff(rows) > 2)[0] + 1)
        r = max(runs, key=len)
        hs.append((r[-1] - r[0] + 1) * 1080 / W)
    return round(float(np.median(hs))) if len(hs) >= 3 else None


def text_colours(events, frames, crops=None):
    """Pixel colours of the caption glyphs (fill, stroke or shadow, highlight), pooled across captions.
    crops: [(image, box)] from the caption pass, at full resolution; otherwise read from frames/."""
    pix = []
    if crops:
        for im, b in crops[:120]:
            glyph_pixels(im, b, pix)
    else:
        for e in [e for e in events if e["kind"] == "caption"][:80]:
            im = cv2.imread(str(frames[min(len(frames) - 1, e["frame"])]))
            if im is not None:
                glyph_pixels(im, e["box"], pix)
    if not pix:
        return None
    X = np.concatenate(pix).astype(np.float32)
    k = 4 if len(X) > 2000 else 3 if len(X) > 300 else 2
    _, lab, cen = cv2.kmeans(X, k, None, (cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_MAX_ITER, 30, 1.0), 3,
                             cv2.KMEANS_PP_CENTERS)
    sh = np.bincount(lab.ravel(), minlength=k) / len(lab)
    return [{"hex": hexcol(cen[i][::-1]), "share": round(float(sh[i]), 3)} for i in np.argsort(-sh)]


LET = re.compile(r"[^A-Z0-9]")


def match_words(text, t0, t1, sp_words):
    """How many spoken words a caption holds, and when the first of them is spoken. OCR often drops the
    spaces in caption text, so match the caption's letters against the transcript instead of splitting."""
    letters = LET.sub("", text.upper())
    if not letters:
        return 0, None
    cand = [w for w in sp_words if t0 - 1.5 <= w["s"] <= t1 + 1.0]
    best = None
    for i in range(len(cand)):
        acc = ""
        for j in range(i, len(cand)):
            acc += LET.sub("", cand[j]["w"].upper())
            if acc == letters:
                cnt = (j - i + 1, cand[i]["s"])
                if best is None or abs(cand[i]["s"] - t0) < abs(best[1] - t0):
                    best = cnt
                break
            if len(acc) >= len(letters) or not letters.startswith(acc):
                break
    if best:
        return best
    n = len(text.split())
    return (n if n > 1 or len(letters) <= 8 else max(1, round(len(letters) / 4.7))), None


def captions_precise(band, sp_words):
    """Frame-accurate caption track: watch the caption band for pixel changes at every frame, then read
    one frame per stable stretch. Gives exact hold times, words per caption and sync with the voice."""
    c = cached("captions.json")
    if c is not None:
        return c["events"], c["metrics"], None
    try:
        from rapidocr_onnxruntime import RapidOCR
    except Exception:
        return None, None, None
    from difflib import SequenceMatcher
    rate_c = 8 if DUR <= 180 else 4 if DUR <= 600 else 2
    k = max(1, int(round(FPS / rate_c)))
    step(f"caption track: band read {rate_c}x a second, edges found to the frame")
    Hf, Wf = P["height"], P["width"]
    y0 = int(band[0] * Hf) // 2 * 2
    hb = min(even((band[1] - band[0]) * Hf), (Hf - y0) // 2 * 2)
    Wc = 240
    Hc = even(Wc * hb / Wf)
    d, prev = [], None
    for g in decode(MP4, f"fps={FPS},crop={Wf}:{hb}:0:{y0},scale={Wc}:{Hc}:flags=area", Wc, Hc, "gray"):
        gi = g.astype(np.int16)
        d.append(0.0 if prev is None else float(np.abs(gi - prev).mean() / 255))
        prev = gi
    d = np.array(d)
    n = len(d)
    if n < 4:
        return None, None, None
    out = C / "capband"
    out.mkdir(exist_ok=True)
    for p_ in out.glob("*.jpg"):
        p_.unlink()
    Hs = even(720 * hb / Wf)
    flt = out / "_filter.txt"
    flt.write_text(f"fps={FPS},select='not(mod(n,{k}))',crop={Wf}:{hb}:0:{y0},scale=720:{Hs}:flags=area", encoding="utf-8")
    run(["ffmpeg", "-y", "-v", "error", "-i", MP4, "-/filter:v", flt, "-fps_mode", "passthrough", "-q:v", "2", out / "%05d.jpg"])
    files = sorted(out.glob("*.jpg"))
    eng = RapidOCR(det_limit_side_len=736, det_limit_type="max", det_model_path=None)
    samples, crops = [], []
    for i, f in enumerate(files):
        im = cv2.imread(str(f))
        if im is None:
            continue
        res, _ = eng(im, use_cls=False)
        bs = []
        for box, text, score in res or []:
            text = str(text).strip()
            if float(score) < 0.6 or not text:
                continue
            xs = [p_[0] for p_ in box]
            ys = [p_[1] for p_ in box]
            bb = {"text": text, "x0": min(xs) / im.shape[1], "x1": max(xs) / im.shape[1],
                  "y0": min(ys) / im.shape[0], "y1": max(ys) / im.shape[0]}
            if (bb["y1"] - bb["y0"]) * hb / Hf >= 0.015:
                bs.append(bb)
        samples.append({"f": min(n - 1, i * k), "raw": bs, "im": im if i % 3 == 0 else None})
    # keep caption-like boxes only: about the captions' usual height and centred, so screen text that
    # drifts into the band (a zoomed screen recording, a sign) isn't read as a caption
    cent = [b for s_ in samples for b in s_["raw"] if abs((b["x0"] + b["x1"]) / 2 - 0.5) < 0.12]
    capH = float(np.median([b["y1"] - b["y0"] for b in cent])) if cent else None
    lettered = [b["text"] for b in cent if re.search("[A-Za-z]", b["text"])]
    upper_style = bool(lettered) and sum(1 for t in lettered if t == t.upper()) / len(lettered) >= 0.8
    for s_ in samples:
        bs = [b for b in s_["raw"] if capH is None or (abs((b["y1"] - b["y0"]) - capH) <= 0.4 * capH
                                                      and abs((b["x0"] + b["x1"]) / 2 - 0.5) < 0.25
                                                      and not (upper_style and b["text"] != b["text"].upper()))]
        bs.sort(key=lambda x: (round(x["y0"], 1), x["x0"]))
        text = " ".join(x["text"] for x in bs)
        s_.update(key=LET.sub("", text.upper()), text=text, boxes=bs)
        if bs and s_["im"] is not None and len(crops) < 80:
            crops += [(s_["im"], x) for x in bs]
        s_.pop("im")
    # OCR wobble: one odd sample between two equal ones, or a near-identical reading, is the same caption
    same = lambda a, b: a == b or (a and b and SequenceMatcher(None, a, b).ratio() >= 0.88)  # noqa: E731
    for i in range(1, len(samples) - 1):
        if samples[i - 1]["key"] == samples[i + 1]["key"] and samples[i]["key"] != samples[i - 1]["key"]:
            samples[i].update(key=samples[i - 1]["key"], text=samples[i - 1]["text"], boxes=samples[i - 1]["boxes"])
    runs = []
    for s_ in samples:
        if runs and same(runs[-1]["key"], s_["key"]):
            runs[-1]["last"] = s_["f"]
            runs[-1]["all"].append(s_)
            continue
        runs.append({"key": s_["key"], "first": s_["f"], "last": s_["f"], "all": [s_]})
    for i, r in enumerate(runs):  # exact edges: the biggest band change between the two samples
        if i == 0:
            r["a"] = 0 if r["first"] < k else r["first"]
        else:
            lo, hi = runs[i - 1]["last"] + 1, r["first"]
            r["a"] = lo + int(np.argmax(d[lo:hi + 1])) if hi >= lo else r["first"]
            runs[i - 1]["b"] = r["a"]
    if runs:
        runs[-1]["b"] = min(n, runs[-1]["last"] + k)
    events, prev_key, prev_end = [], "", -9.0
    for r in runs:
        if not r["key"]:
            prev_key = ""
            continue
        best = max(r["all"], key=lambda s_: len(s_["key"]))
        bx = best["boxes"]
        st, en = r["a"] / FPS, r["b"] / FPS
        nw, said = match_words(best["text"], st, en, sp_words)
        build = bool(prev_key and r["key"].startswith(prev_key) and st - prev_end < 0.1)
        prev_key, prev_end = r["key"], en
        events.append({"start": round(st, 3), "end": round(en, 3), "text": best["text"], "kind": "caption",
                       "words": nw, "spoken_at": round(said, 3) if said is not None else None, "builds_on_previous": build,
                       "box": {"x0": round(min(b["x0"] for b in bx), 4), "x1": round(max(b["x1"] for b in bx), 4),
                               "y0": round((y0 + min(b["y0"] for b in bx) * hb) / Hf, 4),
                               "y1": round((y0 + max(b["y1"] for b in bx) * hb) / Hf, 4),
                               "h": round(float(np.median([(b["y1"] - b["y0"]) * hb / Hf for b in bx])), 4),
                               "lines": len({round(b["y0"], 1) for b in bx})}})
    caps = [e for e in events if e["end"] - e["start"] <= 6]
    met = None
    if caps:
        holds = [e["end"] - e["start"] for e in caps]
        wpc = [e["words"] for e in caps if e["words"]]
        gaps = [b["start"] - a["end"] for a, b in zip(caps, caps[1:]) if b["start"] - a["end"] > 0.04]
        offs = [e["start"] - e["spoken_at"] for e in caps if e["spoken_at"] is not None]
        up = sum(1 for e in caps if e["text"].upper() == e["text"] and re.search("[A-Z]", e["text"]))
        met = {"method": "band diff at every frame + OCR per change", "count": len(caps),
               "per_min": round(len(caps) / (DUR / 60), 1),
               "on_screen_pct": round(sum(holds) / DUR * 100, 1),
               "words_per_caption_median": float(np.median(wpc)) if wpc else None,
               "words_per_caption_max": int(max(wpc)) if wpc else None,
               "single_word_pct": round(sum(1 for x in wpc if x == 1) / len(wpc) * 100, 1) if wpc else None,
               "hold_median_s": round(float(np.median(holds)), 2), "hold_p10_s": pct(holds, 10), "hold_p90_s": pct(holds, 90),
               "gap_median_s": round(float(np.median(gaps)), 2) if gaps else 0,
               "y_centre_pct": round(float(np.median([(e["box"]["y0"] + e["box"]["y1"]) / 2 for e in caps])) * 100, 1),
               "text_height_pct_of_frame": round(float(np.median([e["box"]["h"] for e in caps])) * 100, 2),
               "approx_cap_height_px_at_1080w": round(float(np.median([e["box"]["h"] for e in caps])) * 1080 * Hf / Wf * 0.72),
               "width_pct_median": round(float(np.median([e["box"]["x1"] - e["box"]["x0"] for e in caps])) * 100, 1),
               "centre_x_pct": round(float(np.median([(e["box"]["x0"] + e["box"]["x1"]) / 2 for e in caps])) * 100, 1),
               "lines_median": float(np.median([e["box"]["lines"] for e in caps])),
               "all_caps_pct": round(up / len(caps) * 100, 1),
               "builds_word_by_word_pct": round(sum(1 for e in caps if e.get("builds_on_previous")) / len(caps) * 100, 1),
               "matched_to_speech_pct": round(len(offs) / len(caps) * 100, 1)}
        if len(offs) >= 3:
            met["vs_speech_median_s"] = round(float(np.median(offs)), 3)
            met["appears_before_word_pct"] = round(sum(1 for o in offs if o < -0.02) / len(offs) * 100, 1)
        met["static_text_in_band"] = [e["text"] for e in events if e["end"] - e["start"] > 6][:5]
        try:
            lh = letter_height(crops)
            if lh:
                met["letter_height_px_at_1080w"] = lh
                if met["all_caps_pct"] >= 80:
                    met["approx_cap_height_px_at_1080w"] = lh
        except Exception as e:
            ERR.append(f"caption letter height: {e!r}")
        try:
            met["colours"] = text_colours(None, None, crops)
        except Exception as e:
            ERR.append(f"caption colours: {e!r}")
    save(C / "captions.json", {"events": events, "metrics": met})
    return events, met, crops


# ---------------------------------------------------------------- audio
def loudness():
    r = run(["ffmpeg", "-nostats", "-i", MP4, "-vn", "-filter_complex", "ebur128=peak=true", "-f", "null", "-"])
    e = r.stderr

    def last(pat):
        m = re.findall(pat, e)
        return float(m[-1]) if m else None
    return {"lufs": last(r"I:\s+(-?[\d.]+) LUFS"), "lra": last(r"LRA:\s+([\d.]+) LU"),
            "true_peak": last(r"Peak:\s+(-?[\d.]+) dBFS")}


def transcribe(a16):
    c = cached("transcript.json")
    if c is not None:
        return c
    step(f"transcribe (faster-whisper {args.model}, CPU int8)")
    from faster_whisper import WhisperModel
    model = WhisperModel(args.model, device="cpu", compute_type="int8", cpu_threads=os.cpu_count() or 8)
    # VAD off by default: with it on, Whisper dropped the last 20 s of speech under music in testing.
    # Off, it can invent an outro ("Thanks for watching!") over music: those segments are dropped below.
    segs, info = model.transcribe(a16, language=args.lang, word_timestamps=True, vad_filter=args.vad,
                                  condition_on_previous_text=False, beam_size=5)
    out, dropped = [], []
    halluc = re.compile(r"^(thanks for watching|thank you for watching|please subscribe|subtitles by|"
                        r"like and subscribe)[.! ]*$", re.I)
    for s in segs:
        text = s.text.strip()
        weak = s.no_speech_prob > 0.5 and s.avg_logprob < -0.6
        canned = bool(halluc.match(text)) and (s.no_speech_prob > 0.2 or s.avg_logprob < -0.5 or s.end > len(a16) / 16000 - 2)
        if weak or canned:
            dropped.append({"start": round(s.start, 2), "text": text, "no_speech": round(s.no_speech_prob, 2),
                            "logprob": round(s.avg_logprob, 2)})
            continue
        out.append({"start": round(s.start, 2), "end": round(s.end, 2), "text": text,
                    "words": [{"w": w.word.strip(), "s": round(w.start, 3), "e": round(w.end, 3),
                               "p": round(w.probability, 2)} for w in (s.words or [])]})
    if dropped:
        ERR.append(f"transcript: dropped {len(dropped)} likely-invented segment(s): " + "; ".join(
            f"{tc(d['start'])} \"{d['text'][:40]}\"" for d in dropped))
    c = {"language": info.language, "language_p": round(info.language_probability, 2), "segments": out, "dropped": dropped}
    save(C / "transcript.json", c)
    return c


WORD_RX = re.compile(r"[A-Za-z0-9']+")


def speech_metrics(tx):
    words = [w for s in tx["segments"] for w in s["words"] if WORD_RX.search(w["w"])]
    if not words:
        return {"words": 0}, words
    n = len(words)
    span = max(0.1, words[-1]["e"] - words[0]["s"])
    gaps = [(a["e"], b["s"]) for a, b in zip(words, words[1:]) if b["s"] - a["e"] >= 0.25]
    gl = [b - a for a, b in gaps]
    talk = 0.0
    cur_s, cur_e = words[0]["s"], words[0]["e"]
    for w in words[1:]:
        if w["s"] - cur_e < 0.3:
            cur_e = max(cur_e, w["e"])
        else:
            talk += cur_e - cur_s
            cur_s, cur_e = w["s"], w["e"]
    talk += cur_e - cur_s
    bins = 10
    edges = np.linspace(0, DUR, bins + 1)
    curve = []
    for i in range(bins):
        k = sum(1 for w in words if edges[i] <= w["s"] < edges[i + 1])
        curve.append(round(k / ((edges[i + 1] - edges[i]) / 60), 0))
    text = " ".join(s["text"] for s in tx["segments"])
    sents = [s for s in re.split(r"(?<=[.!?])\s+", text) if WORD_RX.search(s)]
    low = [WORD_RX.findall(w["w"].lower())[0] if WORD_RX.findall(w["w"].lower()) else "" for w in words]
    cnt = Counter(low)
    per100 = lambda keys: round(sum(cnt[k] for k in keys) / n * 100, 1)  # noqa: E731
    m = {
        "language": tx.get("language"), "words": n, "first_word_at": round(words[0]["s"], 2),
        "words_first_3s": sum(1 for w in words if w["s"] < 3.0),
        "opening_words": " ".join(w["w"] for w in words[:25]),
        "wpm_while_talking": round(n / (talk / 60)) if talk else None, "wpm_overall": round(n / (DUR / 60)),
        "wpm_span": round(n / (span / 60)), "talk_coverage_pct": round(talk / DUR * 100, 1),
        "wpm_by_tenth": curve,
        "pauses_025": len(gl), "pauses_per_min": round(len(gl) / (DUR / 60), 1),
        "pause_median": round(float(np.median(gl)), 2) if gl else 0, "pause_p90": round(float(np.percentile(gl, 90)), 2) if gl else 0,
        "pauses_over_07": sum(1 for g in gl if g >= 0.7), "longest_pause": round(max(gl), 2) if gl else 0,
        "sentences": len(sents), "words_per_sentence": round(n / max(1, len(sents)), 1),
        "questions": text.count("?"),
        "you_per_100": per100(["you", "your", "you're", "yours", "yourself"]),
        "i_per_100": per100(["i", "i'm", "my", "me", "i've", "i'll", "mine"]),
        "we_per_100": per100(["we", "our", "we're", "us"]),
        "numbers": len(re.findall(r"\b\d[\d,.%$]*\b", text)),
        "low_confidence_words": sum(1 for w in words if w.get("p", 1) < 0.5),
    }
    return m, words


def rms_db(x, hop):
    n = len(x) // hop
    if n == 0:
        return np.array([-120.0])
    r = np.sqrt((x[:n * hop].reshape(n, hop) ** 2).mean(1) + 1e-12)
    return 20 * np.log10(r)


def speech_mask(words, n, hop_s):
    m = np.zeros(n, bool)
    for w in words:
        m[int(w["s"] / hop_s):int(math.ceil(w["e"] / hop_s))] = True
    return m


def pause_mask(words, n, hop_s, min_gap=0.4, trim=0.1):
    m = np.zeros(n, bool)
    for a, b in zip(words, words[1:]):
        if b["s"] - a["e"] >= min_gap:
            m[int((a["e"] + trim) / hop_s):int((b["s"] - trim) / hop_s)] = True
    return m


def stems():
    want = args.stems == "on" or (args.stems == "auto" and DUR <= 400)
    if not want or not P["audio"]:
        return None
    voc = C / "stems" / "htdemucs" / "audio44" / "vocals.wav"
    acc = voc.with_name("no_vocals.wav")
    if voc.exists() and acc.exists() and not args.force:
        return voc, acc
    py = find_demucs()
    if not py:
        ERR.append("stems: Demucs isn't installed (pip install demucs in this venv); music and SFX measured on the mix")
        return None
    step("separating voice from music (Demucs htdemucs)")
    wav = C / "audio44.wav"
    run(["ffmpeg", "-y", "-v", "error", "-i", MP4, "-vn", "-ac", "2", "-ar", "44100", wav])
    # seeded: Demucs shifts the audio by a random offset, so unseeded runs give slightly different stems
    # and a re-run could find a different set of effect candidates
    r = run([py, "-c", "import random, sys; random.seed(0); from demucs.separate import main; main(sys.argv[1:])",
             "--two-stems=vocals", "-n", "htdemucs", "-o", C / "stems", wav], timeout=7200)
    if not voc.exists():
        ERR.append("stems: demucs failed: " + (r.stderr or "")[-300:])
        return None
    return voc, acc


def onset_env(x, sr=16000, n_fft=1024, hop=256):
    n = 1 + (len(x) - n_fft) // hop
    if n < 8:
        return np.zeros(1), sr / hop
    win = np.hanning(n_fft).astype(np.float32)
    out = np.empty(n, np.float32)
    prev = None
    for i0 in range(0, n, 2048):
        i1 = min(n, i0 + 2048)
        idx = np.arange(n_fft)[None, :] + hop * np.arange(i0, i1)[:, None]
        mag = np.log1p(100 * np.abs(np.fft.rfft(x[idx] * win, axis=1)))
        if prev is not None:
            mag_full = np.vstack([prev[None, :], mag])
        else:
            mag_full = np.vstack([mag[:1], mag])
        out[i0:i1] = np.maximum(0, np.diff(mag_full, axis=0)).sum(1)
        prev = mag[-1]
    return out, sr / hop


def tempo(env, rate):
    e = env - env.mean()
    if len(e) < rate * 8:
        return None
    ac = np.correlate(e, e, "full")[len(e) - 1:]
    if ac[0] <= 0:
        return None
    lags = np.arange(int(rate * 60 / 200), int(rate * 60 / 60) + 1)
    bpms = 60 * rate / lags
    prior = np.exp(-0.5 * (np.log2(bpms / 120) / 0.9) ** 2)
    score = ac[lags] * prior
    k = int(score.argmax())
    lag = lags[k]
    if 0 < k < len(lags) - 1:  # parabolic refinement
        y0, y1, y2 = ac[lag - 1], ac[lag], ac[lag + 1]
        den = y0 - 2 * y1 + y2
        lag = lag + (0.5 * (y0 - y2) / den if den else 0)
    period = lag / rate
    phases = np.arange(0, int(lag))
    best = max(phases, key=lambda ph: env[np.round(np.arange(ph, len(env), lag)).astype(int).clip(0, len(env) - 1)].sum())
    beats = [round(float(b / rate), 3) for b in np.arange(best, len(env), lag)]
    return {"bpm": round(60 / period, 1), "confidence": round(float(ac[int(round(lag))] / ac[0]), 3), "beats": beats}


def music_and_sfx(words, st, events):
    res = {}
    sr = 16000
    if st is None:
        a = audio_array(MP4, sr)
        hop = 800
        r = rms_db(a, hop)
        sm = speech_mask(words, len(r), hop / sr)
        pm = pause_mask(words, len(r), hop / sr)
        if sm.any() and pm.sum() > 10:
            sp, gp = float(np.median(r[sm])), float(np.median(r[pm]))
            res["bed"] = {"method": "mix, word gaps", "speech_db": round(sp, 1), "gaps_db": round(gp, 1),
                          "verdict": ("something plays under the pauses (bed or room tone)" if gp > -50 and sp - gp < 28
                                      else "near-silent pauses: no bed, or a very low one")}
        res["sfx"] = None
        return res, None
    voc, acc = st
    v = audio_array(voc, sr)
    m = audio_array(acc, sr)
    hop = 800
    rv, rm = rms_db(v, hop), rms_db(m, hop)
    n = min(len(rv), len(rm))
    rv, rm = rv[:n], rm[:n]
    sm = speech_mask(words, n, hop / sr)
    pm = pause_mask(words, n, hop / sr)
    cov = float((rm > -45).mean())
    bed = {"method": "demucs stems", "coverage_pct": round(cov * 100, 1),
           "bed_db_median": round(float(np.median(rm)), 1), "voice_db_median": round(float(np.median(rv[sm])), 1) if sm.any() else None}
    if sm.any():
        bed["under_voice_db"] = round(float(np.median(rm[sm]) - np.median(rv[sm])), 1)
    if pm.sum() > 5 and sm.any():
        bed["ducking_db"] = round(float(np.median(rm[pm]) - np.median(rm[sm])), 1)
    bed["verdict"] = ("continuous non-voice layer (music or room tone: listen.py says which)" if cov >= 0.6
                      else "intermittent non-voice sound" if cov >= 0.2 else "near-silent under the voice")
    res["bed"] = bed
    env, rate = onset_env(m, sr)
    tp = tempo(env, rate) if cov >= 0.3 else None
    if tp:
        per = 60 / tp["bpm"]
        if CUT_T:
            dist = [min(abs(c - b) for b in tp["beats"][max(0, bisect_left(tp["beats"], c) - 1):bisect_left(tp["beats"], c) + 1])
                    for c in CUT_T if tp["beats"]]
            on = sum(1 for d_ in dist if d_ <= 0.05) / len(dist)
            chance = min(1.0, 0.1 / per)
            tp["cuts_on_beat_pct"] = round(on * 100, 1)
            tp["chance_pct"] = round(chance * 100, 1)
            tp["cuts_follow_beat"] = bool(on > 1.8 * chance and tp["confidence"] > 0.15)
        beats = tp.pop("beats")
        res["tempo"] = tp
    else:
        beats = None
    # sound effects: transients that jump out of the non-voice stem
    h2 = 160
    r10 = rms_db(m, h2)
    from scipy.ndimage import median_filter
    floor = median_filter(r10, size=101, mode="nearest")
    rise = r10 - floor
    # an added effect stands out from the recent peaks too, not just the median: a music bed's own drum
    # and note attacks reach the same peak again and again (in testing they made 82 false effects in 45 s)
    prev_peak = np.full(len(r10), -120.0)
    w3 = int(3.0 * sr / h2)
    for t0 in range(0, len(r10), 10):
        lo, hi = max(0, t0 - w3), max(0, t0 - int(0.2 * sr / h2))
        if hi > lo:
            prev_peak[t0:t0 + 10] = np.percentile(r10[lo:hi], 90)
    ev = []
    last_t = -1
    for t in range(1, len(r10) - 1):
        over = r10[t] - prev_peak[t]
        if r10[t] < -42 or not ((rise[t] >= 10 and over >= 3) or (rise[t] >= 4 and over >= 6)):
            continue
        if r10[t] < r10[max(0, t - 8):t + 9].max():
            continue
        if (t - last_t) * h2 / sr < 0.15:
            continue
        on_ = t
        while on_ > 0 and r10[on_ - 1] > floor[on_ - 1] + 3 and t - on_ < 80:
            on_ -= 1
        off = t
        while off + 1 < len(r10) and r10[off + 1] > r10[t] - 12 and off - t < 200:
            off += 1
        seg = m[on_ * h2:max(on_ * h2 + 1024, off * h2)]
        spec = np.abs(np.fft.rfft(seg * np.hanning(len(seg))))
        fq = np.fft.rfftfreq(len(seg), 1 / sr)
        cent = float((spec * fq).sum() / (spec.sum() + 1e-9))
        dur = (off - on_) * h2 / sr
        attack = (t - on_) * h2 / sr
        kind = ("whoosh/riser" if dur >= 0.3 and attack >= 0.12 else "low hit/boom" if cent < 350
                else "click/tick" if cent > 3000 else "hit/pop")
        tt = t * h2 / sr
        j = bisect_left(CUT_T, tt - 0.5)
        near_cut = None
        for c in CUT_T[j:j + 3]:
            if -0.15 <= tt - c <= 0.4:
                near_cut = round(tt - c, 2)
                break
        near_txt = None
        for e in events or []:
            if -0.15 <= tt - e["start"] <= 0.4:
                near_txt = round(tt - e["start"], 2)
                break
        on_beat = bool(beats and min((abs(tt - b) for b in beats[max(0, bisect_left(beats, tt) - 1):bisect_left(beats, tt) + 1]),
                                     default=9) <= 0.035)
        vi = min(len(rv) - 1, int(tt / (hop / sr)))
        ev.append({"t": round(tt, 2), "kind": kind, "peak_db": round(float(r10[t]), 1), "rise_db": round(float(rise[t]), 1),
                   "dur": round(dur, 2), "centroid_hz": round(cent), "after_cut": near_cut, "after_text": near_txt,
                   "on_beat": on_beat, "vs_voice_db": round(float(r10[t] - np.median(rv[sm])), 1) if sm.any() else None})
        last_t = t
    q = [0, 0, 0, 0]
    for e in ev:
        q[min(3, int(e["t"] / DUR * 4))] += 1
    res["sfx"] = {"count": len(ev), "per_min": round(len(ev) / (DUR / 60), 1),
                  "near_cut_pct": round(sum(1 for e in ev if e["after_cut"] is not None) / max(1, len(ev)) * 100, 1),
                  "near_text_pct": round(sum(1 for e in ev if e["after_text"] is not None) / max(1, len(ev)) * 100, 1),
                  "on_beat_pct": round(sum(1 for e in ev if e["on_beat"]) / max(1, len(ev)) * 100, 1),
                  "kinds": dict(Counter(e["kind"] for e in ev)), "by_quarter": q,
                  "median_vs_voice_db": round(float(np.median([e["vs_voice_db"] for e in ev if e["vs_voice_db"] is not None])), 1) if ev and sm.any() else None,
                  "cuts_with_sfx_pct": round(sum(1 for c in CUT_T if any(-0.15 <= e["t"] - c <= 0.4 for e in ev))
                                             / max(1, len(CUT_T)) * 100, 1),
                  "events": ev}
    curves = {"hop": hop / sr, "voice_db": [round(float(x), 1) for x in rv], "bed_db": [round(float(x), 1) for x in rm]}
    return res, curves


def voice_character(words, st):
    sr = 16000
    src = st[0] if st else MP4
    a = audio_array(src, sr)
    if not words:
        return None
    segs = [a[int(w["s"] * sr):int(w["e"] * sr)] for w in words]
    x = np.concatenate([s for s in segs if len(s)]) if segs else np.array([])
    if len(x) < sr:
        return None
    from scipy.signal import welch
    f, pxx = welch(x, sr, nperseg=2048)

    def band(lo, hi):
        return float(pxx[(f >= lo) & (f < hi)].sum() + 1e-12)
    mid = band(800, 1250)
    r = rms_db(x, 800)
    pk = np.array([20 * np.log10(np.abs(x[i * 800:(i + 1) * 800]).max() + 1e-9) for i in range(len(x) // 800)])
    crest = float(np.median(pk - r[:len(pk)])) if len(pk) else None
    return {"low_63_200_vs_1k_db": round(10 * math.log10(band(63, 200) / mid), 1),
            "presence_2_5k_vs_1k_db": round(10 * math.log10(band(2000, 5000) / mid), 1),
            "air_5_8k_vs_1k_db": round(10 * math.log10(band(5000, 7900) / mid), 1),
            "centroid_hz": round(float((pxx * f).sum() / pxx.sum())), "crest_db": round(crest, 1) if crest else None,
            "note": "crest under ~10 dB = heavily compressed; low end above 0 dB = boomy/close mic"}


# ---------------------------------------------------------------- drawing
def grid(items, cols, path, cell_w, label_h=44, pad=8, title=None):
    """items: (PIL image, line1, line2, tag colour or None)."""
    if not items:
        return None
    ims = []
    for im, a, b, col in items:
        if im.width != cell_w:
            im = im.resize((cell_w, max(1, int(im.height * cell_w / im.width))), Image.LANCZOS)
        ims.append((im, a, b, col))
    ch = max(i[0].height for i in ims)
    rows = (len(ims) + cols - 1) // cols
    th = 40 if title else 0
    W = cols * (cell_w + pad) + pad
    H = th + rows * (ch + label_h + pad) + pad
    sheet = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(sheet)
    f1, f2 = font(17, True), font(14)
    if title:
        d.text((pad + 2, 10), title, fill=INK, font=font(20, True))
    for i, (im, a, b, col) in enumerate(ims):
        x = pad + (i % cols) * (cell_w + pad)
        y = th + pad + (i // cols) * (ch + label_h + pad)
        sheet.paste(im, (x, y))
        if col:
            d.rectangle([x, y, x + cell_w - 1, y + 5], fill=col)
        d.text((x + 2, y + ch + 4), a, fill=INK, font=f1)
        d.text((x + 2, y + ch + 24), b, fill=DIM, font=f2)
    sheet.save(path, quality=85)
    return str(path)


def grab_idx(idx, tail, out):
    """Frames at exact frame numbers (at FPS) through the filter tail, in one ffmpeg pass. {index: path}."""
    idx = sorted(set(int(i) for i in idx))
    out.mkdir(parents=True, exist_ok=True)
    for p in out.glob("*.jpg"):
        p.unlink()
    if not idx:
        return {}
    expr = "+".join(f"eq(n,{i})" for i in idx)
    flt = out / "_filter.txt"
    flt.write_text(f"fps={FPS},select='{expr}'" + (f",{tail}" if tail else ""), encoding="utf-8")
    r = run(["ffmpeg", "-y", "-v", "error", "-i", MP4, "-/filter:v", flt, "-fps_mode", "passthrough", "-q:v", "2",
             out / "%05d.jpg"])
    files = sorted(out.glob("*.jpg"))
    if len(files) != len(idx):
        ERR.append(f"grab: wanted {len(idx)} frames, got {len(files)} ({(r.stderr or '')[-200:]})")
    return dict(zip(idx, files))


def grab(times, short=360):
    """Exact frames at the given times, full quality, one ffmpeg pass. Returns PIL images in order."""
    if not times:
        return []
    idx = sorted({min(N - 1, max(0, int(round(t * FPS)))) for t in times})
    if VERT:
        w, h = short, even(short * P["height"] / P["width"])
    else:
        w, h = even(short * P["width"] / P["height"]), short
    files = grab_idx(idx, f"scale={w}:{h}:flags=lanczos", C / "grab")
    by = {i: Image.open(f).convert("RGB") for i, f in files.items()}
    res = []
    for t in times:
        i = min(N - 1, max(0, int(round(t * FPS))))
        res.append(by.get(i) or (by[min(by, key=lambda k: abs(k - i))] if by else Image.new("RGB", (w, h))))
    return res


def boards(cam, facesd, colr):
    files = {}
    for old in list(IMG.glob("shots_*.jpg")) + list(IMG.glob("sheet_*.jpg")):  # a re-run may make fewer pages
        old.unlink()
    # shot board: one frame per shot, at its middle
    mids = [s["start"] + s["dur"] / 2 for s in SHOTS]
    ims = grab(mids, short=300 if VERT else 220)
    cm = {x["n"]: x for x in (cam or {}).get("shots", [])}
    items = []
    for s, im in zip(SHOTS, ims):
        mv = cm.get(s["n"], {}).get("move", "")
        z = f" x{s['zoom_in']:.2f}" if s["cut_in"] == "punch" and s["zoom_in"] else ""
        items.append((im, f"#{s['n']}  {tc(s['start'])}  {s['dur']:.2f}s", f"{s['cut_in']}{z} · {mv}", CUT_COL.get(s["cut_in"])))
    per = 40 if VERT else 36
    cols = 8 if VERT else 6
    cw = 190 if VERT else 300
    files["shot_boards"] = []
    for k in range(0, len(items), per):
        p = IMG / f"shots_{k // per + 1:02d}.jpg"
        grid(items[k:k + per], cols, p, cw, title=f"Shots {k + 1}-{min(len(items), k + per)} of {len(items)}"
             "   (bar: white new shot, amber jump cut, blue punch in/out, pink transition)")
        files["shot_boards"].append(str(p))
    # contact sheets from frames/
    fr = sorted(FR.glob("*.jpg"))
    sel = list(range(len(fr))) if DUR <= 180 else list(range(min(len(fr), int(90 * R2))))
    files["contact_sheets"] = []
    per = 48 if VERT else 36
    for k in range(0, len(sel), per):
        it = []
        for i in sel[k:k + per]:
            t = ftime(i)
            s = shot_at(t)
            newcut = any(t - 1 / R2 < c <= t for c in CUT_T)
            it.append((Image.open(fr[i]).convert("RGB"), tc(t), f"shot #{s['n']}", (220, 60, 50) if newcut else None))
        p = IMG / f"sheet_{k // per + 1:02d}.jpg"
        grid(it, 8 if VERT else 6, p, 160 if VERT else 260, label_h=38,
             title=f"Every {1 / R2:.2f}s from {tc(ftime(sel[k]))} (red bar: a cut just before this frame)")
        files["contact_sheets"].append(str(p))
    if DUR > 180 and fr:
        picks = np.linspace(0, len(fr) - 1, 60).astype(int)
        it = [(Image.open(fr[i]).convert("RGB"), tc(ftime(i)), f"shot #{shot_at(ftime(i))['n']}", None) for i in picks]
        p = IMG / "spine.jpg"
        grid(it, 10, p, 200, label_h=38, title="The whole video, 60 evenly spaced frames")
        files["spine"] = str(p)
    # hook: first 5 s at 10 fps
    hk = sorted((WD / "hook").glob("*.jpg"))
    if hk:
        it = [(Image.open(p).convert("RGB"), f"{i / 10:.1f}s", "", (220, 60, 50) if any(i / 10 - 0.1 < c <= i / 10 for c in CUT_T) else None)
              for i, p in enumerate(hk)]
        p = IMG / "hook_5s.jpg"
        grid(it, 10, p, 150 if VERT else 230, label_h=26, title="First 5 seconds at 10 fps")
        files["hook_sheet"] = str(p)
    # palette strip
    if colr:
        W, Hh = 1400, 150
        im = Image.new("RGB", (W, Hh + 40), BG)
        d = ImageDraw.Draw(im)
        x = 0
        for c_ in colr["palette"]:
            if x >= W:
                break
            w = max(60, int(c_["share"] * W))
            rgb = tuple(int(c_["hex"][i:i + 2], 16) for i in (1, 3, 5))
            d.rectangle([x, 0, min(W, x + w), Hh], fill=rgb)
            d.text((x + 6, Hh + 6), f"{c_['hex']} {c_['share'] * 100:.0f}%", fill=INK, font=font(14, True))
            d.text((x + 6, Hh + 22), c_["role"], fill=DIM, font=font(12))
            x += w
        p = IMG / "palette.jpg"
        im.save(p, quality=90)
        files["palette"] = str(p)
    return files


def text_crops(events):
    if not events:
        return None
    pick = []
    for kind, k in (("title", 6), ("caption", 4), ("text", 4)):
        evs = sorted([e for e in events if e["kind"] == kind], key=lambda e: -e["box"]["h"])
        seen = set()
        for e in evs:
            key = norm_text(e["text"])[:20]
            if key in seen:
                continue
            seen.add(key)
            pick.append(e)
            if len([p for p in pick if p["kind"] == kind]) >= k:
                break
    if not pick:
        return None
    ims = grab([(e["start"] + e["end"]) / 2 for e in pick], short=1080)
    items = []
    for e, im in zip(pick, ims):
        b = e["box"]
        W, H = im.size
        mx, my = (b["x1"] - b["x0"]) * 0.12 * W + 8, (b["y1"] - b["y0"]) * 0.5 * H + 8
        crop = im.crop((max(0, int(b["x0"] * W - mx)), max(0, int(b["y0"] * H - my)),
                        min(W, int(b["x1"] * W + mx)), min(H, int(b["y1"] * H + my))))
        scale = min(560 / crop.width, 200 / crop.height)
        crop = crop.resize((max(1, int(crop.width * scale)), max(1, int(crop.height * scale))), Image.LANCZOS)
        canvas = Image.new("RGB", (560, 200), (40, 40, 40))
        canvas.paste(crop, ((560 - crop.width) // 2, (200 - crop.height) // 2))
        items.append((canvas, f"{e['kind']} {tc(e['start'])}", f"h {b['h'] * 100:.1f}% of frame · y {((b['y0'] + b['y1']) / 2) * 100:.0f}%", None))
    p = IMG / "text_crops.jpg"
    grid(items, 3, p, 560, title="On-screen text at full resolution (for naming the fonts)")
    return str(p)


def pacing_map(cam, facesd, colr, events, sp_words, curves, sfx, heat):
    W = 1900
    L = 150
    plot = W - L - 20
    lanes = [("Shots", 80), ("Cuts / 10 s", 50), ("Words / min", 50), ("Camera", 34), ("Face", 30), ("Text", 34),
             ("Voice / bed", 70), ("SFX", 22), ("Colour", 40), ("Brightness", 34)]
    if heat:
        lanes.append(("Replays", 44))
    H = sum(h + 10 for _, h in lanes) + 70
    im = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(im)
    f = font(15, True)
    fs = font(12)
    X = lambda t: L + int(t / DUR * plot)  # noqa: E731
    y = 40
    d.text((L, 10), f"Pacing map · {DUR:.1f}s · {len(SHOTS)} shots · {len(CUT_T) / (DUR / 60):.1f} cuts/min", fill=INK, font=font(18, True))
    pos = {}
    for name, h in lanes:
        pos[name] = (y, h)
        d.text((10, y + h // 2 - 8), name, fill=DIM, font=f)
        d.rectangle([L, y, L + plot, y + h], outline=(45, 43, 40))
        y += h + 10
    # shots: bar height ~ shot length (cap 6 s), colour by the cut that starts it
    y0, h = pos["Shots"]
    for i, s in enumerate(SHOTS):
        bh = int(min(s["dur"], 6) / 6 * (h - 4))
        col = (90, 88, 84) if i % 2 else (120, 117, 112)
        d.rectangle([X(s["start"]), y0 + h - bh, max(X(s["start"]) + 1, X(s["end"]) - 1), y0 + h], fill=col)
        d.rectangle([X(s["start"]), y0, X(s["start"]) + 1, y0 + 8], fill=CUT_COL.get(s["cut_in"]))
    d.text((L + plot - 130, y0 + 2), "bar height = shot length", fill=DIM, font=fs)

    def line(name, xs, ys, lo, hi, col, width=2):
        y0, h = pos[name]
        pts = [(X(x), y0 + h - int((min(max(v, lo), hi) - lo) / (hi - lo + 1e-9) * (h - 4)) - 2) for x, v in zip(xs, ys)]
        if len(pts) > 1:
            d.line(pts, fill=col, width=width)
    ts = np.linspace(0, DUR, 200)
    rate = [sum(1 for c in CUT_T if t - 5 <= c < t + 5) for t in ts]
    line("Cuts / 10 s", ts, rate, 0, max(rate + [4]), (240, 180, 60))
    d.text((L + 4, pos["Cuts / 10 s"][0] + 2), f"max {max(rate + [0])}", fill=DIM, font=fs)
    if sp_words:
        wpm = [sum(1 for w in sp_words if t - 3 <= w["s"] < t + 3) * 10 for t in ts]
        line("Words / min", ts, wpm, 0, max(wpm + [200]), (120, 210, 140))
        d.text((L + 4, pos["Words / min"][0] + 2), f"max {max(wpm)}", fill=DIM, font=fs)
    if cam:
        y0, h = pos["Camera"]
        for s in cam["shots"]:
            sh = SHOTS[s["n"] - 1]
            col = {"push in": (80, 200, 230), "pull out": (60, 120, 200), "snap zoom": (230, 90, 90), "pan/slide": (200, 160, 80),
                   "handheld": (170, 110, 210), "locked": (70, 68, 64)}.get(s["move"])
            if col:
                d.rectangle([X(sh["start"]), y0 + 6, max(X(sh["start"]) + 1, X(sh["end"]) - 1), y0 + h - 6], fill=col)
            for t in s.get("snaps", []):
                d.polygon([(X(t), y0 + 2), (X(t) - 4, y0 + 10), (X(t) + 4, y0 + 10)], fill=(255, 120, 120))
    if facesd:
        y0, h = pos["Face"]
        for fr in facesd["frames"]:
            if fr["n"]:
                v = min(1.0, fr["h_short"] / 0.6)
                c = tuple(int(60 + 180 * v) for _ in range(3))
                d.rectangle([X(fr["t"]), y0 + 4, X(fr["t"] + 1 / R2), y0 + h - 4], fill=c)
    if events:
        y0, h = pos["Text"]
        for e in events:
            col = {"caption": (240, 220, 120), "title": (230, 110, 90), "text": (150, 190, 230)}.get(e["kind"], (90, 90, 90))
            off = {"caption": 0, "title": 1, "text": 2}.get(e["kind"], 2)
            yy = y0 + 3 + off * 10
            d.rectangle([X(e["start"]), yy, max(X(e["start"]) + 1, X(e["end"])), yy + 8], fill=col)
    if curves:
        hop = curves["hop"]
        n = len(curves["voice_db"])
        idx = np.linspace(0, n - 1, min(n, 900)).astype(int)
        xs = [i * hop for i in idx]
        line("Voice / bed", xs, [curves["bed_db"][i] for i in idx], -60, 0, (230, 120, 80), 1)
        line("Voice / bed", xs, [curves["voice_db"][i] for i in idx], -60, 0, (200, 200, 200), 1)
        d.text((L + 4, pos["Voice / bed"][0] + 2), "white voice · orange music/bed (dBFS)", fill=DIM, font=fs)
    if sfx:
        y0, h = pos["SFX"]
        for e in sfx["events"]:
            d.line([(X(e["t"]), y0 + 2), (X(e["t"]), y0 + h - 2)], fill=(255, 200, 90), width=2)
    if colr:
        y0, h = pos["Colour"]
        frs = colr["frames"]
        for fr in frs:
            rgb = tuple(int(fr["mean"][i:i + 2], 16) for i in (1, 3, 5))
            d.rectangle([X(fr["t"]), y0 + 1, X(fr["t"] + 1 / R2) + 1, y0 + h - 1], fill=rgb)
        line("Brightness", [x["t"] for x in frs], [x["luma"] for x in frs], 0, 1, (220, 220, 220), 1)
    if heat:
        xs = [(hh["start_time"] + hh["end_time"]) / 2 for hh in heat]
        line("Replays", xs, [hh["value"] for hh in heat], 0, 1, (240, 80, 120), 2)
    # time axis
    step_s = next(s for s in (1, 2, 5, 10, 15, 30, 60, 120, 300, 600) if DUR / s <= 24)
    for t in np.arange(0, DUR + 0.01, step_s):
        d.line([(X(t), 32), (X(t), y)], fill=(38, 36, 34))
        d.text((X(t) + 2, y + 2), tc(t), fill=DIM, font=fs)
    p = IMG / "pacing_map.png"
    im.save(p)
    return str(p)


# ---------------------------------------------------------------- run everything
def pct(a, q):
    return round(float(np.percentile(a, q)), 2) if len(a) else None


def main():
    step(f"{P['width']}x{P['height']} {P['fps']}fps {DUR:.1f}s, {N} frames read")
    cam = camera()
    frames = dump_frames()
    colr = facesd = oc = None
    try:
        colr = colour(frames)
    except Exception as e:
        ERR.append(f"colour: {e!r}")
    try:
        facesd = faces(frames)
    except Exception as e:
        ERR.append(f"faces: {e!r}")
    try:
        oc = ocr(frames)
    except Exception as e:
        ERR.append(f"ocr: {e!r}")
    events, band = text_events(oc)
    loud = tx = None
    sp, sp_words = {"words": 0}, []
    st = curves = None
    audio = {}
    voice = None
    if P["audio"]:
        loud = loudness()
        try:
            tx = transcribe(audio_array(MP4, 16000))
            sp, sp_words = speech_metrics(tx)
        except Exception as e:
            ERR.append(f"transcribe: {e!r}")
    capm = None
    if band is not None:
        try:
            cev, capm, _ = captions_precise(band, sp_words)
            if cev:
                events = sorted([e for e in events if e["kind"] != "caption"] + cev, key=lambda e: e["start"])
        except Exception as e:
            ERR.append(f"captions: {e!r}")
    tcols = text_colours(events, frames) if events and capm is None else None
    if P["audio"]:
        try:
            st = stems()
        except Exception as e:
            ERR.append(f"stems: {e!r}")
        try:
            audio, curves = music_and_sfx(sp_words, st, [e for e in events if e["kind"] in ("title", "text")])
        except Exception as e:
            ERR.append(f"music/sfx: {e!r}")
        try:
            voice = voice_character(sp_words, st)
        except Exception as e:
            ERR.append(f"voice: {e!r}")
    # per-shot enrichment
    cm = {x["n"]: x for x in (cam or {}).get("shots", [])}
    for s in SHOTS:
        s["camera"] = cm.get(s["n"], {}).get("move")
        if facesd:
            fs_ = [f for f in facesd["frames"] if s["start"] <= f["t"] < s["end"]]
            withf = [f for f in fs_ if f["n"]]
            s["face_pct"] = round(len(withf) / len(fs_) * 100) if fs_ else None
            if withf:
                hs = float(np.median([f["h_short"] for f in withf]))
                s["face_size"] = size_class(hs)
                s["face_cx"] = round(float(np.median([f["cx"] for f in withf])), 2)
        if colr:
            cf = [f for f in colr["frames"] if s["start"] <= f["t"] < s["end"]]
            if cf:
                s["ground"] = Counter(f["ground"] for f in cf).most_common(1)[0][0]
        if events:
            s["text"] = sorted({e["kind"] for e in events if e["start"] < s["end"] and e["end"] > s["start"]})
        if sp_words:
            s["words"] = sum(1 for w in sp_words if s["start"] <= w["s"] < s["end"])
    durs = np.array([s["dur"] for s in SHOTS])
    q4 = []
    for k in range(4):
        a, b = DUR * k / 4, DUR * (k + 1) / 4
        sh = [s for s in SHOTS if a <= s["start"] < b]
        q4.append({"shots": len(sh), "mean_len": round(float(np.mean([s["dur"] for s in sh])), 2) if sh else None})
    types = Counter(c["type"] for c in CUTS["cuts"])
    shots_m = {
        "count": len(SHOTS), "cuts": len(CUT_T), "cuts_per_min": round(len(CUT_T) / (DUR / 60), 1),
        "mean": round(float(durs.mean()), 2), "median": round(float(np.median(durs)), 2),
        "p10": pct(durs, 10), "p90": pct(durs, 90), "min": round(float(durs.min()), 2), "max": round(float(durs.max()), 2),
        "under_1s_pct": round(float((durs < 1).mean() * 100), 1), "over_4s_pct": round(float((durs > 4).mean() * 100), 1),
        "by_quarter": q4, "first_cut_at": CUT_T[0] if CUT_T else None,
        "cuts_in_first_5s": sum(1 for c in CUT_T if c < 5),
        "cut_types": dict(types), "flashes": sum(1 for c in CUTS["cuts"] if c["flash"]),
        "punch_zooms": [c["zoom"] for c in CUTS["cuts"] if c["type"] == "punch"],
        "region_changes": CUTS["region"],
        "histogram": {k: int(v) for k, v in zip(["<0.5", "0.5-1", "1-2", "2-3", "3-5", "5-10", "10+"],
                                                 np.histogram(durs, bins=[0, 0.5, 1, 2, 3, 5, 10, 1e9])[0])},
    }
    if CUT_T and sp_words:  # where cuts land relative to speech
        starts = [w["s"] for w in sp_words]
        on_word = mid = 0
        for c in CUT_T:
            j = bisect_left(starts, c)
            near = min([abs(c - s_) for s_ in starts[max(0, j - 1):j + 1]] or [9])
            if near <= 0.12:
                on_word += 1
            elif 0 < j <= len(sp_words) and sp_words[j - 1]["e"] > c + 0.05:
                mid += 1
        shots_m["cuts_at_word_start_pct"] = round(on_word / len(CUT_T) * 100, 1)
        shots_m["cuts_mid_word_pct"] = round(mid / len(CUT_T) * 100, 1)
        shots_m["cuts_in_pause_pct"] = round((len(CUT_T) - on_word - mid) / len(CUT_T) * 100, 1)
    camm = None
    if cam:
        mv = Counter()
        for s in SHOTS:
            if s.get("camera"):
                mv[s["camera"]] += s["dur"]
        pushes = [x["zoom_pct_s"] for x in cam["shots"] if x.get("move") == "push in"]
        camm = {"time_share_pct": {k: round(v / DUR * 100, 1) for k, v in mv.most_common()},
                "push_rate_median_pct_s": round(float(np.median(pushes)), 2) if pushes else None,
                "snap_zooms": sum(len(x.get("snaps", [])) for x in cam["shots"]),
                "element_motion_median": round(float(np.median([x["element_motion"] for x in cam["shots"] if "element_motion" in x] or [0])), 4)}
    facem = None
    if facesd:
        fr = facesd["frames"]
        withf = [f for f in fr if f["n"]]
        facem = {"on_screen_pct": round(len(withf) / max(1, len(fr)) * 100, 1)}
        if withf:
            hs = [f["h_short"] for f in withf]
            facem.update({
                "size_median": size_class(float(np.median(hs))), "face_height_of_short_side": round(float(np.median(hs)), 3),
                "sizes": dict(Counter(size_class(h) for h in hs)),
                "centre_x_median": round(float(np.median([f["cx"] for f in withf])), 3),
                "eyeline_y_median": round(float(np.median([f["eye_y"] for f in withf])), 3),
                "two_plus_faces_pct": round(sum(1 for f in withf if f["n"] >= 2) / len(fr) * 100, 1),
                "position": dict(Counter("left" if f["cx"] < 0.4 else "right" if f["cx"] > 0.6 else "centre" for f in withf))})
    textm = None
    if oc:
        fr = oc["frames"]
        textm = {"frames_with_text_pct": round(sum(1 for f in fr if f["boxes"]) / max(1, len(fr)) * 100, 1),
                 "events": len(events), "kinds": dict(Counter(e["kind"] for e in events))}
        caps = [e for e in events if e["kind"] == "caption"]
        if capm:
            textm["captions"] = capm
        elif caps:
            wpc = [len(e["text"].split()) for e in caps]
            durc = [e["end"] - e["start"] for e in caps]
            hh = [e["box"]["h"] for e in caps]
            up = sum(1 for e in caps if e["text"].upper() == e["text"] and re.search("[A-Z]", e["text"]))
            cap_frames = sum(1 for f in fr if any(band and band[0] <= (b["y0"] + b["y1"]) / 2 <= band[1] for b in f["boxes"]))
            textm["captions"] = {
                "band_y_pct": [round(band[0] * 100), round(band[1] * 100)] if band else None,
                "y_centre_pct": round(float(np.median([(e["box"]["y0"] + e["box"]["y1"]) / 2 for e in caps])) * 100, 1),
                "on_screen_pct": round(cap_frames / max(1, len(fr)) * 100, 1),
                "words_per_caption_median": float(np.median(wpc)), "words_per_caption_max": int(max(wpc)),
                "single_word_pct": round(sum(1 for w in wpc if w == 1) / len(wpc) * 100, 1),
                "hold_median_s": round(float(np.median(durc)), 2), "sample_step_s": round(1 / R2, 2),
                "text_height_pct_of_frame": round(float(np.median(hh)) * 100, 2),
                "approx_cap_height_px_at_1080w": round(float(np.median(hh)) * 1080 * P["height"] / P["width"] * 0.72),
                "lines_median": float(np.median([e["box"]["lines"] for e in caps])),
                "all_caps_pct": round(up / len(caps) * 100, 1), "colours": tcols,
                "width_pct_median": round(float(np.median([e["box"]["x1"] - e["box"]["x0"] for e in caps])) * 100, 1)}
            if sp_words:
                offs = []
                for e in caps:
                    first = norm_text(e["text"]).split()[:1]
                    if not first:
                        continue
                    for w in sp_words:
                        if abs(w["s"] - e["start"]) <= 1.5 and norm_text(w["w"]) == first[0]:
                            offs.append(e["start"] - w["s"])
                            break
                if len(offs) >= 3:
                    textm["captions"]["vs_speech_median_s"] = round(float(np.median(offs)), 2)
                    textm["captions"]["vs_speech_note"] = "negative = caption appears before the word is spoken (sampling step limits precision)"
    heat = META.get("heatmap")
    ret = None
    if heat:
        vals = [hh["value"] for hh in heat]
        top = sorted(heat, key=lambda hh: -hh["value"])
        ret = {"peaks": [{"t": round((hh["start_time"] + hh["end_time"]) / 2, 1), "value": round(hh["value"], 2)} for hh in top[:5]],
               "dip": {"t": round((min(heat, key=lambda hh: hh["value"])["start_time"]), 1)}, "mean": round(float(np.mean(vals)), 3)}
    step("boards and charts")
    files = {}
    try:
        files.update(boards(cam, facesd, colr))
    except Exception as e:
        ERR.append(f"boards: {e!r}")
    try:
        files["text_crops"] = text_crops(events)
    except Exception as e:
        ERR.append(f"text crops: {e!r}")
    try:
        files["pacing_map"] = pacing_map(cam, facesd, colr, events, sp_words, curves, audio.get("sfx"), heat)
    except Exception as e:
        ERR.append(f"pacing map: {e!r}")
    fmt = dict(P)
    fmt["real_fps"] = REAL_FPS
    M = {"source": {k: META.get(k) for k in ("source", "platform", "id", "title", "channel", "uploader", "upload_date",
                                             "view_count", "like_count", "comment_count", "channel_follower_count",
                                             "channel_followers", "chapters", "via") if META.get(k) is not None},
         "format": fmt, "shots": shots_m, "shot_list": SHOTS, "cuts": CUTS["cuts"], "camera": camm, "faces": facem,
         "colour": {k: v for k, v in (colr or {}).items() if k != "frames"} or None, "text": textm,
         "speech": sp, "loudness": loud, "audio": {k: v for k, v in audio.items() if k != "sfx"},
         "sfx": {k: v for k, v in (audio.get("sfx") or {}).items()} or None, "voice": voice, "retention": ret,
         "text_events": events, "files": files, "errors": ERR,
         "settings": {"frames_fps": R2, "analysis": f"{W1}px every frame; {W2}x{H2} frames", "whisper": args.model,
                      "stems": bool(st)}}
    Lj = load(WD / "listen.json")
    if Lj:  # keep an earlier listen.py run (re-run it if the audio steps changed)
        M["listen"] = {k: v for k, v in Lj.items() if k != "timeline"}
    save(WD / "measures.json", M)
    write_summary(M)
    if Lj:
        from listen import write_summary as listen_summary
        listen_summary(WD, Lj)
    write_transcript(tx, events)
    step("done" + (f" with {len(ERR)} warnings" if ERR else ""))
    for e in ERR:
        log("  !", e)


def write_transcript(tx, events):
    lines = []
    if tx:
        marks = [(s["start"], s["n"]) for s in SHOTS[1:]]
        mi = 0
        for seg in tx["segments"]:
            out = f"[{tc(seg['start'])}] "
            for w in seg["words"]:
                while mi < len(marks) and marks[mi][0] <= w["s"]:
                    out += f"[#{marks[mi][1]}] "
                    mi += 1
                out += w["w"] + " "
            lines.append(out.rstrip())
    (WD / "transcript.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    small = sum(1 for e in events if e["kind"] == "ui/small")
    ev = [f"[{tc(e['start'])}-{tc(e['end'])}] {e['kind']:<8} y{(e['box']['y0'] + e['box']['y1']) / 2 * 100:3.0f}% "
          f"h{e['box']['h'] * 100:4.1f}%" + (f" {e['words']}w" if e.get("words") else "") + f"  {e['text']}"
          for e in events if e["kind"] != "ui/small"]
    head = [f"# On-screen text. kind, vertical centre (% from top), text height (% of frame). "
            f"{small} small UI/screen-text pieces left out (in measures.json)."]
    (WD / "onscreen_text.txt").write_text("\n".join(head + ev) + "\n", encoding="utf-8")


def write_summary(M):
    f, s, sp = M["format"], M["shots"], M["speech"]
    src = M["source"]
    L = [f"# Measurements: {src.get('title') or src.get('id') or WD.name}", ""]
    L.append(f"{src.get('platform', '')} · {src.get('channel') or src.get('uploader') or ''} · "
             f"views {src.get('view_count')} · likes {src.get('like_count')} · comments {src.get('comment_count')}")
    L += ["", "## Hard numbers", "", "| Metric | Measured |", "|---|---|"]
    row = lambda k, v: L.append(f"| {k} | {v} |")  # noqa: E731
    row("Format", f"{f['width']}x{f['height']} ({f['aspect']}), {f['fps']} fps (real ~{f['real_fps']}), {f['duration']:.1f}s")
    row("Shots / cuts", f"{s['count']} shots, {s['cuts']} cuts, **{s['cuts_per_min']} cuts/min**")
    row("Shot length", f"mean **{s['mean']}s**, median {s['median']}s, p10 {s['p10']}s, p90 {s['p90']}s, range {s['min']}-{s['max']}s")
    row("Short / long shots", f"{s['under_1s_pct']}% under 1s, {s['over_4s_pct']}% over 4s")
    row("Shot length by quarter", ", ".join(f"Q{i + 1} {q['mean_len']}s ({q['shots']})" for i, q in enumerate(s["by_quarter"])))
    row("Opening", f"first cut at {s['first_cut_at']}s, {s['cuts_in_first_5s']} cuts in the first 5s")
    row("Cut types", ", ".join(f"{k} {v}" for k, v in s["cut_types"].items()) + (f", {s['flashes']} flash frames" if s["flashes"] else ""))
    if s["punch_zooms"]:
        row("Punch-in scales", ", ".join(f"x{z:.2f}" for z in s["punch_zooms"][:12]))
    if "cuts_at_word_start_pct" in s:
        row("Cuts vs speech", f"{s['cuts_at_word_start_pct']}% on a word start (±0.12s), {s['cuts_mid_word_pct']}% mid-word, "
            f"{s['cuts_in_pause_pct']}% in a pause or with no speech")
    rc = s["region_changes"]
    if rc["top_only"] + rc["bottom_only"] > 2:
        row("Split-layout changes", f"top half alone {rc['top_only']}x, bottom half alone {rc['bottom_only']}x")
    if M["camera"]:
        c = M["camera"]
        row("Camera (share of time)", ", ".join(f"{k} {v}%" for k, v in c["time_share_pct"].items()))
        row("Zooms", f"push rate median {c['push_rate_median_pct_s']}%/s, {c['snap_zooms']} snap zooms inside shots")
    if M["faces"]:
        fa = M["faces"]
        row("Face", f"on screen {fa['on_screen_pct']}%, typical {fa.get('size_median')}, centre x {fa.get('centre_x_median')}, "
            f"eyeline y {fa.get('eyeline_y_median')} (0 top, 1 bottom)")
    if M["colour"]:
        co = M["colour"]
        row("Palette", " ".join(f"`{p['hex']}` {p['share'] * 100:.0f}%" for p in co["palette"][:6]))
        row("Look", f"brightness {co['luma_mean']}, black {co['black_level']}, white {co['white_level']}, saturation "
            f"{co['saturation']}, warmth {co['warmth']:+}, dark frames {co['dark_frames_pct']}%, light frames {co['light_frames_pct']}%")
    if M["text"]:
        t = M["text"]
        row("On-screen text", f"{t['frames_with_text_pct']}% of frames, {t['events']} pieces ({', '.join(f'{k} {v}' for k, v in t['kinds'].items())})")
        cp = t.get("captions")
        if cp:
            bits = []
            if cp.get("count"):
                bits.append(f"{cp['count']} captions ({cp['per_min']}/min), on screen {cp['on_screen_pct']}% of the time")
            if cp.get("words_per_caption_median") is not None:
                bits.append(f"**{cp['words_per_caption_median']:g} words each** (max {cp['words_per_caption_max']}"
                            + (f", single word {cp['single_word_pct']}%" if cp.get("single_word_pct") is not None else "") + ")")
            bits.append(f"held **{cp['hold_median_s']}s**" + (f" (p10 {cp['hold_p10_s']}s, p90 {cp['hold_p90_s']}s)" if cp.get("hold_p10_s") is not None else ""))
            bits.append(f"{cp['lines_median']:g} line(s), centre y {cp['y_centre_pct']}%, text height {cp['text_height_pct_of_frame']}% of frame"
                        f" (~{cp['approx_cap_height_px_at_1080w']} px caps at 1080 wide)")
            bits.append(f"all caps {cp['all_caps_pct']}%")
            if "vs_speech_median_s" in cp:
                bits.append(f"vs the voice {cp['vs_speech_median_s']:+}s" + (f", {cp['appears_before_word_pct']}% appear before the word"
                                                                           if "appears_before_word_pct" in cp else ""))
            row("Captions", "; ".join(bits))
            if cp.get("colours"):
                row("Caption colours", " ".join(f"`{c['hex']}` {c['share'] * 100:.0f}%" for c in cp["colours"]))
    if sp.get("words"):
        row("Speech", f"{sp['words']} words, **{sp['wpm_while_talking']} wpm while talking** ({sp['wpm_overall']} overall), "
            f"talking {sp['talk_coverage_pct']}% of the time, first word at {sp['first_word_at']}s, {sp['words_first_3s']} words in 3s")
        row("Pace by tenth (wpm)", " ".join(f"{int(x)}" for x in sp["wpm_by_tenth"]))
        row("Pauses", f"{sp['pauses_per_min']}/min over 0.25s, median {sp['pause_median']}s, {sp['pauses_over_07']} over 0.7s, longest {sp['longest_pause']}s")
        row("Sentences", f"{sp['sentences']} sentences, {sp['words_per_sentence']} words each, {sp['questions']} questions")
        row("Address", f"you {sp['you_per_100']} / I {sp['i_per_100']} / we {sp['we_per_100']} per 100 words, {sp['numbers']} numbers")
    if M["loudness"]:
        lo = M["loudness"]
        row("Loudness", f"{lo['lufs']} LUFS integrated, LRA {lo['lra']} LU, true peak {lo['true_peak']} dBFS")
    a = M["audio"] or {}
    if a.get("bed"):
        b = a["bed"]
        bits = [b["verdict"]]
        if "under_voice_db" in b:
            bits.append(f"{b['under_voice_db']} dB vs voice")
        if "ducking_db" in b:
            bits.append(f"{b['ducking_db']:+} dB in pauses")
        if "coverage_pct" in b:
            bits.append(f"present {b['coverage_pct']}% of the time")
        row("Under the voice", ", ".join(bits))
    if a.get("tempo"):
        tp = a["tempo"]
        row("Tempo", f"~{tp['bpm']} BPM (confidence {tp['confidence']})" + (
            f", cuts on beat {tp['cuts_on_beat_pct']}% vs chance {tp['chance_pct']}%" if "cuts_on_beat_pct" in tp else ""))
    if M["sfx"]:
        x = M["sfx"]
        row("Effect candidates", f"{x['count']} ({x['per_min']}/min, before listen.py sorts music notes and room sounds out), {x['near_cut_pct']}% just after a cut, {x['near_text_pct']}% with text, "
            f"kinds {x['kinds']}, by quarter {x['by_quarter']}, median {x['median_vs_voice_db']} dB vs voice")
    if M["voice"]:
        v = M["voice"]
        row("Voice tone", f"low {v['low_63_200_vs_1k_db']:+} dB, presence {v['presence_2_5k_vs_1k_db']:+} dB, air {v['air_5_8k_vs_1k_db']:+} dB re 1 kHz, crest {v['crest_db']} dB")
    if M["retention"]:
        r = M["retention"]
        row("Most replayed", ", ".join(f"{tc(p['t'])} ({p['value']})" for p in r["peaks"]))
    L += ["", "## Shot list", "", "| # | In | Length | Cut | Camera | Face | Text | Words |", "|---|---|---|---|---|---|---|---|"]
    for sh in SHOTS[:400]:
        z = f" x{sh['zoom_in']:.2f}" if sh.get("zoom_in") and sh["cut_in"] == "punch" else ""
        face = f"{sh.get('face_size') or '-'} {sh.get('face_pct', '')}%" if sh.get("face_pct") else "-"
        L.append(f"| {sh['n']} | {tc(sh['start'])} | {sh['dur']:.2f}s | {sh['cut_in']}{z} | {sh.get('camera') or '-'} | {face} | "
                 f"{','.join(sh.get('text') or []) or '-'} | {sh.get('words', '-')} |")
    if M["sfx"] and M["sfx"]["events"]:
        L += ["", "## Sound effect candidates", "", "| t | kind | dur | vs voice | after cut | after text | on beat |", "|---|---|---|---|---|---|---|"]
        for e in M["sfx"]["events"][:150]:
            L.append(f"| {tc(e['t'])} | {e['kind']} | {e['dur']}s | {e['vs_voice_db']} dB | {e['after_cut']} | {e['after_text']} | {'yes' if e['on_beat'] else ''} |")
    L += ["", "## Files", ""]
    for k, v in M["files"].items():
        if isinstance(v, list):
            for x in v:
                L.append(f"- {k}: `{Path(x).relative_to(WD)}`")
        elif v:
            L.append(f"- {k}: `{Path(v).relative_to(WD)}`")
    if M["errors"]:
        L += ["", "## Warnings", ""] + [f"- {e}" for e in M["errors"]]
    L += ["", "Measured by .claude/skills/reverse-video/scripts/measure.py. Cut detection covers hard cuts and fast transitions;"
          " dissolves and slow wipes need eyes. Face sizes, OCR and SFX are candidates: check them on the boards."]
    (WD / "summary.md").write_text("\n".join(L) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
