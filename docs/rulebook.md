# Contest Rulebook - One-Pager (participant handout)

This file has two parts:
1. **Instructions for Claude Design** - the brief to paste in so it builds the page.
2. **Rulebook content** - the copy to lay out on the page.

Everything here is participant-facing. It deliberately does NOT reveal the hidden
side quests, easter eggs, or the recognition-award list - those are teased only.

---

## Part 1 - Instructions for Claude Design

> Paste the block below into Claude Design as your prompt, then hand it "Part 2 -
> Rulebook content" as the copy to place.

**Build:** a single-page **A4 portrait** rulebook / handout (one artboard, print-ready,
also readable on a phone). One page only - it must fit without scrolling when exported
to PDF. Dense but calm; a participant should scan it in 60 seconds.

**Visual theme (match `design.md` - "Paper Portfolio" editorial/newspaper look):**
- **Palette (two inks on paper, one warm accent):**
  - paper `#F3F0E9`, panel `#EAE6DC`, sunk `#E2DDD0`
  - ink `#0A0A0A`, ink-soft `#2B2A27`, ink-muted `#6B675E`
  - accent (warm tan) `#987654`, accent-deep `#6F5638`
  - hairlines `rgba(10,10,10,0.16)` and `rgba(10,10,10,0.42)`
  - functional (use sparingly): ok `#3C7A4E`, warn `#B07B2C`, bad `#A6483C`
- **Type:** display serif **Fraunces** (headlines), body sans **Inter**, mono
  **JetBrains Mono** (all numbers, times, scores, kicker labels). Numbers use
  `tabular-nums`.
- **Feel:** oversized high-contrast serif masthead, uppercase mono kicker labels with
  wide tracking, 1px hairline rules between sections, sharp corners (radius <= 2px),
  generous whitespace. Hierarchy comes from type/scale/weight/rules, NOT many colors.
- **No** rounded SaaS cards, no drop shadows, no gradients, no 3D, no rainbow color.

**Layout (top to bottom):**
1. **Masthead** - contest name huge in Fraunces, centered, hairline rules above/below.
   Dateline strip under it in uppercase mono: `12-HOUR ONLINE CONTEST · INDIVIDUAL · 24 PROBLEMS`.
2. **Two-column body** (single column on phone). Place the sections from Part 2 as
   editorial blocks with mono kicker labels (`SCHEDULE`, `SCORING`, `RULES`, ...) above
   serif sub-heads.
3. **Schedule** as a mono definition-list / timeline (time on the left in tan mono).
4. **Scoring** as a compact key/value or tiny table; keep the formula in mono.
5. **Prizes** block ends with the teaser line - render the teaser in accent tan, slightly
   larger, as the emotional hook. Do not list the hidden awards.
6. **Footer stamp** - a small circular "official seal" motif (static, SVG) + the club
   name + a one-line "good luck".

**Do:** keep it one page, print-safe margins, high contrast (WCAG AA), phone-legible.
**Don't:** reveal hidden prizes/side quests; add colors beyond the palette; use em dashes
(use `-`).

---

## Part 2 - Rulebook content

### Masthead
**Njack Freshmen CP Orientation Contest**
Dateline: `12-HOUR ONLINE CONTEST · INDIVIDUAL · 24 PROBLEMS · BEGINNER-FRIENDLY`

### The gist
A 12-hour, beginner-friendly programming contest. 24 problems across three themed sets.
The goal is simple: **everyone solves at least one.** No prior competitive-programming
experience needed - if you learned `print()` this week, problem A1 is for you.

### Schedule (10:00 - 22:00)
| Time | What happens |
|---|---|
| 10:00 | Contest opens - **Set A** released (JEE / pre-college life) |
| 14:00 | **Set B** released (film, music, internet culture) |
| 18:00 | **Set C** released (college & campus life) |
| 21:00 | **Leaderboard freezes** - board stops updating, judging continues |
| 22:00 | Contest closes |
| 23:00 | Final standings + editorials + awards |

All 24 problems are out by 18:00. Take breaks - scoring does not reward grinding non-stop.

### Scoring (short version)
- **Base points** by set and difficulty: 100-200 (A), 200-400 (B), 300-450-600 (C).
- **Wrong answer:** each wrong submission cuts that problem's value by 15%, floored at 40%.
- **Compile errors are free** - they never count. Experiment freely.
- **First-solver bonus:** first three to solve a problem get x1.20 / x1.12 / x1.06.
- **Formula:** `score = base x decay x first_solver_bonus`.
- **Ties break on:** fewest total wrong submissions, then earliest last solve.

### Rules & conduct
1. **Individual** event. One account per person.
2. **No sharing** code, approaches, or hints while the contest is live. Discussion opens after it closes.
3. Personal templates and reference material are fine.
4. **AI:** allowed only to explain concepts. Requesting or submitting a full solution is not allowed. The person most cheated by outsourcing a solve is you.
5. **Clarifications** go through the announcements channel only - answers are broadcast to everyone.
6. **Be kind.** Harassment or targeting anyone gets you removed.

### Learn as you go
Every problem ends with a **"Learn More"** footer - links to the exact concepts you need.
A one-page cheat sheet (both languages, side by side) is shared before the start.

### Prizes
- **Top 3 overall.**
- **Best in each set** - highest score in Set A, Set B, and Set C.

> **...and that's only the start.** There are many more ways to win - surprise awards and
> hidden challenges scattered through the contest. Keep your eyes open, read carefully,
> and explore. Some prizes find the people who go looking.

### Footer
Good luck, and welcome to the club. - Njack CP
