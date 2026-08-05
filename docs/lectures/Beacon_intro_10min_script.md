# GA4GH Beacon — 10-minute introduction (presenter script)

Companion to `Beacon_intro_10min.pptx`. Speaker notes are also embedded in the
deck itself; this file is the longer, conversational version.

**Total time:** 10:00 (≈7:30 narration + 2:30 live demo)
**Audience:** honours students, first exposure to GA4GH
**Goal:** by minute 10, students can describe what a Beacon is, hit a real
endpoint, and pick a project from the menu.

---

## Slide 1 — Title (0:00 → 0:15)

> Over the next 10 minutes I want to give you a working understanding of GA4GH
> Beacons — what they are, why they exist, what they look like in production,
> and what you can build on top of one. By the end you should be able to send a
> query to a real Beacon and tell me what came back.

**Cue:** advance immediately, no pause.

---

## Slide 2 — *What is Beacon API?* (0:15 → 1:15)

> A Beacon answers one question: has anyone, anywhere, in any of the datasets I
> host, observed this genetic variant? You send a chromosome, a position, an
> alternate allele — it replies yes or no.
>
> Why is that useful? The rest of biomedical data sharing is hard — datasets
> are siloed by ethics committees, hosted in different countries, governed by
> different DUAs. A researcher whose patient has a mutation needs to know
> whether anyone else has seen it, but there's nowhere to look. A Beacon's
> answer doesn't tell you whose sample, what condition, when it was sequenced —
> just that it exists in some dataset out there. That's enough to start a
> conversation with the data owner.

**Cue:** advance on "start a conversation."

---

## Slide 3 — *Beacon v1* (1:15 → 2:00)

> This is Beacon v1, from 2014. One endpoint, two possible answers: yes or no.
> By design it leaks the minimum information that's still useful. The
> original idea came from David Haussler at UC Santa Cruz — let's see who's
> actually willing to share at the lowest possible cost, and call those
> institutions Beacons.
>
> Within a year there were dozens. Within two, a federation. Within three —
> we'll come back to this on slide 6 — the privacy researchers showed up.

**Cue:** advance on "we'll come back to this."

---

## Slide 4 — *Beacon v1 in a network* (2:00 → 2:45)

> Once you have many Beacons, you connect them. A Beacon Network is an
> aggregator: fan a query out to all member Beacons in parallel, merge the
> booleans. As a researcher you ask one question and get one answer per
> institution. ELIXIR maintains the largest such network in Europe; we run
> a small one for African Beacons.

**Cue:** advance.

---

## Slide 5 — *Beacon v2* (2:45 → 4:00)

> v2 was approved as a GA4GH standard in 2022. Two things changed.
>
> First, response granularity. v1 only returned yes or no. v2 has three
> levels — boolean, count (how many samples, no identities), record (full
> structured data, usually requires authentication). Operators decide what
> level to expose to whom.
>
> Second — the bigger change — v2 generalised beyond variants. The data model
> now has six entity types: variants, individuals, biosamples, runs, analyses,
> datasets, cohorts. Same protocol, richer queries. "Has this allele been
> seen?" is one question. "How many cohorts contain individuals with
> phenotype X *and* variant Y?" is another. Same shape.
>
> This is also why people have started building Beacons for non-variant data —
> methylation, imaging, microbiome — because the framework decouples from
> variants.

**Cue:** advance on "decouples from variants."

---

## Slide 6 — *Beacon Security* (4:00 → 5:00)

> Privacy is the entire game. The naive view is that yes/no is safe. In 2015
> Shringarpure and Bustamante showed that with a few thousand carefully
> chosen queries you can determine whether a specific person is in a Beacon.
> von Thenen extended the attack in 2019 using linkage disequilibrium —
> fewer queries, harder to detect. In 2025 a reconstruction attack showed you
> can rebuild whole genome regions from summary statistics.
>
> The spec doesn't mandate authentication. It's the operator's call.
> AfriGen-D's public Beacon — which we're about to query — uses rate limiting
> but no login. That's a deliberate choice. We'll discuss it when you pick
> projects.

