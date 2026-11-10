# baptisteodonovan: "5 GitHub repos of the week", style teardown

Source: https://www.instagram.com/reel/DdEea0wiU1_/ · Instagram Reel · 9 Sep 2026 · 1:05.5 · 9:16, 1080x1920, 60 fps
Performance: 506,531 views, about 148x the account's usual reel (the creator's own stats, 9 Nov 2026); 18,882 likes and
4,146 comments (measured, from the post)
Analysed: 9 Nov 2026 with the reverse-video skill. This is the creator's own reel, so section 13 checks the teardown
against the project that built it.

## The style in one paragraph

A five-item listicle told in one breath, with a layout change every 1.6 seconds. The speaker sits in a dark room in an
extreme close-up and talks fast (217 wpm). Every item opens on a cream card with the item's number, its name in a
green italic serif, its GitHub stars and its icon. The edit then moves through a strict loop of four layouts: face,
cream title card, a graphic on top with the face in a rounded inset below, and graphic-only cards. Captions are two
words at a time. On the face they're white, in a heavy sans and lower case. On cream cards they switch to black italic
serif capitals, with the key word in green. A quiet music bed runs under everything at a fixed level and there isn't
a single sound effect. The comment-gate CTA is the post's first line and the last shot.

**What defines it**, ranked by how much each changes the feel:
1. **Metronome layout changes**: 39 cuts, median shot 1.63 s, none over 3.2 s (measured). The pace comes from cuts
   between layouts, not from jump cuts in the face.
2. **Dark face vs cream cards**: the picture flips between a dark room (13% of frames dark, 40% light, measured) and
   cream cards. The flip itself is the rhythm (`img/pacing_map.png`, colour and brightness rows).
3. **The item card**: the same cream card opens all five items (seen 0:04.5, 0:16.1, 0:25.5, 0:37.3, 0:49.7).
4. **Two caption voices**: white sans on the face, black italic serif capitals on cards, green serif for the key word (seen).
5. **No sound design**: one music bed, no effects (heard, and confirmed against the project, section 13).

## Hard numbers

| | Measured |
|---|---|
| Length, format | 65.5 s, 9:16, 60 fps file; the camera footage repeats frames (about 25 fps), the graphics run at 60 |
| Cuts | 39 (35.7/min): 32 layout changes, 4 list-step changes, 2 builds, 1 jump |
| Shot length | median 1.63 s, mean 1.64 s, p10 0.38 s, p90 2.55 s, 0% over 4 s |
| Layout share | face 31%, graphic + face inset 30%, graphic cards 24%, item title cards 15% (seen, timed from the shot list) |
| Face | on screen 61% (incl. insets), extreme close-up (face height 88% of the frame width), eyes at 39% from the top |
| Speech | 221 words, 217 wpm while talking, talking 93% of the time, longest pause 0.58 s |
| Hook | first word at 0.0 s, 11 words in the first 3 s, first cut at 2.1 s |
| Captions | 75, 2 words each (max 3), held 0.48 s, centred at 71% of the height, appear 0.14 s before the word |
| Sentences | 10, 22 words each on average, no questions, "you" 7.2 per 100 words, "I" 0.5 |
| Loudness | -14.2 LUFS, LRA 2.0 LU (very even), true peak -0.1 dBFS |
| Music | 98% of the time, 17 dB under the voice, no ducking (1.9 dB change in pauses), ~133 BPM |
| Sound effects | none (heard; 48 candidates, all notes in the music) |
| Palette | cream `#F5F5F2` 40%, near-black `#1B1B18` 25%, room brown `#3C3027` 14%, skin `#96573B` / `#E2A88D` |

## 1. Script and structure

Archetype: **numbered listicle of free tools**, hook plus 5 items plus a comment-gate CTA.

