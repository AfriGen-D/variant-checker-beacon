# Slide format spec — `Beacon_intro_10min.pptx`

Reference for editing the deck or producing variants of it (longer talk,
different audience, etc.). Mirrors what `build/build_deck.py` outputs.

## Geometry

| | |
|---|---|
| Aspect ratio | 16:9 |
| Slide size | 13.333 × 7.5 in (PowerPoint widescreen default) |
| Render DPI for embedded images | 200 |
| Image native resolution | 2667 × 1500 px |

## Colour palette

| Role | Hex | Used on |
|---|---|---|
| `NAVY` | `#0B2E4F` | Title-slide background, body titles |
| `ACCENT` | `#C84B31` | Title-slide horizontal stripe, side accent bar on text slides |
| `GREY` | `#555555` | Body copy, footers |
| `LIGHT` | `#F4F1EC` | Text-slide background (warm off-white) |
| `WHITE` | `#FFFFFF` | Title-slide headline |
| `MUTED-BLUE` | `#C8D8E8` | Title-slide subtitle / metadata |

## Typography ladder

| Element | Size | Weight | Colour |
|---|---|---|---|
| Title-slide headline | 60 pt | bold | white |
| Title-slide subtitle | 28 pt | regular | muted-blue |
| Title-slide meta | 16 pt | italic | muted-blue |
| Body-slide title | 40 pt | bold | navy |
| Body-slide bullet | 22 pt | regular | grey |
| Body-slide footer | 12 pt | italic | grey |

PowerPoint default font (Calibri) is used throughout — no font dependencies.
If you swap fonts, prefer something with a strong geometric weight at 60 pt
and a humanist body at 22 pt.

## Slide types

### Type A — title slide (slide 1 only)

```
┌────────────────────────────────────────────────┐
│  NAVY background                               │
│                                                │
│  GA4GH Beacon                  ← 60 pt white   │
│  ────────────────              ← 0.08 in accent│
│                                                │
│  Federated genomic data        ← 28 pt muted   │
│  discovery — a 10-minute…                      │
│                                                │
│                                                │
│                                                │
│  AfriGen-D · Honours student   ← 16 pt italic  │
│  onboarding                       muted-blue   │
└────────────────────────────────────────────────┘
```

### Type B — full-bleed image slide (slides 2–8)

```
┌────────────────────────────────────────────────┐
│                                                │
│         [PNG fills entire slide,               │
│          0,0 to 13.333×7.5]                    │
│                                                │
└────────────────────────────────────────────────┘
```

Source PNGs live in `build/extracted_p<n>-<n>.png` — 200 dpi, no padding.
To replace: drop in a new PNG of the same dimensions or let PowerPoint
rescale.

### Type C — authored text slide (slides 9, 10)

```
┌────────────────────────────────────────────────┐
│  LIGHT background                              │
│                                                │
│  ┃ Slide title                  ← 40 pt navy   │
│  ┃ ← 0.18 in accent stripe                     │
│                                                │
│  • Body bullet one              ← 22 pt grey   │
│  • Body bullet two                              │
│  • Body bullet three                            │
│  • Body bullet four                             │
│                                                │
│                                                │
│  Footer note                    ← 12 pt italic │
└────────────────────────────────────────────────┘
```

Body bullets: max ~6 lines, max ~120 chars each. Beyond that the slide
becomes unreadable from the back of the room.

## Speaker notes

Every slide carries notes (`slide.notes_slide.notes_text_frame`). The notes
are the short version — `Beacon_intro_10min_script.md` is the long version.
PowerPoint shows notes in Presenter View; Keynote does the same. Don't
delete them — they're the only thing keeping the deck self-explanatory if
someone else picks it up.

## Editing workflow

| Task | Action |
|---|---|
| Change title text | Click the text box on slide 1, retype |
| Replace an extracted slide | Right-click the image, "Change Picture", point to new PNG |
| Re-extract from a different source page | Edit `SOURCES` in `build/survey_titles.py`; rerun `python3 build/build_deck.py` |
| Add a slide | Easier in PowerPoint/Keynote directly than via python-pptx |
| Bulk regenerate | `python3 build/build_deck.py` (overwrites the .pptx) |

## Reproducing the build from scratch

```bash
cd ~/projects-uct/_beacon-afrigend/afrigen-beacon-v2/docs/lectures
# 1. Convert source .pptx to PDF (one-off, requires Keynote)
osascript /tmp/keynote_export.applescript \
  "$PWD/Afrigen-D_AGM2025_reference_panel_imputation_beacon.pptx" \
  "$PWD/build/AGM2025_full.pdf"

# 2. Extract pages as PNG
cd build
for p in 38 39 40 41 43 44 46; do
  pdftoppm -png -r 200 -f $p -l $p AGM2025_full.pdf "extracted_p${p}"
done

# 3. Build the deck
python3 build_deck.py
```

Output: `Beacon_intro_10min.pptx` (≈2.3 MB, 10 slides).

## Variants you might want to author

- **20-minute version**: keep all 10 existing slides; add (a) one historical
  context slide before slide 3 (David Haussler / 2014 origin), (b) one slide
  summarising attack-defense literature after slide 6, (c) one slide showing
  the Beacon network aggregator front-end after slide 8, (d) one Q&A prompt
  slide before slide 10. Total: 14 slides.
- **5-minute teaser**: drop slides 4, 6, 8, 9. Keep title, "what is Beacon",
  v1, v2, demo, next steps. Total: 6 slides.
- **Postgrad / research-talk version**: replace slide 9 with a 3-line summary
  of one chosen project's research question + threat model + measurement plan.
  Total: 10 slides, different focus.
