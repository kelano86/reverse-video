---
name: reverse-video
description: Reverse-engineer a video's whole style from a YouTube, Instagram, TikTok or X link (or a local file) so you can make videos that work the same way. Covers everything the video is made of - script and structure, hook, pacing, shots and framing, layouts, editing and transitions, camera moves and zooms, motion graphics and animation timing, captions and typography, colour and grade, music, sound effects, voice and loudness, packaging. Measures what numbers can settle (every cut, shot lengths, words per minute, frame-accurate caption timing, palette, face framing, music bed, SFX placement, loudness), names the sound effects, music genre and mood with free local audio models, reads frames and frame-by-frame strips for the rest, and writes a teardown, a machine-readable style spec and a plan to recreate it. Everything runs locally for free, with no accounts or API keys. Use for `reverse [url or file ...]`, "reverse engineer this video", "tear down this reel", "how is this edited", "break down this creator's style", "I want my videos to look and feel like this", or any request to copy, study or match a video's style. Works on one video, or several from one creator to separate the style from the content.
---

# Reverse Video

Take a video apart until every choice in it is named, measured where it can be, and written down as
something you can rebuild. The teardown answers three questions: **what is it made of, why does it
hold attention, and how would you make one.**

Numbers first, eyes second, opinions last. A script measures everything a number can settle; you
then look at the boards and strips for what numbers can't (fonts, animation style, what the shot is
of), and only then explain why it works.

Everything here is free and local: yt-dlp downloads, ffmpeg and OpenCV measure, Whisper transcribes,
Demucs splits the voice from the music, and two open audio models listen. No account, no API key.

## What you get

```
teardowns/<slug>/        in the user's current project folder, unless they name another place
  teardown.md      the style bible (template: references/teardown-template.md)
  style.json       the same, as a spec a build can read (references/style-spec.md)
  img/             the pacing map, shot boards, hook sheet, palette, text crops and strips you cite
  work/            video, frames, transcript, cache, measures.json, summary.md
```

`<slug>` is `<creator>-<short-topic>` for one video (`janedoe-coffee-vlog`), `<creator>-style` for
several. `work/` holds someone else's video and words: keep it out of anything published (add
`teardowns/*/work/` to `.gitignore` in a git repo). The teardown quotes at most a short line.

## Setup (once per machine)

Paths below: `SKILL_DIR` is the folder this file is in. `S` = `SKILL_DIR/scripts`. `PY` = the skill's
venv python, always run with `-I`: `SKILL_DIR/.venv/Scripts/python.exe` on Windows,
`SKILL_DIR/.venv/bin/python` on Mac and Linux.

First time, run the check. It lists anything missing with the command that fixes it:

```bash
$PY -I $S/doctor.py
```

If `.venv` doesn't exist yet, set it up from `SKILL_DIR` (needs [uv](https://docs.astral.sh/uv/),
which also fetches the right Python):

```bash
uv venv --python 3.12 .venv
uv pip install -r scripts/requirements.txt --torch-backend cpu
uv pip install --no-deps rapidocr_onnxruntime
```

Also needed on the PATH: **ffmpeg** (with ffprobe), and **Node** or **Deno** for YouTube downloads.
Models download on first use and are cached (about 3 GB in all: Whisper medium, AST, CLAP, Demucs,
YuNet). Tell the user the first run is slow because of that.

## Steps

### 1. Scope

- One link → a teardown of that video.
- "This creator's style" → 3 to 5 videos: their best performers in the format the user cares about
  plus one typical one. One video can't separate their style from that video's topic; say so if
  that's all there is. To find the outliers for free, list their recent uploads with views:
  `$PY -I -m yt_dlp --flat-playlist -I 1:40 --print "%(view_count)s|%(id)s|%(title)s" "<channel url>/shorts"`
  (`/videos` for long form) and compare against the median.
- Ask nothing you can default. Ask only when the goal is unclear in a way that changes the work
  (e.g. "match the edit" vs "match the script" when only one matters).

### 2. Fetch

```bash
$PY -I $S/fetch.py "<url or file>" teardowns/<slug>/work               # one video
$PY -I $S/fetch.py "<url>" teardowns/<slug>/work/<video-id>             # several
```

Links go through yt-dlp. If Instagram (or TikTok, X) refuses without a signed-in session, fetch.py
says so: ask the user before adding `--cookies-from-browser <browser>` (yt-dlp then reads that
browser's cookies on this computer; Firefox works best, Chrome on Windows often can't be read), or
ask them to download the video and give you the file. `meta.json` keeps title, caption, channel,
date, views, likes, comments, and for YouTube the chapters and the most-replayed heatmap.

### 3. Measure

```bash
$PY -I $S/measure.py <workdir>          # --stems on|off, --ocr off, --model small, --lang en
```

Roughly 2x the video's length for short form on a recent desktop CPU (a 2:19 Short took about 4
minutes, most of it OCR, Whisper and Demucs); a laptop can take twice that, and `--model small` makes
Whisper faster. Long form: run it in the background; Demucs is skipped past ~6.5 minutes unless
`--stems on`. Every step is cached, so a re-run takes seconds.

