"""Several measured videos side by side. What holds steady across a creator's videos is the style; what
moves from video to video is the content (or a choice per topic). Reads each <workdir>/measures.json.

Usage: python -I compare.py <workdir> <workdir> [...] [--out compare.md]
A row is marked STEADY when the videos agree (numbers within ±20% of their median, or the same label in
at least 3 of 4 videos) and VARIES when they spread wide (beyond ±50%, or no majority label)."""
import argparse
import sys
from collections import Counter
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import load  # noqa: E402

ROWS = [
    ("Duration (s)", "format.duration"), ("Aspect", "format.aspect"), ("Views", "source.view_count"),
    ("Cuts / min", "shots.cuts_per_min"), ("Mean shot (s)", "shots.mean"), ("Median shot (s)", "shots.median"),
    ("Shots under 1 s (%)", "shots.under_1s_pct"), ("First cut (s)", "shots.first_cut_at"),
    ("Cuts in first 5 s", "shots.cuts_in_first_5s"), ("Jump cuts (%)", "_jump_pct"), ("Punch-ins (%)", "_punch_pct"),
    ("Cuts on a word start (%)", "shots.cuts_at_word_start_pct"), ("Main camera move", "_camera_top"),
    ("Face on screen (%)", "faces.on_screen_pct"), ("Face size", "faces.size_median"), ("Eyeline y", "faces.eyeline_y_median"),
    ("Brightness", "colour.luma_mean"), ("Saturation", "colour.saturation"), ("Warmth", "colour.warmth"),
    ("Text on screen (% frames)", "text.frames_with_text_pct"), ("Caption words", "text.captions.words_per_caption_median"),
    ("Caption hold (s)", "text.captions.hold_median_s"), ("Caption y (%)", "text.captions.y_centre_pct"),
    ("Caption height (% frame)", "text.captions.text_height_pct_of_frame"), ("Captions all caps (%)", "text.captions.all_caps_pct"),
    ("Caption vs voice (s)", "text.captions.vs_speech_median_s"),
    ("WPM while talking", "speech.wpm_while_talking"), ("Talking (% of time)", "speech.talk_coverage_pct"),
    ("Words in first 3 s", "speech.words_first_3s"), ("Words / sentence", "speech.words_per_sentence"),
    ("Questions", "speech.questions"), ("you / 100 words", "speech.you_per_100"), ("I / 100 words", "speech.i_per_100"),
    ("Loudness (LUFS)", "loudness.lufs"), ("Non-voice layer", "audio.bed.verdict"), ("Music (% of time, heard)", "listen.music.present_pct"),
    ("Bed vs voice (dB)", "audio.bed.under_voice_db"),
    ("Tempo (BPM)", "audio.tempo.bpm"), ("Effect candidates / min", "sfx.per_min"), ("Candidates just after a cut (%)", "sfx.near_cut_pct"),
]


def get(m, path):
    if path == "_jump_pct" or path == "_punch_pct":
        ct = (m.get("shots") or {}).get("cut_types") or {}
        tot = sum(ct.values())
        return round(ct.get(path[1:-4], 0) / tot * 100, 1) if tot else None
    if path == "_camera_top":
        ts = ((m.get("camera") or {}).get("time_share_pct")) or {}
        return max(ts, key=ts.get) if ts else None
    cur = m
    for k in path.split("."):
        if not isinstance(cur, dict):
            return None
        cur = cur.get(k)
    return cur


def verdict(vals):
    vals = [v for v in vals if v is not None]
    if len(vals) < 2:
        return "", ""
    if all(isinstance(v, (int, float)) for v in vals):
        med = float(np.median(vals))
        spread = max(abs(v - med) for v in vals) / (abs(med) if med else 1)
        tag = "STEADY" if spread <= 0.2 else "VARIES" if spread > 0.5 else ""
        return f"{med:g}", tag
    c = Counter(str(v) for v in vals).most_common(1)[0]
    share = c[1] / len(vals)
    return c[0], "STEADY" if share >= 0.75 else "VARIES" if share < 0.5 else ""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("workdirs", nargs="+")
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    ms = []
    for w in a.workdirs:
        m = load(Path(w) / "measures.json")
        if m is None:
            print(f"skip {w}: no measures.json")
            continue
        ms.append((Path(w), m))
    heads = [(m["source"].get("id") or w.parent.name or w.name)[:14] for w, m in ms]
    L = ["| Metric | " + " | ".join(heads) + " | Median / mode | |", "|---" * (len(heads) + 3) + "|"]
    for name, path in ROWS:
        vals = [get(m, path) for _, m in ms]
        if all(v is None for v in vals):
            continue
        med, tag = verdict(vals)
        cells = [("" if v is None else f"{v:g}" if isinstance(v, float) else str(v)) for v in vals]
        L.append(f"| {name} | " + " | ".join(cells) + f" | {med} | {tag} |")
    L += ["", "Palettes (top 4 per video):", ""]
    for (w, m), h in zip(ms, heads):
        pal = ((m.get("colour") or {}).get("palette")) or []
        L.append(f"- {h}: " + " ".join(f"`{p['hex']}`" for p in pal[:4]))
    out = "\n".join(L) + "\n"
    if a.out:
        Path(a.out).write_text(out, encoding="utf-8")
        print("wrote", a.out)
    print(out)


if __name__ == "__main__":
    main()