**Cue:** advance to demo.

---

## Slide 7 — *Beacon v2 Implementation + LIVE DEMO* (5:00 → 8:00)

**Slide context (15 sec):**

> Here's our actual implementation. Django on the API side, MongoDB for
> variants, Redis for caching, nginx in front, deployed on ILIFU.
> Verifier-conformant — 17 out of 17 spec checks pass.

**Switch to browser. Three tabs pre-loaded.**

### Tab 1 — `/info` (≈45 sec)

URL: `https://api-beacon.afrigen-d.dev/api/info`

> The standard envelope: `meta` block with `returnedGranularity: boolean`,
> `response` block with the Beacon's identity. That's the spec.

### Tab 2 — real query (≈60 sec)

URL: `https://api-beacon.afrigen-d.dev/api/g_variants?referenceName=11&start=5246696&referenceBases=A&alternateBases=T`

> A real query. Chromosome 11, position 5246696, A to T. That's the HBB
> sickle-cell variant. Response is `exists: true` — somewhere in our African
> reference panel that variant is present. That's the entire Beacon contract.
> No counts, no identities, no metadata. Just the boolean.

### Tab 3 — verifier output (≈30 sec)

Either show `docs/SPEC_CONFORMANCE.md` in your editor or have the verifier
result JSON on screen.

> Independent verification — the EGA-archive's `beacon-verifier` Rust CLI.
> 17 PASS, 0 FAIL. Real production Beacon, by the spec body's own measure.

**Cue:** switch back to slides.

---

## Slide 8 — *Implementation options (African context)* (8:00 → 8:45)

> The thing that's specific to us: V6HC-S African reference panel — 1,895
> individuals, GRCh38, indexed and queryable. Cross-referenced with AGVD and
> AGMP. African allele frequencies served through a GA4GH-standard discovery
> API. Nobody else has this.

**Cue:** advance.

---

## Slide 9 — *What you can build* (8:45 → 9:45)

> Here's a project menu, sorted roughly by research novelty.
>
> **Privacy:** replicate the re-identification attack on our Beacon and see if
> African data is more or less vulnerable than European data. Nobody has run
> that comparison. Differential-privacy defense layers. Defenses against the
> 2025 reconstruction attack.
>
> **Federation:** anomaly detection on our query log to flag attack-shaped
> traffic. Latency benchmarking across the African Beacon Network.
>
> **Standards:** a property-based fuzzer for Beacon v2 implementations.
>
> **Clinical:** phenopacket-driven cohort discovery — turn our Beacon from
> variant-only into clinical-grade. Pharmacogenomic extension tied into AGMP.
>
> **A whole other family** — Beacons for new data types: pathogens,
> methylation, cancer CNVs, plants, microbiomes, medical imaging. Most of
> these don't exist for African data anywhere. First-mover territory.

**Cue:** advance on "first-mover territory."

---

## Slide 10 — *Next steps* (9:45 → 10:00)

> Homework: Baudis March 2024 talk on YouTube — fifty minutes, best overview
> out there. Read the Rambla 2022 paper. Browse `docs.genomebeacons.org`. Hit
> the live API yourself — same URL we just used.
>
> Pick a project from the menu before our next session. Bring questions.

**Cue:** stop. Take questions or hand off.

---

## Notes for the presenter

- **Pre-load the three demo tabs** before starting. The demo dies if you have
  to type the variant URL in front of the audience.
- **If a tab is slow,** rate limiting may have throttled your IP from a prior
  test run. Have a backup screenshot ready.
- **If you're running short on time,** drop slide 4 (network) and slide 8
  (African context) — the lecture survives without them.
- **If you have extra time,** use it on slide 6 (security) — privacy is the
  most engaging entry point for honours students and the easiest to recruit
  on.
- **Q&A buffer:** the talk is sized for 10 min; you usually have another
  5 min for questions. The most common questions are: "what about the
  GDPR / POPIA?", "how is this different from a database?", and "can I
  break it?". Have one-line answers ready.