It writes `summary.md` (the hard numbers and the shot list), `measures.json` (everything),
`transcript.txt` (words with `[#n]` where shot n starts), `onscreen_text.txt` and `img/`.
Read the warnings at the bottom of `summary.md` before trusting a section.

### 4. Read the numbers, then the pacing map

Read `summary.md` whole. Then look at `img/pacing_map.png`: one picture of the video's rhythm with
shots, cut rate, speech rate, camera moves, face, text, voice against music, SFX, colour and the
YouTube replay curve on one time axis. Note where things bunch up and where they go quiet: that is
the structure, before you've read a word.

### 5. Look

Viewing order, and a budget so long videos don't eat the context:

| What | Short form | Long form |
|---|---|---|
| `img/hook_5s.jpg` (first 5 s at 10 fps) | always | always |
| `img/shots_*.jpg` (one frame per shot, cut type on the bar) | all | all pages |
| `img/sheet_*.jpg` (every 0.25-1 s) | all | first 90 s only |
| `img/spine.jpg` (60 frames across the video) | n/a | always |
| `img/text_crops.jpg` (text at full resolution) | always | always |
| `img/palette.jpg` | always | always |

While looking, build the **shot taxonomy**: name every distinct composition (full-bleed face, face
bottom + screen top, screen only, title card, b-roll, ...), count them, note what each is used for.
The checklist in `references/checklist.md` lists what to look for in every dimension: go through it.

### 6. Read the motion

Numbers find motion; strips show what it is. For every element that animates (titles, captions,
graphics, transitions, zooms, highlight boxes), run a strip on one or two instances:

```bash
$PY -I $S/strips.py <workdir> 12.4,0:31.2 --dur 0.8                    # every frame, 0.8 s
$PY -I $S/strips.py <workdir> 12.4 --dur 0.6 --crop 0.1,0.7,0.8,0.25   # zoom on one element
```

Each strip prints when the motion starts, peaks and settles, and its shape (ease-out, ease-in, even,
overshoot). Read the frames to get the entrance type (scale pop, slide, mask, type-on, blur), the
duration in frames at the video's fps, overshoot, stagger and the exit. Six to twelve strips is usual
for short form. Where to point them: cuts marked `transition` or `punch` on the shot boards, `snap
zoom` shots, the first frame of each title or graphic in `onscreen_text.txt`, and SFX candidates
(something visual usually lands with the sound).

A `transition` in the measurements is any change spread over several frames: check it in a strip,
because scrolling or a fast camera move reads the same as a whip or zoom transition.

### 7. Read the script

From `transcript.txt` (shot markers inline) and the speech numbers:

- **Beat map**: every beat with its time, what it does (hook, context, promise, proof, step,
  re-hook, payoff, CTA), what's on screen at the time, and the device it uses.
- **Hook anatomy**, first 3 seconds and first 15: the visual hook, the spoken line, the on-screen text,
  when the first cut lands, and what's promised.
- **Retention devices**: open loops and where they close, re-hooks, stakes, pattern interrupts. Line
  them up with the replay heatmap peaks and dips when there is one.
- **Language**: wpm, sentence length, you vs I, questions, numbers, reading level, tone.
- **CTA**: where, what, how it's set up.

Then write the **formula** as a fill-in template with new example words, never their lines. If the
user has script templates or script skills of their own, say which one this is closest to, or that
it's a new format.

### 8. Sound: listen

```bash
$PY -I $S/listen.py <workdir>          # --no-clap for AudioSet tags only, --hop 2 for long videos
```

Two free models that run on the CPU with no key do the listening (first run downloads ~1.2 GB):
**AST** tags the audio with AudioSet's 527 classes (whoosh, click, ding, camera, typing, music genres,
music moods, instruments, kinds of voice, including "Speech synthesizer" for app and AI voices), and
**CLAP** scores clips against plain-English labels for what AudioSet lacks (a riser, a UI notification,
a lo-fi beat). It writes `listen.json` and a Listening section in `summary.md`:

- **Music**: when it plays and stops, genre, mood, instruments, style (AudioSet and CLAP side by side).
- **Each SFX candidate** from measure.py gets a call: what it is, or "part of the music" (a drum hit),
  or "a voice, not an effect", with both models' scores and whether it's sure.
- **Voices**: what kind (male, female, synthesized) and any voice the transcript missed.

measure.py's "effect candidates" count includes music notes and room sounds; quote listen.py's "Added
effects" line instead. Put it together with the numbers: is there a bed (`audio.bed`), how far under
the voice, does it duck, its tempo, whether cuts follow the beat, which effects mark what. Quote the
scores: these are model judgements, not hearing. When the two models disagree, or a call isn't sure,
say so and check what happens on screen at that moment (a strip). Without Demucs stems, listen.py
judges the mix and can't classify effects.

### 9. Several videos

```bash
$PY -I $S/compare.py work/<id1> work/<id2> work/<id3> --out work/compare.md
```

STEADY rows are the style. VARIES rows are content or per-topic choices: don't put them in the
spec as rules. Read the boards of every video before calling a visual element part of the style.

### 10. Write

