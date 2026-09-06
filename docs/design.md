# Design Spec - Competitive Programming Contest Site

A design system for a competitive-programming contest website (leaderboard, announcements,
general information, rules). The visual language is adapted from the **"Paper Portfolio"**
newspaper/editorial aesthetic: warm paper background, near-black ink, a single warm-tan accent,
big high-contrast serif headlines, and small monospaced labels - like a modern broadsheet
newspaper. Monospace is leaned into for anything numeric (ranks, scores, penalties, timers),
which suits a leaderboard well.

> **Do NOT** replicate the "rotate your device" prompt, heavy WebGL/Three.js scenes, or any
> 3D/rotation effects from the source. Keep motion subtle and functional (see §7).

---

## 1. Design Philosophy / Vibe

- **Editorial & print-inspired.** Think broadsheet newspaper: a masthead, hairline column
  rules, datelines, kicker labels, generous margins, and confident typography.
- **Two-tone and disciplined.** Ink on paper, with one warm accent. Color is used sparingly
  and intentionally - hierarchy comes from *type, scale, weight, and rules*, not from many colors.
- **Type-led.** Oversized serif headlines do the heavy lifting. Body text is a clean grotesque
  sans. Small metadata is uppercase monospace with wide tracking.
- **Structured, calm, high-contrast.** Lots of whitespace, crisp 1px rules, strong alignment
  to a grid.

---

## 2. Color Palette

Strictly two "inks" over paper, plus a small set of *optional* muted functional colors for the
leaderboard (use only if needed - prefer weight/rules/fills for emphasis first).

```css
:root {
  /* Core (from source aesthetic) */
  --paper:        #F3F0E9; /* warm off-white / newsprint background (approx.) */
  --paper-panel:  #EAE6DC; /* slightly deeper cream for cards, table stripes */
  --paper-sunk:   #E2DDD0; /* recessed / hover surface */

  --ink:          #0A0A0A; /* primary text, near-black */
  --ink-soft:     #2B2A27; /* secondary text */
  --ink-muted:    #6B675E; /* captions, metadata, disabled */

  --accent:       #987654; /* warm tan - the one accent color (confirmed) */
  --accent-deep:  #6F5638; /* darker tan for hover/active on accent */

  /* Lines & rules (newspaper hairlines) */
  --line:         rgba(10,10,10,0.16);
  --line-strong:  rgba(10,10,10,0.42);

  /* OPTIONAL functional colors - keep muted, use sparingly */
  --ok:           #3C7A4E; /* accepted / solved */
  --warn:         #B07B2C; /* pending / partial */
  --bad:          #A6483C; /* wrong answer / failed */
}
```

**Rules of thumb**
- Background is always `--paper`. Cards/table stripes use `--paper-panel`.
- Text is `--ink`; drop to `--ink-soft`/`--ink-muted` for supporting text.
- `--accent` (tan) is for: active nav, links on hover, kicker labels, the #1 rank marker,
  small decorative marks/stamps, and section numbers. Don't flood the page with it.
- Prefer a **dark mode as inversion** only if you want it: swap to `--paper: #141310`,
  `--ink: #F3F0E9`, keep `--accent` the same. Optional - the source is light-only.

---

## 3. Typography

The source pairs a **high-contrast editorial serif** for display with a **neo-grotesque sans**
for text, plus **monospace** for tiny labels. Below are the "ideal" (paid) fonts and
**free, drop-in alternatives** - use the free stack unless the paid licenses are available.

| Role | Ideal (source-like) | Free alternative (recommended) | Fallback |
|---|---|---|---|
| Display serif (headlines) | PP Editorial New | **Fraunces** (Google) or **Playfair Display** | Georgia, serif |
| Body / UI sans | Neue Montreal / grotesque | **Inter** or **Space Grotesk** (Google) | system-ui, Arial |
| Mono (labels, ranks, scores) | - | **JetBrains Mono** or **Space Mono** (Google) | ui-monospace, monospace |

> **Recommendation:** `Fraunces` (headlines) + `Inter` (body) + `JetBrains Mono` (numbers/labels).
> Fraunces is variable with a high-contrast "opsz" that reads editorial and newspaper-y.

```css
:root {
  --font-display: "Fraunces", Georgia, "Times New Roman", serif;
  --font-body:    "Inter", system-ui, -apple-system, Arial, sans-serif;
  --font-mono:    "JetBrains Mono", ui-monospace, "SFMono-Regular", monospace;
}
```

### Type scale (fluid)

```css
--fs-display: clamp(3.25rem, 9vw, 8rem);   /* hero masthead / page title */
--fs-h1:      clamp(2.5rem, 6vw, 5rem);
--fs-h2:      clamp(1.9rem, 4vw, 3.25rem);
--fs-h3:      clamp(1.4rem, 2.5vw, 2rem);
--fs-lead:    clamp(1.1rem, 1.6vw, 1.375rem); /* intro paragraphs */
--fs-body:    1.0625rem;                        /* 17px */
--fs-small:   0.875rem;
--fs-label:   0.72rem;                          /* uppercase mono labels */
```

