# Freshmen Competitive Programming Orientation Contest
## Official Contest Documentation (Draft v1.0)

**Event type:** 12-hour online individual programming contest
**Audience:** First-year students, majority with no prior competitive programming exposure
**Prerequisite session:** "Hello World" orientation - IDE setup, language basics, I/O patterns

---

## 1. Objectives

1. Convert a one-off orientation session into sustained engagement with the coding club.
2. Guarantee that **every registered participant solves at least one problem.** This is the primary success metric, ahead of leaderboard quality or problem difficulty.
3. Build peer connections across the batch through side quests, group activity, and prediction mechanics.
4. Introduce the standard competitive programming toolchain - IDE, stdin/stdout, submission verdicts, editorials - in a low-stakes environment.

**Secondary metric:** number of participants who register on Codeforces and attempt a Div. 3/Div. 4 round within two weeks of the contest.

---

## 3. Contest Structure

### 3.1 Problem sets

24 problems, released in three themed sets of eight.

| Set | Theme | Difficulty ceiling (CF rating equivalent) | Intended solve rate |
|---|---|---|---|
| **A** | JEE / pre-college life | ≤ 800 | 90%+ of participants solve at least 3 |
| **B** | Entertainment, film, music, internet culture | ≤ 900 | 50% solve at least 3 |
| **C** | College and campus life | ≤ 1100 | 20% solve at least 3 |

Within each set, problems are ordered by difficulty (slot 1 easiest, slot 8 hardest). **A1 must be solvable by someone who learned `print()` four hours earlier** - a fixed-string output problem, themed to the college.

### 3.2 Release schedule

The contest runs as a single 12-hour daytime window (10:00–22:00), with the three sets released on a uniform 4-hour cadence. This keeps all content inside waking hours and avoids any structural reward for sleep deprivation.

| Time | Event |
|---|---|
| T+0h (10:00) | Contest opens. Set A released. |
| T+4h (14:00) | Set B released. |
| T+8h (18:00) | Set C released. |
| T+11h (21:00) | **Leaderboard freezes.** |
| T+12h (22:00) | Contest closes. |
| T+13h (23:00) | Final standings and editorials published. |

All 24 problems are therefore available well before the close, and no participant is forced to stay up late to access content. See §11.

### 3.3 Per-problem statement format

Every problem statement must contain:

1. **Story block** - themed narrative. Recurring cast recommended (see §7.5).
2. **Formal statement** - restated without narrative, unambiguously.
3. **Constraints**, input format, output format.
4. **Two sample cases minimum**, one of which is trivially small.
5. **"Learn More" footer** - 1–3 links to GeeksforGeeks, CP-Algorithms, or cplusplus.com covering the concepts needed. This footer is what converts the contest into a teaching instrument; it is not optional.

---

## 4. Scoring System

### 4.1 Base points

Base points rise linearly with a problem's slot (its difficulty order within the contest). Each slot is worth `0.1 x 100 = 10` more than the previous one, starting at 100:

```
base(slot) = 100 + (slot - 1) * 10
```

| Slot | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 |
|---|---|---|---|---|---|---|---|---|
| Base | 100 | 110 | 120 | 130 | 140 | 150 | 160 | 170 |

Base is **independent of the set** (A / B / C): a later, harder problem always outscores an earlier one, wherever it lives. Maximum attainable base score over 24 problems (three sets of eight): **3 x (100+110+...+170) = 3 x 1080 = 3240**.

### 4.2 Wrong-answer decay

Each wrong submission on a problem reduces that problem's value by 15%, floored at 40%.

```
decay(W) = max(0.4, 1 - 0.15 * W)
```

| Wrong submissions before AC | 0 | 1 | 2 | 3 | 4+ |
|---|---|---|---|---|---|
| Multiplier | 1.00 | 0.85 | 0.70 | 0.55 | 0.40 |

**Compilation errors are not counted** as wrong submissions. Beginners produce a large volume of compilation errors and penalising them discourages experimentation.

The floor at 4 wrong submissions means guessing is never *more* costly beyond that point. This is deliberate - a beginner stuck on a problem must never be told the situation is hopeless. The incentive against blind guessing is instead carried by the first tiebreaker (§4.4).

### 4.3 First-solver multiplier

The first three participants to solve each problem receive a bonus multiplier on that problem only.