`teardown.md` from `references/teardown-template.md`, `style.json` from `references/style-spec.md`.
Copy the images you cite into `<slug>/img/` (the pacing map, shot boards, hook sheet, palette, text
crops, the strips that prove an animation): not the contact sheets, they stay in `work/`.

Tag every claim: **(measured)** from `measures.json`, **(heard)** from `listen.json`, **(seen 0:12)** from a
frame or strip, or **(inferred)**. A rule in the spec with no tag isn't finished.

### 11. Recreate plan

The last section of the teardown maps every element to how the user would build it, in the tools
they use (ask once if you can't tell from the project: CapCut, Premiere, DaVinci Resolve, Final Cut,
After Effects, Remotion, ...):

- Script → a fill-in template, or the user's own script format if they have one.
- Edit → which of their tools fits, with the settings: cut rhythm, zoom rates, transition lengths.
- Each motion element → a preset, template or component, with duration in frames, easing and
  overshoot from the strips. Each caption style → font match, size, position, colours, words per
  caption, hold.
- Shoot notes: framing, lens, light, camera height, b-roll and screen recordings to capture.
- **Clashes.** If the project has brand or style rules (a brand guide, a style file, a CLAUDE.md
  section), read them and list every place this style breaks them (pace, music, colour, type,
  captions) with the options. Adopting a clash is the user's call, never the teardown's.
- Effort per element: cheap (settings), medium (a new template or component), heavy (new footage).

### 12. Check and deliver

Before calling it done:
- Every number in the teardown matches `measures.json`; every "seen" has a timestamp.
- The formula and examples are in new words. Nothing of theirs is copied: no footage, music, logos,
  characters, or script lines as rules.
- The recreate plan names a real tool, preset or component for each element, or says it doesn't exist yet.
- Open questions are listed, not papered over.

Then in chat: the style in one paragraph, the five things that define it, the three biggest gaps
between this style and the user's videos (if you know them), and the paths. Offer (don't do
unasked): building one sample scene in their editor or code, or turning the formula into a script
template.

## Rules

- **Measure before you describe.** If a number exists, use it, not an estimate from the frames. When
  your eyes disagree with a number, run a strip and say which you trust and why.
- **Recreate the style, never the video.** Their structure, rhythm, layout and techniques are fair to
  learn; their footage, music, characters, logos, exact lines and branded look-alikes are not.
- **Fonts**: name the closest match you can see ("bold geometric sans, closest free match
  Montserrat ExtraBold") and say it's a match, not confirmed.
- **The user's rules win for the user's videos.** The teardown reports the style as it is and lists
  the clashes; the user decides what to adopt.
- **No invented proof.** Views, outcomes and "why it works" claims cite the data or are marked as
  inference.
- **Free means free.** Never sign in anywhere, read browser cookies or use a paid service unless the
  user asks for it.

## Known limits (from testing, Nov 2026)

- Cut detection catches hard cuts, jump cuts, punch-ins and fast transitions; dissolves and slow wipes
  need eyes. A `transition` can be in-frame motion (scrolling, a fast pan): confirm with a strip. A
  screen that fills the frame changing page reads as a `new` cut: when the video films a monitor or
  phone, treat the cut count as an upper bound.
- A handheld camera's zooms are reported as `handheld push/pull`, not edit zooms. `snap zoom` means a
  sudden zoom inside a steady shot (an edit keyframe or a Screen Studio style zoom).
- The OCR drops spaces in caption text ("ANDICAN"); word counts come from matching the caption's
  letters to the transcript, so they're right when the captions follow the voice.
- Full-frame OCR reads every UI string in screen recordings: `onscreen_text.txt` leaves the small ones
  out. Scene text (signs, posters) can show up as a `title`: check the crop sheet.
- Faces in profile or very small are missed (YuNet). Shot sizes are approximate.
- SFX are transients in the non-voice stem: drum hits in a music bed can pass for SFX. listen.py calls
  those "part of the music"; `on_beat` marks the suspicious ones it isn't sure about.
- listen.py names what a sound is like, not whether it was added in the edit: in a filmed video, desk
  taps, phone handling and an app's own sounds get effect names with the same scores as real added
  effects. Decide provenance from context (on cuts or text? a mixed studio sound? a music bed?).
- Known-answer test (8 effects planted under a music bed and a voice): all 8 found; ding, glitch, boom
  and counter named right or close; a pop and a click called "part of the music"; a whoosh called
  "punch impact"; one music note passed as an effect. Music notes the detector catches are mostly
  labelled "part of the music". Treat single calls as leads, patterns across calls as findings.
- listen.py's labels are model judgements. AudioSet's genre and mood classes are broad ("Electronic
  music", "Happy music"), CLAP's zero-shot labels are a share across the list you gave it, so a
  confident-looking top label can still be the least-bad option: read the scores.
- Whisper runs without its voice filter by default: with it on, it dropped the last 20 s of speech under
  music. Without it, it can invent an outro ("Thanks for watching!"): measure.py drops those and lists them
  in the warnings. A second voice (an app, a guest) can still be missed: check `matched_to_speech_pct`.
- Reading the boards and strips needs a model that can see images.