### Usage conventions
- **Display / headlines** → `--font-display`, weight 400–600, `line-height: 0.98`,
  `letter-spacing: -0.01em`. Big, tight, confident. Use for the site title, page titles,
  and announcement headlines.
- **Body** → `--font-body`, weight 400, `line-height: 1.55`, `max-width: ~68ch` for reading.
- **Kickers / metadata / tags** (e.g. `LIVE`, `ROUND 2`, timestamps, `NEW`) →
  `--font-mono`, `text-transform: uppercase`, `font-size: var(--fs-label)`,
  `letter-spacing: 0.12em`, color `--ink-muted` or `--accent`.
- **All numeric data** (rank, score, penalty, time, problem counts) → `--font-mono` with
  `font-variant-numeric: tabular-nums` so columns align perfectly.

---

## 4. Layout & Spacing

Newspaper structure: a wide container with strong margins, hairline rules dividing sections,
and column-based content.

```css
:root {
  --maxw: 1280px;        /* content container */
  --gutter: clamp(1.25rem, 4vw, 4rem); /* page side padding */
  --space-1: 0.5rem;  --space-2: 1rem;  --space-3: 1.5rem;
  --space-4: 2rem;    --space-6: 3rem;  --space-8: 5rem;  --space-12: 8rem;
  --radius: 2px;         /* corners are nearly square - print feel */
  --border: 1px solid var(--line);
}
```

- **Container:** centered, `max-width: var(--maxw)`, `padding-inline: var(--gutter)`.
- **Section rhythm:** separate major sections with a full-width **hairline rule**
  (`border-top: 1px solid var(--line-strong)`) and `--space-8`+ vertical padding.
- **Grid:** a 12-column grid for desktop; collapse to 1 column on mobile. Announcements and
  info can use a 2–3 "newspaper column" layout on wide screens.
- **Corners:** keep them sharp (`--radius: 2px` max). This is print, not a rounded SaaS UI.

---

## 5. Signature "Newspaper" Details

Reproduce these to capture the aesthetic:

- **Masthead header** - the contest name set very large in the display serif, centered or
  left-aligned, with hairline rules above/below and small metadata flanking it (location/date
  on one side, edition/round on the other), exactly like a newspaper nameplate.
- **Dateline / status strip** - a thin bar under the masthead in uppercase mono:
  e.g. `TUE 01 SEP 2026 · ROUND 2 · LIVE` with a small pulsing tan dot for "LIVE".
- **Kicker labels** - short uppercase mono tags above headlines (`ANNOUNCEMENT`, `RULES`,
  `UPDATE`, `NEW`), often in `--accent`.
- **Hairline rules & column rules** - 1px `--line` dividers between rows, sections, and
  between text columns.
- **Circular stamp/seal motif** - a small circular badge (SVG) with text-on-a-circle can act
  as a logo mark or an "official" seal for the contest. (This is the *static* stamp - **not**
  the rotating one.)
- **Marquee ticker (optional, tasteful)** - a single horizontally scrolling strip near the top
  for breaking announcements (`⚠ Problem C statement updated · Extension: +15 min · …`).
  Keep it slow, pause on hover, and honor `prefers-reduced-motion`.

---

## 6. Component Specs (mapped to the contest site)

### 6.1 Header / Navigation
- Masthead contest title (display serif) + horizontal nav: **Leaderboard · Announcements ·
  Info · Rules**.
- Nav items: uppercase mono or sans small-caps; active item underlined or in `--accent`.
- Right side: live status tag + a clock/countdown in mono.
- Sticky on scroll with a subtle bottom hairline; background `--paper` (add faint shadow only
  when scrolled).

### 6.2 Leaderboard (primary screen)
- A bordered **table** with a `--line` grid, reading like a printed results table.
- **Columns:** Rank · Contestant · Solved · Penalty/Time · (optional per-problem cells).
- **All numbers** in `--font-mono` + `tabular-nums`.
- **Header row:** uppercase mono labels, `--ink`, `border-bottom: 1px solid --line-strong`;
  make it **sticky**.
- **Rows:** zebra striping using `--paper` / `--paper-panel`. Row hover → `--paper-sunk`.
- **Top 3:** emphasize with the tan accent - e.g. rank number in `--accent`, a small
  medal/seal glyph, and a slightly heavier bottom rule under the top-3 block.
- **Per-problem status cells** (optional): use a compact monospace glyph or fill -
  solved = filled `--ok` cell with `+`, attempted = `--bad` outline with `−`, untried = empty.
  Keep these muted; the table should still read as ink-on-paper.
