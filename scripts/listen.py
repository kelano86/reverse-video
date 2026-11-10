"""Listen to a measured video with free, local models: what each sound effect is, what the music is
(genre, mood, instruments, where it stops), and whether there are voices the transcript missed.

Two open models, both run on the CPU, no account or key:
  AST  (MIT/ast-finetuned-audioset-10-10-0.4593) tags audio with AudioSet's 527 classes: sound effects
       (whoosh, click, ding, camera, typing...), music genres, music moods, instruments, kinds of voice.
  CLAP (laion/larger_clap_general) scores a clip against labels written in plain English, for what
       AudioSet has no class for (a riser, a UI notification, a lo-fi beat).
The first run downloads about 1.2 GB of weights (cached after that).

Usage: python -I listen.py <workdir> [--no-clap] [--hop 1.0]
Run measure.py first. With its Demucs stems, music and effects are judged on the non-voice stem and
voices on the voice stem; without them, everything is judged on the mix and effects aren't classified.
Writes listen.json, adds a "listen" block to measures.json and a Listening section to summary.md.
These are model judgements, not hearing: every label carries its score, and low scores say "unsure"."""
import argparse
import os
import re
import sys
import time
from pathlib import Path

import numpy as np

# public models, no token needed: keep Hugging Face from asking for one
os.environ.setdefault("HF_HUB_VERBOSITY", "error")
os.environ.setdefault("TRANSFORMERS_VERBOSITY", "error")

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import audio_array, load, log, save, tc  # noqa: E402

AST_ID = "MIT/ast-finetuned-audioset-10-10-0.4593"
CLAP_ID = "laion/larger_clap_general"

GENRES = ["Pop music", "Hip hop music", "Rock music", "Heavy metal", "Punk rock", "Rhythm and blues", "Soul music",
          "Reggae", "Country", "Funk", "Folk music", "Jazz", "Disco", "Classical music", "Opera", "Electronic music",
          "House music", "Techno", "Dubstep", "Drum and bass", "Electronica", "Electronic dance music", "Ambient music",
          "Trance music", "Music of Latin America", "Blues", "Music for children", "New-age music", "Vocal music",
          "A capella", "Afrobeat", "Gospel music", "Music of Asia", "Music of Bollywood", "Ska", "Independent music",
          "Beatboxing", "Swing music", "Middle Eastern music", "Flamenco", "Salsa music", "Christian music",
          "Traditional music", "Carnatic music", "Psychedelic rock", "Rock and roll", "Progressive rock", "Grunge"]
MOODS = ["Happy music", "Funny music", "Sad music", "Tender music", "Exciting music", "Angry music", "Scary music"]
MUSIC_USE = ["Background music", "Theme music", "Jingle (music)", "Soundtrack music", "Video game music",
             "Dance music", "Lullaby", "Christmas music", "Wedding music"]
INSTRUMENTS = ["Piano", "Electric piano", "Synthesizer", "Sampler", "Guitar", "Electric guitar", "Acoustic guitar",
               "Bass guitar", "Drum kit", "Drum machine", "Drum", "Snare drum", "Bass drum", "Hi-hat", "Cymbal",
               "Percussion", "Orchestra", "String section", "Violin, fiddle", "Cello", "Brass instrument", "Trumpet",
               "Saxophone", "Flute", "Organ", "Harp", "Glockenspiel", "Marimba, xylophone", "Vibraphone", "Choir",
               "Ukulele", "Banjo", "Accordion", "Harmonica", "Theremin", "Scratching (performance technique)"]
VOICE = ["Male speech, man speaking", "Female speech, woman speaking", "Child speech, kid speaking",
         "Speech synthesizer", "Narration, monologue", "Conversation", "Whispering", "Laughter", "Singing",
         "Shout", "Screaming", "Crowd", "Applause", "Cheering"]
NOT_SFX = set(GENRES + MOODS + MUSIC_USE + ["Music", "Speech", "Silence", "Musical instrument", "Inside, small room",
              "Inside, large room or hall", "Outside, urban or manmade", "Narration, monologue", "Conversation",
              "Male speech, man speaking", "Female speech, woman speaking", "Noise", "Sound effect"])

