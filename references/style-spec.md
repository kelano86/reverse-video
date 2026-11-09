# style.json

The teardown as data, so a build (a Remotion or After Effects template, an editing script, a script
writer) can read the
settings instead of re-deriving them. Units are in the key names. Every section is listed in
`confidence` by its path, under measured, heard (listen.py), seen or inferred. Leave out what doesn't
apply rather than writing nulls. Times in seconds, frames at `format.fps`, positions as % of the frame
from the top-left, colours as hex.

```json
{
  "name": "creator-build-demo",
  "sources": [{"url": "...", "views": 616969, "duration_s": 139.2}],
  "format": {"aspect": "9:16", "resolution": "1080x1920", "fps": 30, "duration_s": [45, 140]},

  "script": {
    "archetype": "result-first demo",
    "beats": [{"name": "hook", "t_s": [0, 3.9], "purpose": "show the result", "pattern": "I built [thing] with [tool]"}],
    "hook": {"first_word_s": 0.0, "words_first_3s": 8, "visual": "...", "text": "...", "promise": "..."},
    "rehooks_s": [24.5, 58.0],
    "cta": {"type": "comment gate", "at_s": 130, "pattern": "comment [word] and I'll send you [asset]"},
    "language": {"wpm_talking": 236, "words_per_sentence": 10.3, "you_per_100": 3.4, "i_per_100": 6.4, "questions": 4},
    "template": ["Hook: ...", "Setup: ...", "Proof: ...", "CTA: ..."]
  },

  "pacing": {"cuts_per_min": 9.1, "shot_s": {"mean": 6.3, "median": 4.0, "p10": 0.8, "p90": 14.8},
             "first_cut_s": 3.9, "cuts_by_quarter": [1, 6, 8, 5], "cuts_vs_speech": {"word_start_pct": 9.5, "pause_pct": 85.7}},

  "shots": {
    "compositions": [{"name": "desk + screen, phone in front", "share_pct": 80, "framing": "...", "used_for": "..."}],
    "face": {"on_screen_pct": 4.7, "size": "close-up", "centre_x_pct": 67, "eyeline_y_pct": 57},
    "camera": {"type": "handheld phone", "moves": {"handheld push/pull": 58, "locked": 21}}
  },

  "editing": {
    "cut_types_pct": {"new": 48, "jump": 43, "punch": 5, "transition": 5},
    "punch_scale": [1.15],
    "transitions": [{"type": "whip", "frames": 8, "easing": "ease-out", "when": "between items"}],
    "zoom": {"push_rate_pct_s": 0.8, "snap_zooms": 0}
  },

  "motion": {
    "elements": [{
      "name": "title pop", "trigger": "first frame", "position_pct": {"x": 50, "y": 19},
      "in": {"type": "scale pop", "frames": 8, "easing": "spring", "overshoot_pct": 8},
      "hold_s": 3.9, "out": {"type": "cut"}, "stagger_frames": 0
    }]
  },

  "type": {
    "captions": {
      "font_match": "Montserrat ExtraBold (match, not confirmed)", "case": "upper", "cap_height_px_1080w": 56,
      "y_centre_pct": 88.8, "max_width_pct": 80, "words": 3, "hold_s": 0.5, "sync_vs_voice_s": 0.0,
      "fill": "#F9FBFA", "stroke": null, "shadow": "#171B2C soft drop", "highlight": null,
      "build": "replace each chunk", "entrance": "cut on"
    },
    "titles": [{"font_match": "...", "case": "title", "size_pct_of_height": 4.8, "fill": "#FFFFFF", "plate": "#000000 rounded"}]
  },

  "colour": {
    "palette": [{"hex": "#464D56", "role": "ground"}, {"hex": "#AF7238", "role": "warm wood accent"}],
    "grade": {"brightness": 0.32, "black": 0.04, "white": 0.72, "saturation": 0.35, "warmth": 0.0},
    "grounds": ["real room"], "texture": "none", "light_frames_pct": 0
  },

  "sound": {
    "voice": {"lufs_mix": -14.6, "crest_db": 10.3, "tone": "neutral, slightly dark"},
    "music": {"bed": "none", "heard_music_pct": 0, "note": "room rumble 24 dB under the voice"},
    "sfx": {"added_in_edit": "none found", "named_sounds": 9, "on_cuts": 3, "note": "app sounds and handling"},
    "voices": ["male, one speaker"]
  },

  "packaging": {"title_pattern": "...", "cover": "...", "first_frame_is_cover": true},

  "confidence": {
    "measured": ["pacing", "type.captions.words", "sound.voice"],
    "heard": ["sound.music.bed", "sound.sfx"],
    "seen": ["motion.elements[0].in"],
    "inferred": ["type.captions.font_match", "sound.music.mood"]
  }
}
```

The example values are from a test run on a 2:19 filmed build-demo Short; every real style.json
takes its own from `measures.json`, the strips and the boards.