| Solve order | Multiplier |
|---|---|
| 1st | 1.20 |
| 2nd | 1.12 |
| 3rd | 1.06 |
| 4th onward | 1.00 |

### 4.4 Final formula and ranking

```
problem_score = base * decay(W) * first_solver_multiplier
total_score   = sum of problem_score over all solved problems
```

Scores are rounded to the nearest integer at display time only; all internal computation uses full precision.

**Ranking order:**

1. **Total score** - descending.
2. **Total wrong submissions across the contest** - ascending. *(Fewer negatives ranks higher.)*
3. **Timestamp of last scoring submission** - ascending.

**Worked example.** Participant solves a slot-5 problem (base 140) with 2 prior wrong submissions, and is the 2nd solver:

```
140 * 0.70 * 1.12 = 109.76
```

### 4.5 Leaderboard freeze

Standings freeze at T+11h. Submissions continue to be accepted and judged, but the public board stops updating. Final standings are revealed at T+13h alongside the editorial stream. The freeze is the single highest-value piece of drama in the format - do not skip it.

---

## 5. Technical Infrastructure

### 5.1 Architecture

| Layer | Choice |
|---|---|
| Judge | Codeforces group contest / mashup (problems hosted and judged on CF) |
| Data ingestion | Codeforces API, polled on a schedule |
| Scoring engine | Custom - CF's own scoring is **not** used |
| Frontend | Next.js on Vercel |
| Snapshot store | Serverless KV or a committed JSON history file |

### 5.2 Ingestion notes

- Poll `contest.status` (full submission list), **not** `contest.standings`. The custom scoring model in §4 cannot be derived from CF standings.
- Codeforces rate-limits its API. Poll on a fixed interval (60–120 s is ample), cache aggressively, and never poll per-page-load.
- Persist a standings snapshot at every poll. These snapshots are the data source for the rank-over-time graph (§6.2).
- **Verify API access to a private group contest during the build phase, not on contest day.** Authenticated endpoints require an API key whose owner has access to the contest, and behaviour differs between gyms, group contests, and mashups. Confirm this works at least one week ahead.

### 5.3 Mandatory fallback

Build a manual override path: an admin endpoint that accepts a CSV submission dump and recomputes the entire leaderboard. If the API path fails mid-contest, the fallback must be usable within ten minutes. Test it before the contest starts.

### 5.4 Site features

- Live leaderboard with per-problem cell state (solved / attempted / first-solver highlight).
- Countdown to next problem release.
- Announcements feed.
- Problem index with links, themes, and "Learn More" footers.
- Freeze indicator once T+11h passes.

---

## 6. Live Engagement Features

### 6.1 Announcements
Pinned channel, organizers only. Clarifications, release notices, side-quest hints, and periodic "N people have now solved A1" milestones.(can remove)

### 6.2 Rank-over-time graph
A concurrent plot of each participant's rank across the contest duration, rendered from the snapshot history. Displayed live on the site and replayed during the closing session. This visualisation is what makes comebacks legible and is worth the engineering cost. (might get messy so need to think/only top 10)

### 6.3 Prediction pool ("The Bookie's Table")
Participants and non-participants may stake **non-transferable prediction points** - an in-contest currency with no monetary value and no purchase mechanism - on outcomes such as:(just bw team)

- Who reaches 10 solves first
- Whether problem C8 will be solved at all
- Final top-3 composition

The purpose is social: it gives non-competing seniors and less confident freshmen a reason to watch the board and talk to each other. **No real money, no entry fee, no cash-equivalent payout.** Prizes are limited to the recognition categories in §10.

---

## 7. Side Quests and Easter Eggs

Side quests award **bonus points capped at 5% of total attainable score**, and are never required to place well. Several involve physical presence on campus; these must remain strictly optional and awarded only in the small-prize categories, since day scholars and students who are travelling cannot participate equally.

### 7.1 Hidden URL
A path referenced only in the page source, an HTTP header, or a problem statement's whitespace. Leads to a bonus problem or a claim form.

### 7.2 Assembled URL
Expected outputs of designated problems are fragments of a URL. A participant who solves all fragments can concatenate them into a working link. Publish the fragment count so participants know when they have a complete set.

### 7.3 Physical checkpoints
- A marked table at CLH holding a QR code or passphrase card.
- A briefed staff cameo (e.g. the Nescafé counter) who supplies a token on the correct passphrase.