| Time | Beat | What's said (paraphrase) | On screen | Device |
|---|---|---|---|---|
| 0:00.0 | Hook | these five repos blew up this week, all free | title card, 5 icons pop in, face waving in an inset | number + recency + "free" |
| 0:04.5 | Item 1 (11.6 s) | the #1 repo last week; like a famous tool but runs on any model | item card, terminal typing, pixel title | borrowed credibility ("#1 last week") |
| 0:16.1 | Item 2 (9.4 s) | an ad-free YouTube; never sit through an ad again | item card, screenshot, settings page | pain removed |
| 0:25.5 | Item 3 (11.8 s) | built by university researchers; an AI classroom for any topic, for $0 | item card, GitHub card, diagram | authority + $0 |
| 0:37.3 | Item 4 (12.4 s) | 45,000 stars; research steps done for you | item card, a 5-step list stepping down | social proof (stars) |
| 0:49.7 | Item 5 (10.3 s) | "and finally": train your own model in under 2 hours for under 50 cents | item card, diagram, stat cards (2.3h, $0.42) | concrete numbers |
| 1:00.0 | CTA (5.5 s) | comment the keyword for all the links in your inbox | comment box with the keyword, face inset | comment gate |

**Hook anatomy.** 0-3 s: a cream title card names the promise ("5 GitHub repos of the week"), five app icons pop in
one by one in the first 0.4 s, the spoken line builds word by word in the middle of the card ("These 5", "GitHub
repos", "just", then "BLEW UP" in green), and the face waves in an inset below (seen, `img/hook_5s.jpg`). The first cut
lands at 2.1 s, to the full face. 0-15 s: the first item is already halfway through by 15 s. Promise: five free
things, each worth stopping for.

**Retention devices.** The ordinal ("the first", "the second" ... "and finally") is a countdown the viewer can track.
Each item opens with a credibility fact before the benefit. The numbers get more concrete towards the end (45,000
stars, 2 hours, 50 cents). No open loops or questions; the pace and the card flips do the work.

**Language.** 217 wpm while talking, 10 long sentences (22 words), "you" 14x more than "I", no questions, plain words.
Every item follows the same pattern: name, credibility, "it's basically [familiar thing]", what you get.

**CTA.** Comment gate twice: the post's first line ("Comment [keyword] below...") and the last 5.5 s, with a mock
comment box showing the keyword (seen 1:02.4).

**The formula** (in new words, never their lines):
1. Hook: "These [N] [things] just [took off] this [week], and every one of them is [free]."
2. Each item: "The [first] is [Name], [one credibility fact]. It's basically [thing you know], but [twist], so you
   [concrete benefit]." 9-12 seconds each.
3. Last item: "And finally, [Name], which lets you [most ambitious outcome] in [time] for [cost]."
4. CTA: "If you want all the links, comment [WORD] and I'll send them to you."

## 2. Pacing

35.7 cuts/min and very even: shot length p10 0.38 s, p90 2.55 s, and the quarters run 1.98 / 1.47 / 1.30 / 1.98 s
(measured). The middle speeds up slightly (items 3 and 4 carry the most graphics), and the first and last quarters
breathe a little more. The speech is the steady line under it (`img/pacing_map.png`): 238-247 wpm in the hook,
165-201 in the middle items, back up to 229 at the CTA. Cuts sit on word starts 54% of the time and in a pause 28%
(measured). A new visual idea arrives every 1.6 s. No dead air: the longest pause is 0.58 s.

## 3. Shots, framing and layouts

| Composition | Share of time | Used for | Example |
|---|---|---|---|
| Face, full bleed, dark room | 31% (12 shots) | the spoken claim, the benefit | 0:02.1 |
| Graphic on top, face in a rounded inset below | 30% (10 shots) | showing the tool while talking about it | 0:07.9 |
| Graphic only, on cream or dark | 24% (12 shots) | screenshots, diagrams, the step list, stat cards | 0:43.0 |
| Item title card on cream | 15% (6 shots) | opening every item | 0:04.5 |

Face and camera: one camera, locked, eye-level, dark room with a warm practical lamp at frame right. The full-bleed
face is a tight crop (face height 88% of the frame width, measured); the inset is a wider framing of the same camera
showing the room and the lamp (seen 0:07.9). The "handheld" and "push/pull" camera readings are the speaker's head
and hands moving in a very tight crop, not camera moves (seen in the strips). Background: plain dark wall, a
microphone at the bottom edge.

## 4. Editing

- **Cut types** (measured, then checked on the boards): 32 hard cuts between layouts. The 4 "punch-ins" at 0:43.0-0:44.2
  are a stepped list moving its highlight down one row at a time (seen, `img/shots_01.jpg` #25-29). The 2 "transitions"
  are cards building in. 1 jump cut in the face.
- **No transitions**: everything is a hard cut; the motion lives inside the shots.
- **Zooms**: none added in the edit; the full-bleed face is a static crop.
- **B-roll**: screenshots of each tool (a video player, a settings page, a GitHub card, a diagram), presented as cards.
- **Signature**: the item card opens all five items; the cream/dark flip repeats every 1-3 s.

## 5. Motion graphics and animation

| Element | Trigger | Entrance | Frames @60 | Easing | Hold | Exit | Evidence |
|---|---|---|---|---|---|---|---|
| Item card | new item | hard cut to cream, then elements fade in one after another: number and caption, name, icon, stars | name ~7, icon ~8, starts 3-5 apart | ease-out fade, no movement | 1.4-2.6 s | hard cut | `img/strip_0004.45s.jpg` |
| Two-word caption | each chunk | fade with a slight scale-up | 3 (fade) | ease-out | 0.48 s | replaced | `img/strip_0002.08s.jpg` |
| Terminal window | split layout | fade in, then the command types out | 3 + ~5 per letter | linear typing | ~1.3 s | hard cut | `img/strip_0007.85s.jpg` |
| Hook icon row | first frame | icons pop in left to right | ~5 apart | pop | 2 s | hard cut | `img/hook_5s.jpg` |
| Step list | "research steps" | highlight bar steps down one row per beat | instant per step | none | 0.38 s per step | hard cut | `img/shots_01.jpg` #25-29 |
| Stat cards | numbers said | cards build on cream | not stripped | | 2.6 s | hard cut | `img/shots_01.jpg` #37 |

Overall: fast fades and staggered builds, never slides or bounces. Movement is small, so the cuts carry the energy.

## 6. Typography and captions

**Captions** (measured unless marked): 2 words each (max 3, single words 11%), held 0.48 s, one line, centred at 71%
of the height, about 46% of the frame wide, appearing 0.14 s before the word (91% early). Letters about 62 px tall at
1080 wide.
- On the face (seen): white `#F3F5EF`, heavy sans (closest free match: Inter ExtraBold or Segoe UI Black, a match, not
  confirmed), sentence case, soft dark shadow, no plate.
- On cream cards (seen): near-black `#131C15`, bold italic serif in capitals (closest free match: Cambria Bold Italic
  or Playfair Display Italic).
- Key words, on cards and on the face (seen 0:19.0, 0:40.0): the same serif capitals in green (`#4E7661` in the pixel
  read, softened by anti-aliasing; a saturated green by eye).
- Measured 51% all caps: the two styles split the captions about evenly.

**Other type** (seen): item names in green italic serif, large, centred near the top; "#1" small bold black above;
star counts small with a yellow star; the hook title in black italic serif. Two type families in total.

## 7. Colour and look

Palette with roles (measured, `img/palette.jpg`): cream `#F5F5F2` ground for cards (40%), near-black `#1B1B18` room
and terminal (25%), room brown `#3C3027` (14%), skin `#96573B` / `#E2A88D`, warm grey `#6A625D`. One accent: green for
names and key words (seen). Grade: blacks slightly lifted (0.083), whites near full (0.962), low saturation (0.22),
a touch warm (+0.04): an ungraded webcam-style room against clean cards. No grain, vignette or glow visible.

## 8. Sound

Voice: -14.2 LUFS with only 2.0 LU of range, so it's heavily levelled; tone is full (low +5.4 dB, presence +5.7 dB,
air +6.4 dB against 1 kHz) and close-miked (measured). Music: a bed under 98% of the video (heard), 17 dB under the
voice, at a fixed level with no ducking (measured). CLAP calls it phonk (0.51), mood inspiring or playful (0.37 / 0.33);
AudioSet is too unsure of the genre to quote (heard). About 133 BPM (low confidence), and cuts ignore the beat (15% on
the beat vs 22% by chance, measured). **Sound effects: none.** measure.py found 48 short peaks; listen.py judged all
of them to sound like the music around them (similarity 0.70 or more), and the project confirms there were none
(section 13).

## 9. Packaging

On Instagram the post's first line is the comment gate, followed by the full script as text. The first frame is the
title card, so it works as the cover: the promise in words, five recognisable icons, a face. Length 65 s, long for a
listicle Reel but every second is spoken.

## 10. Why it works

Load-bearing: the hook's three promises in one line (a number, "this week", "free"); the item card, which tells the
viewer where they are in the countdown; a layout change every 1.6 s with nothing on screen longer than 3.2 s; and the
comment gate, which turns interest into comments (4,146 on 18,882 likes, about 1 in 5, measured). Taste: the cream and
green palette, the serif, the dark room. The outlier result (148x the account's usual) came with this exact format,
but one video can't separate the format from the topic (inferred).

## 11. Recreate it

| Element | Build with | Settings from this teardown | Effort |
|---|---|---|---|
| Script | the formula above | 5 items, 9-12 s each, 210-220 wpm | cheap |
| Item card | any template (After Effects, Remotion, CapCut) | cream `#F5F5F2`, name in green italic serif, number, stars, icon; staggered fades of 7-8 frames at 60 fps, 3-5 frames apart | medium |
| Split layout | picture-in-picture | graphic top, rounded face inset below from a wider framing of the same camera | cheap |
| Captions | auto captions plus a second style | 2 words, 0.48 s, y 71%, white heavy sans on the face, black italic serif caps on cards, key word green, 3-frame fade | medium |
| Terminal typing | a typing animation | ~5 frames per letter at 60 fps | cheap |
| Music | any royalty-free phonk or lo-fi bed | 17 dB under the voice, no ducking | cheap |
| Voice | compressor + limiter | -14 LUFS, about 2 LU range | cheap |

**Shoot notes**: one locked camera at eye level in a dark room, one warm practical lamp in the background, a close
mic. Frame wide enough to crop both a tight full-bleed face and a wider inset from the same shot.
**Clashes**: none to list here; check against your own brand rules before adopting the cream and green look.
**Suggested first test**: a 3-item version with only the item card, the split layout and the two caption styles.

## 12. Confidence and open questions

Measured: cuts, shot lengths, speech, captions, palette, grade, loudness, music level, tempo.
Heard: music presence, style and mood, no effects, voice.
Seen: layouts, caption fonts, motion (strips), the step list.
Inferred: why it works, font matches.
Couldn't measure: views (Instagram doesn't expose them to yt-dlp; the figure above is from the creator's stats).
Whisper misheard the repo names (they're names it doesn't know); the teardown uses the names on screen.

## 13. Checked against the project that built it

This is the creator's own reel, and the Remotion project that rendered it was still on disk, so the teardown could be
checked against the truth. (The project was re-cut later for a different version; its shared settings, captions,
cards and music, are the ones this reel used, but this reel's own shot list wasn't kept, so the cut count is checked
against the project's structure rather than a list.)

| What | Teardown | Project | |
|---|---|---|---|
| Frame rate | 60 fps file, camera footage repeating frames | rendered at 60 fps from 25 fps camera footage | match |
| Music | one bed, 98% of the time, no ducking | one music file at a fixed volume (0.17) the whole way | match |
| Sound effects | none | none | match, after a fix |
| Caption styles | white heavy sans, black italic serif caps, key word green | system sans at weight 800, Cambria Bold Italic caps, emphasis in `#1F9E6C` green | match |
| Caption entrance | 3-frame fade, slight scale-up | fade over 3 frames, scale 93% to 100% over 5 frames | match |
| Grounds | cream and near-black | `#F4F5F1` / `#F9F9F9` cream, `#050706` black | match |
| Cut count | 39, nearly all layout changes | each item plays one continuous take, so cuts come from layout changes, not jump cuts in the face | consistent, after a fix |

Two things were wrong on the first run, and both were fixed in the skill before this example was written:
- **Cuts**: the first run counted 97 (88.8/min). The camera footage was recorded at 25 fps and rendered at 60, so most
  frames repeat, and ordinary head and hand movement looked like cuts against the near-zero median
  (`img/strip_0036.05s.jpg` shows one of those stretches: one continuous take, read as seven cuts). measure.py now
  spots repeated frames and judges each new frame against the other new frames.
- **Sound effects**: listen.py first named 8 effects "with confidence" (coin sounds, chimes, a pop). Lined up against
  the real music file, every one was a note in the music. listen.py now compares each candidate with the music just
  around it; on this reel that leaves 0 effects, and on a copy with 8 planted effects it finds 5 of them with no
  false ones.