- **Live updates:** briefly flash a row's background to `--accent` at ~8% opacity on rank change,
  then fade. No layout jumps.
- Provide a clear **last-updated** timestamp (mono) and a manual refresh affordance.

### 6.3 Announcements (editorial feed)
- Each announcement is styled like a **news article**: kicker label (mono, `--accent`) +
  timestamp (mono, `--ink-muted`) → serif **headline** → body paragraph(s).
- Separate items with hairline rules. Newest first; pin urgent ones at top with a small
  `PINNED` / `⚠` marker.
- Optional 2-column newspaper layout on desktop; single column on mobile.
- Optional marquee ticker (see §5) for the most urgent line.

### 6.4 Info / Rules / General
- Big serif section titles with a numbered index (`01 - Format`, `02 - Scoring`) in mono/tan.
- Body in readable measure (`max-width: 68ch`), generous leading.
- Use **definition-list** or **two-column key/value** blocks for schedule, prizes, eligibility.
- Callouts/notes: a bordered box (`--border`, `--paper-panel` fill) with a mono kicker.

### 6.5 Footer
- Copyright "stamp" + small mono links (Rules, Contact, Discord/socials), organizer credit,
  and a repeat of the dateline. Hairline rule on top.

### 6.6 Buttons & links
- **Links:** `--ink` with a 1px underline offset; hover → `--accent`.
- **Primary button:** solid `--ink` background, `--paper` text, sharp corners; hover →
  `--accent-deep`. **Secondary:** `--border` outline, transparent fill, hover fills `--paper-panel`.
- Keep buttons rectangular and understated - this is editorial, not a marketing landing page.

---

## 7. Motion & Interaction

Keep it **subtle, fast, and functional**. The source is animation-heavy; we deliberately are not.

- **Allowed:** short fade/slide-up (8–16px, 300–500ms, ease-out) as sections enter viewport;
  underline reveals on hover; row-highlight flashes on leaderboard updates; slow marquee ticker.
- **Avoid:** device-rotation prompts, 3D/WebGL scenes, spinning/rotating elements, parallax-heavy
  hero, cursor-follow blobs, page-transition curtains.
- Always respect `@media (prefers-reduced-motion: reduce)` - disable marquee and entrance
  animations, keep instant state changes.

---

## 8. Accessibility & Responsiveness

- Maintain WCAG AA contrast. `--ink` on `--paper` is strong; `--ink-muted` only for
  non-essential metadata. Never rely on the tan accent alone to convey state - pair with text/glyph.
- Leaderboard: real `<table>` semantics with `<thead>/<th scope>`, caption, and sticky header;
  make it horizontally scrollable on mobile inside a bordered container (don't crush columns).
- Minimum body size 16px; tap targets ≥44px.
- Breakpoints: `≥1024px` full multi-column; `640–1024px` condensed; `<640px` single column,
  nav collapses to a simple menu, masthead scales down via the fluid `--fs-display`.

---

## 9. Do / Don't Summary

**Do**
- Warm paper background, near-black ink, one tan accent.
- Oversized high-contrast serif headlines; grotesque body; monospace for numbers & labels.
- Hairline rules, kicker labels, datelines, sharp corners, generous whitespace.
- `tabular-nums` everywhere numbers align.

**Don't**
- No rotating/3D effects, no "rotate your device" screen, no heavy WebGL.
- No rounded, shadow-heavy "SaaS card" look.
- No rainbow of colors - stay two-tone + tan (+ muted functional colors only where needed).

---

## 10. Notes for Claude Code (implementation)

- **Stack:** plain HTML/CSS/JS or React + Tailwind both work. If Tailwind, map the tokens in
  §2–§4 into `tailwind.config` (`theme.extend.colors`, `fontFamily`, `fontSize`) so classes
  stay semantic. If vanilla, put all tokens in `:root` as above and use them directly.
- **Fonts:** load the free stack from Google Fonts (Fraunces, Inter, JetBrains Mono). Preload
  the display weight; use `font-display: swap`.
- **Data:** leaderboard/announcements should render from a data source (JSON/API). Build the
  components to accept an array of rows/items; include a graceful empty state and a
  `last updated` field. Poll or websocket for live updates; animate row changes per §6.2.
- **Structure suggestion:** `Header/Masthead`, `Ticker`, `LeaderboardTable`, `AnnouncementsFeed`,
  `InfoSection`, `Footer`, plus shared `KickerLabel`, `StatusTag`, `Rule`, and `Seal` primitives.
- Ship the token file first, then build components against it so the whole site stays consistent.

> Values marked "approx." (the cream paper shades) are reasonable reconstructions - the source's
> published palette lists only its two dominant inks (`#000` and `#987654`). Adjust the paper
> tone to taste; keep it a warm, low-saturation off-white.