**Requirements:** brief the person in advance and get their consent; confirm their operating hours and state those hours in the announcement; provide an equivalent online alternative so that no participant is disadvantaged by location or by the hour at which they are working.

### 7.4 Find the Imposter
A senior competes under an undisclosed handle. Participants submit one guess via form. Correct guessers enter a draw. Reveal at the closing session.

### 7.5 inside jokes
Establish 3–4 recurring characters across the 24 statements - a perpetually attendance-short student, the Nescafé counter, a senior giving bad advice, a JEE-era coaching instructor. Continuity across problems is what turns a problem set into a story people quote afterward.

### 7.6 Community puzzles
A Connections-style or Wordle-style puzzle posted in the group at fixed times, unrelated to the main scoring. Drives group activity during the quieter mid-contest lulls.

### 7.7 Social tags
One of the hidden rewards are hid in the comment section of the pr post

---

## 8. AI Usage Policy

### 8.1 Position

A ban on AI assistance in a 12-hour, unproctored, remote contest is unenforceable. A policy that cannot be enforced converts honest participants into disadvantaged participants and teaches freshmen that stated rules are decorative. The following policy is therefore recommended.

### 8.2 Recommended policy

**AI tools are permitted only for concept explanation. Requesting or submitting a complete solution to a contest problem is prohibited.**

This is stated as an honour expectation, backed by one enforceable control:

This is announced in advance, in the briefing and in the rules. Announcing it beforehand is what gives it deterrent effect; applying it retroactively would be unfair.

### 8.3 Structural mitigation

Prize categories weighted toward outcomes that AI cannot produce: physical checkpoints, group participation, prediction accuracy, imposter identification, comeback trajectory. These carry a meaningful share of the total prize count precisely because they are AI-proof.

### 8.4 Framing

The briefing should state the reasoning plainly: the contest exists to make participants better programmers, an AI-generated accepted verdict transfers nothing, and the person most disadvantaged by outsourcing a solution is the one doing it. Delivered as an argument rather than a threat, this is more effective with this audience than a prohibition would be.

---

## 9. Rules and Conduct

1. Individual participation. One account per person; multiple accounts are grounds for disqualification.
2. No sharing of code, approaches, or hints with other participants while the contest is live. Discussion is open after T+12h.
3. Use of pre-written personal templates and reference material is permitted.
4. AI usage per §8.
5. Organizers may not compete for prizes. Seniors may participate for fun; their scores are shown separately and excluded from prize ranking (excepting the designated imposter, §7.4).
6. Statement clarifications are requested through the announcement channel only, and answers are broadcast to everyone.
7. **Reporting.** Any participant may report suspected rule violations to a sub-coordinator at any time during the contest, through a stated private channel. Reports are confidential, reviewed by at least two organizers, and no action is taken on a single unverified report. Reporters' identities are not disclosed.
8. Harassment, abuse, or targeting of any participant in any channel results in immediate removal from the contest and referral to the club coordinators unless the harassment was targeted towards whoever made the bs question.
9. Organizer decisions on scoring disputes are final, but all disputes are logged and the resolution is published.

---

## 10. Prizes

### 10.1 Principal awards
- 1st, 2nd, 3rd overall (major prize)
- Best set-wise performance: highest score in Set A, Set B, Set C individually

### 10.2 Recognition awards

These carry the majority of the total prize count. They exist to ensure a large fraction of participants leave with something, and to reward behaviours the leaderboard cannot see. Rewards may be small - stickers, badges, a mug, a printed certificate. Recognition is the reward.