SFX_VOCAB = ["a whoosh sound effect", "a fast swoosh transition", "a riser building up tension", "a deep bass boom impact",
             "a cinematic hit", "a soft pop", "a bubble pop", "a mouse click", "a user interface notification sound",
             "a ding bell", "a cash register ka-ching", "a camera shutter click", "keyboard typing", "a record scratch",
             "a digital glitch", "a swipe sound", "a sparkle chime", "a short beep", "a zap", "a cartoon boing",
             "a slide whistle", "a punch impact", "an explosion", "a heartbeat", "a clock ticking", "a phone vibrating",
             "a notification chime", "a video game coin sound", "a mechanical counter ticking", "a door knock",
             "a finger tap on a desk", "applause", "laughter", "a person speaking", "a computer voice speaking",
             # rejection labels: when one of these wins, the candidate isn't an added effect
             "a drum hit inside music", "a kick drum", "a snare drum", "a cymbal crash", "a guitar note",
             "a bass note", "a piano note", "a musical note from background music", "room noise", "silence"]
MUSICAL = {"a drum hit inside music", "a kick drum", "a snare drum", "a cymbal crash", "a guitar note", "a bass note",
           "a piano note", "a musical note from background music"}
NOTHING = {"room noise", "silence"}
MUSIC_VOCAB = ["a lo-fi hip hop beat", "a trap beat", "an upbeat pop instrumental", "a cinematic orchestral score",
               "an ambient pad drone", "synthwave", "electronic dance music", "house music",
               "corporate upbeat background music", "acoustic guitar music", "solo piano music", "jazz",
               "rock with electric guitars", "phonk", "drum and bass", "chillhop", "minimal tech house",
               "epic trailer music", "playful quirky music", "tense suspense music", "inspirational uplifting music",
               "a viral meme song", "no music, just room noise"]
MOOD_VOCAB = ["energetic music", "calm music", "playful music", "tense music", "inspiring music", "dark music",
              "happy music", "sad music", "dreamy music", "aggressive music"]


def ascii_safe(s):
    return re.sub(r"\s+", " ", s)


class Ast:
    def __init__(self):
        import torch
        from transformers import ASTForAudioClassification, AutoFeatureExtractor
        torch.set_num_threads(os.cpu_count() or 8)
        self.torch = torch
        self.fe = AutoFeatureExtractor.from_pretrained(AST_ID)
        self.m = ASTForAudioClassification.from_pretrained(AST_ID).eval()
        self.labels = [self.m.config.id2label[i] for i in range(len(self.m.config.id2label))]
        self.idx = {l: i for i, l in enumerate(self.labels)}

    def probs(self, clips, batch=8):
        out = []
        with self.torch.no_grad():
            for i in range(0, len(clips), batch):
                x = self.fe([c.astype(np.float32) for c in clips[i:i + batch]], sampling_rate=16000, return_tensors="pt")
                out.append(self.torch.sigmoid(self.m(**x).logits).numpy())
        return np.concatenate(out) if out else np.zeros((0, len(self.labels)))

    def pick(self, p, names, k=3, floor=0.02):
        ids = [self.idx[n] for n in names if n in self.idx]
        sc = sorted(((float(p[i]), self.labels[i]) for i in ids), reverse=True)
        return [{"label": l, "score": round(s, 3)} for s, l in sc[:k] if s >= floor]

    def top(self, p, k=5, exclude=()):
        order = np.argsort(-p)
        res = []
        for i in order:
            if self.labels[i] in exclude:
                continue
            res.append({"label": self.labels[i], "score": round(float(p[i]), 3)})
            if len(res) >= k:
                break
        return res


