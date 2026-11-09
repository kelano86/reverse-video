"""Shared helpers for the reverse-video scripts: ffmpeg/ffprobe, decoding, fonts, time formatting, JSON."""
import json
import os
import subprocess
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


def run(cmd, text=True, **kw):
    return subprocess.run([str(c) for c in cmd], capture_output=True, text=text,
                          errors="replace" if text else None, **kw)


def log(*a):
    print(*a, flush=True)


def load(p, default=None):
    p = Path(p)
    if not p.exists():
        return default
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def save(p, data):
    p = Path(p)
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1, default=_np_default)


def _np_default(o):
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.floating,)):
        return float(o)
    if isinstance(o, np.ndarray):
        return o.tolist()
    raise TypeError(type(o))


def tc(t):
    """Seconds -> m:ss.s (or h:mm:ss for long videos)."""
    t = max(0.0, float(t))
    m, s = divmod(t, 60)
    if m >= 60:
        h, m = divmod(m, 60)
        return f"{int(h)}:{int(m):02d}:{s:04.1f}"
    return f"{int(m)}:{s:04.1f}"


def frac(x):
    try:
        n, _, d = str(x).partition("/")
        d = float(d or 1)
        return float(n) / d if d else 0.0
    except ValueError:
        return 0.0


def probe(mp4):
    r = run(["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", mp4])
    d = json.loads(r.stdout or "{}")
    streams = d.get("streams", [])
    v = next((s for s in streams if s.get("codec_type") == "video"), None)
    a = next((s for s in streams if s.get("codec_type") == "audio"), None)
    if v is None:
        raise SystemExit(f"no video stream in {mp4}")
    w, h = int(v["width"]), int(v["height"])
    rot = 0
    for sd in v.get("side_data_list") or []:
        if "rotation" in sd:
            rot = int(sd["rotation"])
    if abs(rot) in (90, 270):
        w, h = h, w
    fps = frac(v.get("avg_frame_rate")) or frac(v.get("r_frame_rate"))
    dur = float(d.get("format", {}).get("duration") or v.get("duration") or 0)
    return {
        "width": w, "height": h, "aspect": aspect(w, h), "fps": round(fps, 3), "duration": round(dur, 3),
        "vcodec": v.get("codec_name"), "pix_fmt": v.get("pix_fmt"),
        "color": {k: v.get(k) for k in ("color_space", "color_transfer", "color_primaries") if v.get(k)},
        "bitrate_kbps": round(int(d.get("format", {}).get("bit_rate") or 0) / 1000),
        "audio": bool(a), "audio_codec": a.get("codec_name") if a else None,
        "audio_rate": int(a["sample_rate"]) if a and a.get("sample_rate") else None,
        "audio_channels": a.get("channels") if a else None,
    }


def aspect(w, h):
    r = w / h
    for name, val in (("9:16", 9 / 16), ("4:5", 4 / 5), ("1:1", 1.0), ("16:9", 16 / 9), ("4:3", 4 / 3),
                      ("2.39:1", 2.39), ("3:4", 3 / 4)):
        if abs(r - val) / val < 0.03:
            return name
    return f"{w}:{h}"


def even(x):
    return max(2, int(round(x / 2)) * 2)


def decode(mp4, vf, w, h, pix="gray", ss=None, t=None):
    """Yield raw frames (h, w) or (h, w, 3) uint8 from ffmpeg after the filter chain vf."""
    ch = 3 if pix == "rgb24" else 1
    cmd = ["ffmpeg", "-v", "error"]
    if ss is not None:
        cmd += ["-ss", f"{ss:.3f}"]
    cmd += ["-i", str(mp4)]
    if t is not None:
        cmd += ["-t", f"{t:.3f}"]
    cmd += ["-an", "-vf", vf, "-f", "rawvideo", "-pix_fmt", pix, "-"]
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, bufsize=10 ** 7)
    fs = w * h * ch
    try:
        while True:
            b = p.stdout.read(fs)
            if len(b) < fs:
                break
            a = np.frombuffer(b, np.uint8)
            yield a.reshape(h, w, 3) if ch == 3 else a.reshape(h, w)
    finally:
        p.stdout.close()
        p.wait()


def audio_array(src, sr=16000, ch=1):
    raw = run(["ffmpeg", "-v", "error", "-i", src, "-vn", "-ac", str(ch), "-ar", str(sr), "-f", "s16le", "-"],
              text=False).stdout
    a = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
    return a.reshape(-1, ch) if ch > 1 else a


def font(size, bold=False):
    names = (["arialbd.ttf", "Arial Bold.ttf", "DejaVuSans-Bold.ttf"] if bold
             else ["arial.ttf", "Arial.ttf", "DejaVuSans.ttf"])
    dirs = ["C:/Windows/Fonts", "/System/Library/Fonts/Supplemental", "/Library/Fonts", "/usr/share/fonts/truetype/dejavu"]
    from PIL import ImageFont
    for d in dirs:
        for n in names:
            p = os.path.join(d, n)
            if os.path.exists(p):
                return ImageFont.truetype(p, size)
    return ImageFont.load_default()


def find_demucs():
    """A Python that can run Demucs: this venv's own (it's in requirements.txt), else
    $REVERSE_VIDEO_DEMUCS_PY for a Demucs installed somewhere else."""
    import importlib.util
    if importlib.util.find_spec("demucs") is not None:
        return sys.executable
    env = os.environ.get("REVERSE_VIDEO_DEMUCS_PY")
    if env and Path(env).exists():
        return env
    return None


def hexcol(rgb):
    return "#%02X%02X%02X" % tuple(int(max(0, min(255, round(c)))) for c in rgb[:3])