| Award | Criterion |
|---|---|
| **Certified Wrong Answer Machine** | Most wrong submissions across the contest |
| **Persistence of Vision** | Most wrong submissions on a single problem *before eventually getting AC* |
| **First Blood (Negative)** | First wrong submission of the contest |
| **One Shot, One Kill** | Highest AC-to-submission ratio (minimum 5 solves) |
| **Buzzer Beater** | Last accepted submission before the contest closes that gave a change in ranking |
| **The Comeback** | Largest rank improvement after the freeze |
| **The Constant** | Participant whose rank changed least across the contest |
| **Lone Wolf** | Only participant to solve a given problem |
| **Sniper** | Solved the hardest problem in their solve set, and little else |
| **Novelist** | Longest accepted solution by character count |
| **Code Golf Champion** | Shortest accepted solution |
| **Left the Debug Print In** | Most `cout`/`print` debug statements surviving in accepted code |
| **Naming Things Is Hard** | Least defensible variable names in accepted code |
| **The Rebel** | Best performance in a language other than Python or C or C++ / weirdest lang used |
| **Nocturnal** | Most submissions in the final hour (21:00–22:00) *(awarded, but see §11)* |
| **Inspect Element** | First to find the hidden URL |
| **Among Us** | Correctly identified the imposter |
| **The Bookie** | Best prediction-pool record |
| **Sunk Cost** | Worst prediction-pool record |
| **Yapper of the Contest** | Most active in the group chat |
| **Field Agent** | First to reach the physical checkpoint |
| **Nescafé Loyalty Card** | Most physical checkpoint interactions |
| **Best Handle** | Voted |
| **Best Meme** | After the contest run a google form for opinion and ask for a meme / sticker |
| **Best Doubt** | Funniest genuine question asked in the group |
| **Fair Play** | Participant who reported a verified issue or helped resolve one |

**Note on tone.** Every award above is affectionate or neutral. Deliberately excluded: any award for the largest *drop* in rank, the lowest score, or the fewest solves. With an audience of first-year students being introduced to the field, an award structure that jokes about failure will land differently on the person receiving it than on the room. Keep the humour pointed at behaviour, never at ability.

---

## 11. Participant Wellbeing

A 12-hour daytime contest (10:00–22:00) largely removes the overnight risk of the 24-hour format, but a foreseeable risk remains that participants will grind continuously without breaks.

- The release schedule in §3.2 keeps all content inside waking hours; the final set is out by 18:00.
- The briefing and at least two in-contest announcements should state explicitly that breaks are expected and that the scoring model does not reward continuous presence.
- The **Nocturnal** award is presented as a joke about the recipient's choices, not as an aspiration. Do not announce it in advance.
- Organizers work in shifts. A named on-duty sub-coordinator is listed at all times across the full window.

---

### Run-of-show checklist

- **T−7 days:** all problems set and tested; CF API access verified; site deployed to staging.
- **T−3 days:** full dry run with 5 testers, including a fallback-path drill.
- **T−1 day:** accounts pre-created, credentials distributed, templates and cheat sheet shared.
- **T−0:** orientation session, then contest opens.
- **T+13h:** editorial stream, standings reveal, awards, next-steps briefing.
- **All Through the contest** Send the micro rewards winner to make people look out for more
---

## 13. Risk Register

| Risk | Mitigation |
|---|---|
| CF API inaccessible for private contests | Verify at T−7 days; CSV fallback path (§5.3) |
| Widespread AI use flattens leaderboard | Prize Eligibility Review (§8.2); AI-proof award categories |
| Support gap during the contest window | Named on-duty sub-coordinator per shift |
| Scoring dispute post-freeze | All submission data retained; recompute is deterministic and re-runnable |

---

## 14. Post-Contest

1. **Editorial stream** immediately after the reveal. Walk through 3–4 problems, prioritising the ones with the lowest solve rates and the pure-reasoning problems.
2. **Written editorials** published for all 24 problems within one week.
3. **Next steps slide**, shown while the audience is still in the room: Codeforces registration, CSES problem set, club meeting schedule, permanent group invite link. The contest generates the enthusiasm; the following 48 hours determine whether any of it persists.
4. **Retrospective** with solve-rate data per problem, participation funnel, and a written note on what to change. This document is versioned and carried forward.

---

## Appendix A - Problem Statement Template

```
[SET-SLOT] Title
Theme: A / B / C     Base points: ___     Target rating: ___

--- STORY ---
[Narrative, 3-6 lines, recurring cast where possible]

--- STATEMENT ---
[Formal restatement, no narrative]

--- INPUT ---
--- OUTPUT ---
--- CONSTRAINTS ---
--- SAMPLE 1 --- (trivially small)
--- SAMPLE 2 ---
--- EXPLANATION ---

--- LEARN MORE ---
[1-3 links: GeeksforGeeks / CP-Algorithms / language reference]
```

## Appendix B - Cheat Sheet Contents

Single page, both languages side by side: reading a single value; reading multiple values on one line; reading N values into a list/vector; printing with and without newlines; `if`/`else`; `for` and `while`; string length, indexing, and reversal; integer division and modulo; sorting a list/vector; common compilation error messages and what they actually mean.

---
