# What to look for, dimension by dimension

Go through every section for every teardown. Where `measures.json` has the number, use it; this list
is for naming what you see and asking the questions the numbers raise. Rough norms are there to say
whether a value is unusual, not as targets.

## 1. Script and structure

- **Archetype**: listicle, tutorial / how-to, story, before/after, result-first demo ("I built this"),
  myth-bust, news explainer, reaction, challenge, comparison, POV/opinion. Hybrids are common: name both.
- **Hook (0-3 s)**: what's on screen at frame 1 (the cover for a Reel), the first spoken line, the
  first text, the first cut. Types: result first / proof, bold claim, question, negative ("stop doing"),
  curiosity gap, pattern interrupt (odd visual or sound), in-media-res story, relatable pain, number.
  Words in the first 3 s (measured) and whether the first word is at 0.0 s.
- **Primer / setup (3-15 s)**: what context, what promise ("by the end you'll..."), stakes.
- **Body**: the beat unit (one item, one step, one scene) and its length; what each beat opens with
  (ordinal card, question, cut to a new layout); how proof is shown (screen, result, number, face).
- **Re-hooks**: lines or visuals that renew curiosity ("but here's the thing", "and that's not even
  the crazy part"), how often (every 15-25% of runtime is common), and whether they line up with
  replay peaks or retention dips.
- **Open loops**: what's promised early and paid off late; the payoff's timestamp.
- **Payoff and ending**: does it end on the payoff, a twist, a loop back to the opening (rewatch bait)
  or a CTA? How many seconds after the last real information?
- **CTA**: comment gate ("comment X"), follow, link in bio, save/share, subscribe, next video. Where it
  sits and whether it's earned (a real asset behind it).
- **Language**: wpm (150 relaxed, 180-200 brisk, 220+ very fast), sentence length, you vs I, questions,
  numbers and specifics, jargon level, swear words, catchphrases, direct address to camera vs voiceover.
- **Delivery**: energy, emphasis words, pauses kept or cut (`pauses_over_07`), retakes visible, ad-libs.

## 2. Pacing

- Cuts per minute (short form: 10-20 calm, 20-40 fast, 40+ frantic; long form 5-15) and how it moves
  through the video (`by_quarter`, the pacing map). Fast open then slower is common; check.
- Shot length spread: a steady metronome (low spread) or punches (sub-second shots between long ones).
- Where cuts fall against speech: on word starts, mid-word, in pauses (measured).
- Information rate: a new visual idea every how many seconds (count distinct things you learn per 10 s).
- Dead air: any stretch over 1 s with no speech, no motion and no text.
- Speed ramps or a sped-up voice (wpm far above natural, pitch sounding up).

## 3. Shots, framing, layouts

- **Taxonomy**: name each composition and its share of time. Common ones: full-bleed face, face over
  moving background, split (screen/board top, face bottom), screen or b-roll only, picture-in-picture,
  green screen, title card, document/tweet card, product shot, over-the-shoulder, hands/desk top-down.
- **Face**: on-screen share, size (`face_height_of_short_side`: ~0.3 is a close-up), position, eyeline
  height, headroom, looking at the lens or off, number of people.
- **Camera**: phone selfie (wide, close, distorted) vs camera on tripod (longer lens, background blur);
  camera height; locked vs handheld (measured).
- **Background**: real room (what's in it, practical lights, depth), plain wall, virtual/moving
  background, ground colour per shot (some creators change it every shot).
- **Safe zones** for vertical: IG and TikTok UI covers roughly the bottom 20% and right 15%; where do
  captions and faces sit against that?

## 4. Editing

- **Cut types** (measured): new shot, jump cut (same framing), punch-in/out (same shot reframed; scale
  typical 1.1-1.3), multi-frame transitions.
- **Transitions inventory**: hard cut, whip pan, zoom-through, push/slide, mask wipe, shape wipe,
  morph, flash frame, glitch, dip to black/white, light leak, match cut, J/L cuts (sound leads or trails
  the picture). Duration in frames from a strip.
- **Zoom language**: punch-ins on emphasis, slow push-ins (rate %/s), Screen Studio style zooms on
  screen recordings (smooth, eased, follow the cursor), zoom snaps on beats.
- **B-roll**: share of time, sourced vs shot vs generated, how it's cut in (on the noun being said?).
- **Pattern interrupts**: anything that breaks the visual rhythm on purpose (a shot type used once, a
  freeze, a colour flip, a sound drop) and how often.
- **Speed**: speed ramps, time-lapses, sped-up voice.
- **Repetition**: the same transition or layout reused as a signature.

## 5. Motion graphics and animation

For each element: what it is, when it's used (trigger: a word, a beat, a new item), where in frame,
**entrance** (scale pop, slide in, mask reveal, type-on, blur-in, fade, 3D flip, draw-on, bounce),
**duration** in frames, **easing** (ease-out / spring with overshoot / linear / ease-in-out), overshoot
amount, **stagger** between parts, **hold**, **exit** (or a hard cut away), and depth (shadows,
parallax, 3D). Use strips; the printed shape helps, the frames decide.

Common elements: titles and kinetic type, captions, highlight boxes, circles, arrows, underlines,
emoji or sticker pops, logos and app icons, tweet/article cards, charts and counters, progress bars,
lower thirds, screen recording frames (device mockups, rounded corners, shadows), cursor highlights,
annotations drawn on screen, map or diagram builds, transitions as graphics, background loops.

Norms at 30 fps: UI pops 6-10 frames, slides 8-15, big transitions 8-14, settles with overshoot
10-18. Faster than that reads as snappy, slower as cinematic.

## 6. Typography and captions

- **Captions** (measured: words per caption, hold, position, height, case, sync, colours, word-by-word
  build): font match, weight, tracking, stroke vs shadow vs plate (box behind), highlight logic (which
  word, what colour, scale bump), entrance per caption or per word, emoji, line breaks, safe zone.
- **Other type**: titles, labels, numbers, lower thirds: font, weight, case, size relative to captions,
  colour, alignment, how many type styles in total (fewer is more premium).
- **Font naming**: describe the class (geometric/grotesk/humanist sans, slab, serif, display, mono,
  handwritten), then the closest free match, marked as a match.

## 7. Colour and look

- **Palette** (measured) with roles: ground, ink, accent(s), skin.
- **Grade**: black level (crushed under ~0.03, lifted over ~0.08), highlight roll-off, contrast,
  saturation, warm/cool, skin tone rendering, teal-orange or film looks, LUT feel.
- **Light vs dark** share (measured), and whether the ground changes per shot.
- **Texture**: grain, halation, vignette, blur, paper/noise overlays, glow, chromatic aberration.
- **Lighting**: key direction and softness, practicals in frame, rim light, colour of the background
  light.

## 8. Sound

- **Voice**: mic sound (close/boomy vs thin), processing (crest factor: compression), room, de-essing,
  level against everything else, loudness (`lufs`: -14 is YouTube's reference; Reels often louder).
- **Music**: bed or not (measured coverage), level under voice (-18 to -30 dB typical), ducking in
  pauses, tempo, cuts on the beat or not, where it changes, drops out or hits; genre and mood (inferred).
- **SFX**: count and rate (measured), kinds (hit, whoosh/riser, click, pop, boom), what they mark
  (cuts, text arrivals, transitions, zooms, reveals), level vs voice, how unevenly they're spread.
- **Silence**: deliberate gaps, music drops before a key line.
- **Foley / diegetic**: keyboard, mouse clicks, room sound kept in.

## 9. Packaging

- Title or caption: pattern, length, keyword placement, curiosity vs clarity.
- Cover / thumbnail (`cover.jpg`): composition, text words, face and expression, contrast, what it
  promises; for Reels, is the first frame the cover?
- Description: links, hashtags, the comment-gate keyword.
- Length against the format and against the creator's other videos.

## 10. Why it works

Separate the load-bearing choices (cut them and attention drops: hook, proof timing, pace, captions
that carry the story) from taste (their colours, their font). Evidence: replay heatmap peaks, views
against the creator's usual (their recent uploads tell you their normal), comparison with the
creator's weaker videos (compare.py), and how the choice serves the viewer's next three seconds.