class Clap:
    def __init__(self):
        import torch
        from transformers import ClapModel, ClapProcessor
        self.torch = torch
        self.p = ClapProcessor.from_pretrained(CLAP_ID)
        self.m = ClapModel.from_pretrained(CLAP_ID).eval()
        self.cache = {}

    @staticmethod
    def _t(x, attr):
        if hasattr(x, attr):
            return getattr(x, attr)
        if hasattr(x, "pooler_output"):
            return x.pooler_output
        return x

    def text(self, labels):
        key = tuple(labels)
        if key not in self.cache:
            with self.torch.no_grad():
                t = self.p(text=list(labels), return_tensors="pt", padding=True)
                e = self._t(self.m.get_text_features(**t), "text_embeds")
            self.cache[key] = e / e.norm(dim=-1, keepdim=True)
        return self.cache[key]

    def audio(self, clips48):
        with self.torch.no_grad():
            try:
                a = self.p(audio=[c.astype(np.float32) for c in clips48], sampling_rate=48000, return_tensors="pt")
            except TypeError:
                a = self.p(audios=[c.astype(np.float32) for c in clips48], sampling_rate=48000, return_tensors="pt")
            e = self._t(self.m.get_audio_features(**a), "audio_embeds")
        return e / e.norm(dim=-1, keepdim=True)

    def rank(self, aemb, labels, k=3):
        """aemb: one or more audio embeddings (averaged). Softmax over the labels, CLAP's own temperature."""
        a = aemb.mean(0, keepdim=True)
        a = a / a.norm(dim=-1, keepdim=True)
        scale = float(self.m.logit_scale_a.exp().detach()) if hasattr(self.m, "logit_scale_a") else 100.0
        cos = (a @ self.text(labels).T)[0]
        pr = self.torch.softmax(cos * scale, dim=0).numpy()
        cos = cos.numpy()
        order = np.argsort(-pr)[:k]
        return [{"label": labels[i], "p": round(float(pr[i]), 3), "cos": round(float(cos[i]), 3)} for i in order]


def windows(a, sr, win, hop):
    n = len(a)
    starts = np.arange(0, max(1, n - int(win * sr) + 1), int(hop * sr))
    return [(s / sr, a[s:s + int(win * sr)]) for s in starts]


