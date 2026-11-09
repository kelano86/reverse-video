# reverse-video

A Claude Code skill that takes any video apart and tells you exactly how it's made: the script, the
hook, the pacing, every cut, the camera moves, the captions, the animation timing, the colour, the
music and the sound effects. Then it writes you a plan to make videos that work the same way.

Give it a link:

```
reverse https://www.youtube.com/shorts/<id>
```

It measures what numbers can settle, looks at the frames for the rest, and listens to the audio with
two open models. **It's free: everything runs on your computer, no accounts, no API keys.**

## What you get

```
teardowns/<creator-topic>/
  teardown.md   the style bible: 12 sections, every claim tagged measured / heard / seen / inferred
  style.json    the same as data, for a template, an editing script or another agent to read
  img/          pacing map, one frame per shot, the first 5 seconds frame by frame, palette, text crops,
                frame-by-frame strips of each animation
  work/         the video, transcript and raw measurements (keep this private: it's someone else's video)
```

What it measures, so the teardown argues from numbers rather than impressions:

| Part | How |
|---|---|
| Every cut, and what kind (jump cut, punch-in, new shot, transition) | frame differences + image alignment (OpenCV) |
| Shot lengths, cuts per minute, how the pace changes through the video | from the cuts |
| Camera moves: push-ins, snap zooms, handheld or locked | image alignment between frames |
| Face size, position, eyeline, time on screen | YuNet face detector |
| Words per minute, pauses, hook words in the first 3 s, where cuts land against speech | Whisper (faster-whisper), word timestamps |
| On-screen text and titles; captions frame-accurate: words per caption, hold, position, colours | RapidOCR |
| Palette, grade, light vs dark | k-means in Lab colour |
| Voice loudness and tone, music bed level, tempo, sound-effect timing | ffmpeg EBU R128, Demucs voice/music split |
| What each sound effect is, music genre, mood and instruments, kinds of voice | AST (AudioSet's 527 sounds) + CLAP (plain-English labels) |
| Animation easing and duration in frames | every-frame strips with a motion curve |
| Title, views, likes, chapters, YouTube's most-replayed curve | yt-dlp metadata |

Give it 3 to 5 videos from one creator and it separates their **style** (what stays the same) from
each video's **content** (what changes).

## Install

You need [Claude Code](https://claude.com/claude-code) (or another agent that reads `SKILL.md`
skills and can look at images). The setup is four steps, about 10 minutes, then about 3 GB of models
download on the first run.

**1. Install the programs it uses** (skip any you already have). Paste into Terminal (Mac) or
PowerShell (Windows):

Mac (needs [Homebrew](https://brew.sh)):
```bash
brew install git uv ffmpeg node
```

Windows, one line at a time:
```powershell
winget install Git.Git
winget install astral-sh.uv
winget install Gyan.FFmpeg
winget install OpenJS.NodeJS.LTS
```

Close the terminal and open a new one so it finds them.

**2. Get the skill** into Claude Code's skills folder.

Mac:
```bash
git clone https://github.com/kelano86/reverse-video ~/.claude/skills/reverse-video
cd ~/.claude/skills/reverse-video
```

Windows (PowerShell):
```powershell
git clone https://github.com/kelano86/reverse-video "$HOME\.claude\skills\reverse-video"
cd "$HOME\.claude\skills\reverse-video"
```

**3. Install its Python packages** (same on both; uv fetches the right Python by itself):
```bash
uv venv --python 3.12 .venv
uv pip install -r scripts/requirements.txt --torch-backend cpu
uv pip install --no-deps rapidocr_onnxruntime
```

**4. Check it.** Mac: `.venv/bin/python -I scripts/doctor.py`, Windows:
`.venv\Scripts\python.exe -I scripts\doctor.py`. It lists anything missing with the command that
fixes it. Add `--fetch-models` to download the models now instead of on the first video.

## Use it

Open Claude Code in the folder you want the teardowns in, and ask:

- `reverse <link>`: one video.
- `reverse <link> <link> <link>`: one creator's style across several videos.
- "How is this edited?", "Tear down this reel", "I want my videos to feel like this: <link>".

A 2-minute Short takes about 5 minutes on a recent desktop (longer on a laptop, longer the first
time while models download). Long videos work too; run them while you do something else.

Instagram sometimes refuses downloads without a signed-in session. Claude will ask before using your
browser's cookies (yt-dlp reads them locally), or you can download the video yourself and give it
the file path. Local files always work: `reverse ~/Downloads/video.mp4`.

## What it can't do (yet)

- Dissolves and slow wipes aren't detected as cuts; Claude checks those by eye.
- When the video films a screen, the screen changing page counts as a cut, so cut counts are an upper bound.
- The audio models say what a sound is like, not whether it was added in the edit or happened in the
  room. Every call comes with its score, and the teardown says how sure it is.
- Fonts are matched by eye ("closest free match"), never confirmed.

## Use it fairly

Study the style, then make your own: structure, rhythm, layouts and techniques are fair to learn;
someone's footage, music, characters, logos and lines are not. The teardown writes the formula in
new words, and `work/` (their video and transcript) stays on your computer.

## Credits and licences

This repo is MIT licensed. It downloads and runs these open tools and models; none are included here:

| Tool / model | Licence |
|---|---|
| [yt-dlp](https://github.com/yt-dlp/yt-dlp) | Unlicense |
| [FFmpeg](https://ffmpeg.org) | LGPL / GPL |
| [faster-whisper](https://github.com/SYSTRAN/faster-whisper) and the Whisper medium weights | MIT |
| [RapidOCR](https://github.com/RapidAI/RapidOCR) (PaddleOCR models) | Apache 2.0 |
| [OpenCV](https://opencv.org) and the [YuNet](https://github.com/opencv/opencv_zoo/tree/main/models/face_detection_yunet) face model | Apache 2.0 / MIT |
| [AST, MIT/ast-finetuned-audioset-10-10-0.4593](https://huggingface.co/MIT/ast-finetuned-audioset-10-10-0.4593) | BSD 3-Clause |
| [CLAP, laion/larger_clap_general](https://huggingface.co/laion/larger_clap_general) | Apache 2.0 |
| [Demucs](https://github.com/adefossez/demucs) code | MIT |
| Demucs htdemucs weights | unclear, per its author (trained partly on research-only music data); used here only to measure, locally |
| PyTorch, Transformers, NumPy, SciPy, Pillow | BSD / Apache 2.0 / HPND |