def rms_db(x):
    return 20 * np.log10(np.sqrt(np.mean(x ** 2) + 1e-12)) if len(x) else -120.0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("workdir")
    ap.add_argument("--no-clap", action="store_true")
    ap.add_argument("--hop", type=float, default=0)
    a = ap.parse_args()
    WD = Path(a.workdir).resolve()
    M = load(WD / "measures.json")
    if M is None:
        raise SystemExit("run measure.py first")
    T0 = time.time()
    dur = M["format"]["duration"]
    hop = a.hop or (1.0 if dur <= 180 else 2.0 if dur <= 600 else 5.0)
    voc = WD / "cache" / "stems" / "htdemucs" / "audio44" / "vocals.wav"
    acc = voc.with_name("no_vocals.wav")
    stems = voc.exists() and acc.exists()
    music_src = acc if stems else WD / "video.mp4"
    log(f"[{time.time() - T0:5.1f}s] loading AST" + ("" if a.no_clap else " and CLAP") + f"; music judged on {'the non-voice stem' if stems else 'the mix'}")
    ast = Ast()
    clap = None if a.no_clap else Clap()
    m16 = audio_array(music_src, 16000)
    m48 = audio_array(music_src, 48000) if clap else None
    words = [w for s in (load(WD / "cache" / "transcript.json", {}) or {}).get("segments", []) for w in s["words"]]

    # ---- timeline: AudioSet tags every hop seconds on the music/effects layer
    log(f"[{time.time() - T0:5.1f}s] tagging the {'non-voice stem' if stems else 'mix'} every {hop:g}s")
    wins = windows(m16, 16000, 2.0, hop)
    P = ast.probs([w for _, w in wins])
    imus = ast.idx["Music"]
    timeline = []
    for (t, w), p in zip(wins, P):
        lvl = rms_db(w)
        timeline.append({"t": round(t, 1), "db": round(lvl, 1), "music": round(float(p[imus]), 3),
                         "genre": (ast.pick(p, GENRES, 1) or [{"label": None}])[0]["label"],
                         "mood": (ast.pick(p, MOODS, 1) or [{"label": None}])[0]["label"],
                         "top": [x["label"] for x in ast.top(p, 3)]})
    on = np.array([x["music"] >= 0.3 and x["db"] > -50 for x in timeline])
    music = {"present_pct": round(float(on.mean() * 100), 1) if len(on) else 0}
    if on.any():
        Pm = P[on]
        mean = Pm.mean(0)
        music.update({"genres": ast.pick(mean, GENRES, 3, 0.005), "moods": ast.pick(mean, MOODS, 3, 0.005),
                      "use": ast.pick(mean, MUSIC_USE, 2, 0.005), "instruments": ast.pick(mean, INSTRUMENTS, 5, 0.02)})
        # where it plays and where it stops
        runs, cur = [], None
        for x, o in zip(timeline, on):
            if o and cur is None:
                cur = [x["t"], x["t"] + hop]
            elif o:
                cur[1] = x["t"] + hop
            elif cur is not None:
                runs.append(cur)
                cur = None
        if cur:
            runs.append(cur)
        runs = [[float(s), float(e)] for s, e in runs]
        merged = []
        for s, e in runs:
            if merged and s - merged[-1][1] <= hop + 0.01:
                merged[-1][1] = e
            else:
                merged.append([s, e])
        runs = merged
        music["plays"] = [[round(s, 1), round(min(e + 1.0, dur), 1)] for s, e in runs]
        gaps = [[round(runs[i][1] + 1.0, 1), round(runs[i + 1][0], 1)] for i in range(len(runs) - 1)
                if runs[i + 1][0] - runs[i][1] > hop]
        music["stops"] = gaps
        if clap:
            log(f"[{time.time() - T0:5.1f}s] CLAP on the music")
            segs48 = []
            for s, e in runs:
                for t in np.arange(s, e, 10.0):
                    seg = m48[int(t * 48000):int(min(e, t + 10) * 48000)]
                    if len(seg) > 48000 * 2:
                        segs48.append(seg)
            if segs48:
                emb = clap.audio(segs48[:24])
                music["clap_style"] = clap.rank(emb, MUSIC_VOCAB, 3)
                music["clap_mood"] = clap.rank(emb, MOOD_VOCAB, 3)
    else:
        mean = P.mean(0) if len(P) else np.zeros(len(ast.labels))
        music["verdict"] = "no music: the layer is " + (", ".join(x["label"] for x in ast.top(mean, 4)) or "silent")

    # ---- sound effects: classify every transient measure.py found on the non-voice stem
    sfx_out = []
    events = ((M.get("sfx") or {}).get("events")) or []
    if stems and events:
        log(f"[{time.time() - T0:5.1f}s] classifying {len(events)} sound-effect candidates")
        clips16, clips48 = [], []
        for e in events:
            s = max(0.0, e["t"] - 0.12)
            ln = min(1.5, max(0.6, e["dur"] + 0.3))
            clips16.append(m16[int(s * 16000):int((s + ln) * 16000)])
            if clap:
                clips48.append(m48[int(s * 48000):int((s + ln) * 48000)])
        Pe = ast.probs(clips16)
        # how much each candidate sounds like the music just around it: a melody note in a plucky bed
        # gets effect names from CLAP ("a coin sound", "a chime") but sounds like its neighbours, while
        # an effect laid over the bed doesn't (tested on a reel with no effects and on the same reel with
        # 8 planted ones: notes 0.71-0.90, planted effects 0.52-0.63, a boom 0.76)
        bed_sim = {}
        if clap and music.get("present_pct", 0) >= 30:
            cand_t = [e["t"] for e in events]
            n48 = len(m48) / 48000

            def clip06(t):
                s0 = max(0.0, t - 0.12)
                return m48[int(s0 * 48000):int((s0 + 0.6) * 48000)]
            for i, t in enumerate(cand_t):
                ctx = [t + d for d in (-2.0, -1.5, -1.0, 1.0, 1.5, 2.0) if 0.2 < t + d < n48 - 0.8
                       and all(abs(t + d - o) > 0.35 for j, o in enumerate(cand_t) if j != i)]
                if len(ctx) < 2:
                    ctx = [t + d for d in (-2.0, -1.0, 1.0, 2.0) if 0.2 < t + d < n48 - 0.8]
                if ctx:
                    E = clap.audio([clip06(t)] + [clip06(x) for x in ctx])
                    bed_sim[i] = round(float((E[1:] @ E[0]).max()), 3)
        for i, (e, p) in enumerate(zip(events, Pe)):
            row = {"t": e["t"], "measured_kind": e["kind"], "after_cut": e.get("after_cut"), "on_beat": e.get("on_beat"),
                   "audioset": ast.top(p, 4, exclude=NOT_SFX)}
            if clap:
                row["clap"] = clap.rank(clap.audio([clips48[i]]), SFX_VOCAB, 3)
            if i in bed_sim:
                row["sounds_like_bed"] = bed_sim[i]
            best = row.get("clap", [{}])[0]
            ast_best = row["audioset"][0] if row["audioset"] else {"label": None, "score": 0}
            # a "music" call only makes sense when there is music on this layer
            musical = best.get("label") in MUSICAL and music.get("present_pct", 0) >= 10
            voice = best.get("label") in ("a person speaking", "a computer voice speaking", "laughter")
            # CLAP's softmax is overconfident on anything; its raw similarity separates real effects
            # (0.2-0.32 in testing) from music notes and room sounds (mostly under 0.2)
            clap_ok = best.get("p", 0) >= 0.4 and best.get("cos", 0) >= 0.2
            like_bed = row.get("sounds_like_bed", 0) >= 0.70
            if musical or (like_bed and not voice):
                call = "part of the music"
            elif voice:
                call = "a voice, not an effect"
            elif best.get("label") in NOTHING or best.get("label") in MUSICAL:
                call = "no clear effect (room or background)"
            elif clap_ok:
                call = best["label"]
            elif ast_best["score"] >= 0.3:
                call = ast_best["label"]
            else:
                call = "unsure: " + (best.get("label") or ast_best["label"] or "?")
            row["call"] = call
            row["sure"] = bool(row.get("sounds_like_bed", 0) >= 0.78 if like_bed and not musical
                               else clap_ok or ast_best["score"] >= 0.3)
            sfx_out.append(row)

    # ---- voices: what kind of voice, and any voice the transcript doesn't have
    voices = None
    if stems:
        log(f"[{time.time() - T0:5.1f}s] voices")
        v16 = audio_array(voc, 16000)
        vw = windows(v16, 16000, 2.0, max(hop, 1.0))
        loud = [(t, w) for t, w in vw if rms_db(w) > -38]
        Pv = ast.probs([w for _, w in loud]) if loud else np.zeros((0, len(ast.labels)))
        untx = []
        kinds = np.zeros(len(ast.labels))
        for (t, w), p in zip(loud, Pv):
            kinds += p
            said = any(t - 0.3 <= x["s"] <= t + 2.3 for x in words)
            vk = ast.pick(p, VOICE, 2, 0.05)
            if not said and vk:
                untx.append({"t": round(float(t), 1), "voice": vk})
        voices = {"kinds": ast.pick(kinds / max(1, len(loud)), VOICE, 4, 0.02),
                  "windows_with_voice": len(loud), "voice_without_transcript": untx[:30],
                  "voice_without_transcript_s": round(len(untx) * max(hop, 1.0), 1)}

    L = {"models": {"ast": AST_ID, "clap": None if a.no_clap else CLAP_ID}, "layer": "non-voice stem" if stems else "mix",
         "hop_s": hop, "music": music, "sfx": sfx_out, "voices": voices, "timeline": timeline}
    save(WD / "listen.json", L)
    M["listen"] = {k: v for k, v in L.items() if k != "timeline"}
    save(WD / "measures.json", M)
    write_summary(WD, L)
    log(f"[{time.time() - T0:5.1f}s] done: listen.json and a Listening section in summary.md")


def fmt(xs, key="score"):
    return ", ".join(f"{x['label']} {x[key]:.2f}" for x in xs) if xs else "none"


def write_summary(WD, L):
    p = WD / "summary.md"
    s = p.read_text(encoding="utf-8") if p.exists() else ""
    s = re.sub(r"\n## Listening\n.*?(?=\n## |\Z)", "\n", s, flags=re.S)
    m = L["music"]
    out = ["", "## Listening", "",
           f"Free local models ({L['models']['ast']}" + (f", {L['models']['clap']}" if L["models"]["clap"] else "") +
           f") on the {L['layer']}. Scores are model confidence (AudioSet 0-1, CLAP share across its labels), not certainty.", "",
           "| What | Heard |", "|---|---|",
           f"| Music | {m.get('present_pct')}% of the time" + (f", plays " + ", ".join(f"{tc(a)}-{tc(b)}" for a, b in m["plays"]) if m.get("plays") else "")
           + (f". {m['verdict']}" if m.get("verdict") else "") + " |"]
    if m.get("genres"):
        weak = max([x["score"] for x in m["genres"] + m.get("moods", [])] or [0]) < 0.1
        out.append(f"| Genre (AudioSet) | {fmt(m['genres'])}" + (" (too weak to use: AudioSet isn't sure)" if weak else "") + " |")
        out.append(f"| Mood (AudioSet) | {fmt(m['moods'])} |")
        out.append(f"| Instruments | {fmt(m['instruments'])} |")
        if m.get("use"):
            out.append(f"| Kind of music | {fmt(m['use'])} |")
    if m.get("clap_style"):
        out.append(f"| Style (CLAP) | {fmt(m['clap_style'], 'p')} |")
        out.append(f"| Mood (CLAP) | {fmt(m['clap_mood'], 'p')} |")
    if m.get("stops"):
        out.append(f"| Music stops | " + ", ".join(f"{tc(a)}-{tc(b)}" for a, b in m["stops"]) + " |")
    v = L.get("voices")
    if v:
        out.append(f"| Voices | {fmt(v['kinds'])} |")
        if v["voice_without_transcript"]:
            out.append(f"| Voice the transcript missed | about {v['voice_without_transcript_s']}s, at "
                       + ", ".join(f"{tc(x['t'])} ({fmt(x['voice'])})" for x in v["voice_without_transcript"][:8]) + " |")
    if L["sfx"]:
        fx = [e for e in L["sfx"] if not e["call"].startswith(("part of the music", "a voice", "no clear effect"))]
        sure = [e for e in fx if e["sure"]]
        mus = sum(1 for e in L["sfx"] if e["call"] == "part of the music")
        from collections import Counter
        names = Counter(e["call"] for e in sure)
        out.append(f"| Added effects | {len(sure)} named with confidence, {len(fx) - len(sure)} unsure, {mus} candidates were the music "
                   f"and {len(L['sfx']) - len(fx) - mus} a voice or room sound (of {len(L['sfx'])} candidates)"
                   + (": " + ", ".join(f"{k} x{v}" for k, v in names.most_common()) if names else "") + " |")
        out += ["", "Like the bed: CLAP similarity to the music just around it; 0.70 or more counts as part of the music.",
                "", "| t | Call | Sure | AudioSet | CLAP | Like the bed | After cut |", "|---|---|---|---|---|---|---|"]
        for e in L["sfx"]:
            out.append(f"| {tc(e['t'])} | {e['call']} | {'yes' if e['sure'] else 'no'} | {fmt(e['audioset'][:2])} | "
                       f"{fmt(e.get('clap', [])[:2], 'p')} | {e.get('sounds_like_bed', '-')} | {e['after_cut']} |")
    s = s.rstrip() + "\n" + "\n".join(out) + "\n"
    p.write_text(s, encoding="utf-8")


if __name__ == "__main__":
    main()
