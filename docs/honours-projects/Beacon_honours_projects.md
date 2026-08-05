---
title: "AfriGen-D Beacon — Honours Project Catalogue"
subtitle: "Sixteen projects spanning privacy research, federation, clinical extension, and new Beacon variants"
author: "AfriGen-D · UCT CBIO"
date: "2026-05-06"
---

# Overview

This document catalogues **sixteen honours-level research projects** built on
the AfriGen-D GA4GH Beacon v2 deployment. Each project is scoped for a
**4–6 month** honours dissertation, ties to the existing codebase or live
service, and produces both an engineering deliverable and a measurable
research result.

## How the catalogue is structured

Projects are grouped into seven themes:

- **A. Privacy & security** — attacks and defenses on Beacon responses
- **B. Federation & networking** — the African Beacon Network and its operations
- **C. Standards & conformance** — Beacon v2 specification testing
- **D. Clinical & phenotype queries** — Phenopackets, PharmGKB integration
- **E. UX & visualisation** — privacy-aware result presentation
- **F. Infrastructure & data engineering** — ingest, indexing, scaling
- **G. Other Beacon types** — pathogen, methylation, cancer, plant, microbiome, imaging

Each project entry contains six fields:

| Field | What it captures |
|---|---|
| Research question | The thesis-level question the work answers |
| User-facing question | What end users can now ask of the system |
| Utility | Why it matters (to AfriGen-D, to the field, to the student) |
| Skills learned | Technical and research skills the student gains |
| Knowledge needed | Prerequisite background |
| Difficulty / months / risk | Calibration for a typical honours student |

## Why these projects, on this Beacon

The AfriGen-D Beacon is the only currently deployed, verifier-conformant
GA4GH Beacon v2 over an African reference cohort (V6HC-S_AFR; 1,895
individuals on GRCh38). Its query log is being captured. Its codebase
is documented (`CLAUDE.md`, `docs/SPEC_CONFORMANCE.md`). Its sister
network aggregator (African Beacon Network) is in active development.

Most of the published Beacon literature evaluates on European 1000 Genomes
data. Many open questions — privacy attacks across populations, federated
latency, non-variant Beacons for African endemic disease — are open precisely
*because* nobody has had a real African Beacon to evaluate against. That is
the gap this catalogue exploits.

---

# Theme A — Privacy & security

## A1. Replicating beacon re-identification attacks against an African reference beacon

**Research question.** Does the membership-inference attack power on a Beacon
vary with the ancestry of the underlying cohort? Are African-ancestry Beacons
more, less, or equally vulnerable than European-ancestry Beacons given matched
sample sizes? Which feature of the allele-frequency spectrum (rare-variant
load, LD block size, F~ST~) drives the difference, if any?

**User-facing question.** "If I run a Beacon over my 500 South African
individuals, how many queries does an attacker need to recover one of them?
Should I require authentication for queries below MAF X?"

**Utility.** AfriGen-D operates a public Beacon over African genomes and
needs to know empirically whether the published European attack-power numbers
transfer. If they do, the privacy posture is weaker than assumed. If they
don't, that is a defensible publication arguing for population-aware risk
modelling. Every privacy paper since 2015 evaluates on European 1000G data;
whether attacks scale across populations is genuinely unknown.

**Skills learned.**

- *Technical:* Python statistical computing (scipy, numpy, pandas), VCF
  parsing (pysam/cyvcf2), API client design with rate-limit handling,
  bootstrapping/Monte Carlo simulation, plotting (matplotlib/seaborn).
- *Research:* threat modelling, re-implementing methods from a paper,
  designing power experiments, writing about negative/null results honestly.

**Knowledge needed.** Solid statistics (likelihood-ratio tests, hypothesis
testing) — required. Basic population genetics (allele frequency, MAF, LD)
— self-teachable in 3 weeks. Python proficiency — required. Familiarity
with HTTP APIs.

**Difficulty.** 7/10 (medium-high). The math is well-explained in
Shringarpure & Bustamante (2015) but the student must implement it. The
novelty (African comparison) is what makes it honours-publishable.

**Timeline.** 4–5 months. Month 1: literature + setup + 1000G European
replication. Month 2: African-data attack. Month 3: comparative power
analysis. Month 4: writeup + paper draft.

**Risk.** Low. Worst case: attack works the same on Africans → still a
publishable null result.

---

## A2. Differential-privacy noise layer for Beacon responses

**Research question.** Can we provide ε-DP guarantees on Beacon boolean
responses while keeping researcher utility above a useful threshold? What is
the Pareto frontier of (ε, utility, attack power) on real African data?

**User-facing question.** "If I set ε = 1.0, what fraction of legitimate
variant lookups will I now answer wrongly? What's the minimum cohort size I
need before DP becomes 'free' (utility loss < 5%)?"

**Utility.** This is a deployable security feature — the prototype hardens
the public Beacon directly. DP for genomic Beacons is well-studied
theoretically but few production-deployed implementations exist; a working
open-source middleware would be cited. Differential privacy is one of the
most sought-after specialisations in industry (Apple, Google, US Census).

**Skills learned.**

- *Technical:* Django middleware development, Python decorators, MongoDB
  query interception, statistical mechanism design, A/B testing, utility
  benchmarking.
- *Research:* reading formal cryptography/privacy papers, ε-DP composition
  reasoning, designing utility metrics, defending design choices in writing.

**Knowledge needed.** Strong stats and probability — required. Basic
understanding of DP (ε, δ, sensitivity, Laplace mechanism) — acquirable in
4–6 weeks from Dwork & Roth's *Algorithmic Foundations of DP*. Django + OOP
required.

**Difficulty.** 8.5/10 (hard). The most theoretically demanding project on
the list. Best assigned to a strong honours student aiming at MSc, or an
MSc-bound student. Do not give to a weak student — they will produce
something that *looks* DP but is mathematically broken.

**Timeline.** 5–6 months. Realistically tight; many honours students
under-budget the theory phase.

**Risk.** Medium. Failure mode: implements something they call DP but is
broken. Mitigation: require a formal proof sketch reviewed by a co-supervisor
with cryptography background.

---

## A3. Defending against the 2025 Beacon Reconstruction Attack

**Research question.** Can server-side query-budgeting plus allele-frequency
suppression reduce reconstruction-attack F1 below 0.5 without breaking
benign-user workloads? Which countermeasure subset gives the best
security/utility ratio?

**User-facing question.** "If I'm a benign researcher running 1,000
queries/day, will this defense affect me? How many SNPs of a member's
genome could a determined attacker still reconstruct under our hardened
policy?"

**Utility.** The 2025 reconstruction attack is brand new and the AfriGen-D
Beacon is genuinely vulnerable. There are no published deployable defenses
yet. First-mover advantage; a working defense paper would be timely and
citation-attractive.

**Skills learned.**

- *Technical:* same as A2 (middleware + statistics) plus high-dimensional
  data analysis (correlation matrices, low-rank approximation),
  Redis/cache design for query budgets.
- *Research:* constructive defense design (harder than offense), trade-off
  curves, evaluating against an adversary you simulate yourself.

**Knowledge needed.** Linear algebra (correlation matrices, low-rank
approximation) required. Comfortable reading recent ML/security papers.
Understanding of LD and haplotype structure helps; can be acquired during
the project.

**Difficulty.** 8/10 (hard). Slightly less mathematically demanding than A2
(fewer formal proofs) but more engineering surface area. Better suited than
A2 for an engineering-strong, theory-medium student.

**Timeline.** 5–6 months. Phase 1: replicate attack (1.5 months). Phase 2:
design defenses (2 months). Phase 3: evaluation (1.5 months). Phase 4:
writeup.

**Risk.** Medium-high. Failure mode: defenses break utility too much to be
usable. Mitigation: define "usable" up front via a baseline researcher
use case.

---

# Theme B — Federation & networking

## B1. Beacon network anomaly detection / abuse classifier

**Research question.** Can supervised ML on query logs distinguish
privacy-attack traffic from researcher traffic at AUC > 0.95 with
< 1% false-positive rate? Which features (query inter-arrival, MAF
distribution, position diversity) carry the most signal?

**User-facing question (operator-facing).** "Is this IP currently running a
Shringarpure–Bustamante attack? How much abuse traffic did we receive this
month?" (Grafana panel.)

**Utility.** The `query_logs` collection is already populated but not
analysed. This converts a passive log into an active defense layer.
End-to-end ML system (feature engineering → model → deployment →
monitoring) — a highly employable pattern.

**Skills learned.**

- *Technical:* MongoDB aggregation pipelines, feature engineering on
  time-series logs, scikit-learn (logistic regression, gradient boosting,
  isolation forest), model evaluation (precision/recall/AUC), Grafana panel
  design.
- *Research:* building synthetic adversarial datasets, dealing with extreme
  class imbalance, threshold selection, false-positive cost reasoning.

**Knowledge needed.** Intro ML course (decision trees, regression, basic
evaluation metrics) — required. Python data science (pandas, sklearn) —
required. Basic SQL/NoSQL — pickup in week 1.

**Difficulty.** 5.5/10 (medium). Most students can complete this. The hard
part is *evaluation* — getting realistic positive examples — not the
modelling itself. Pairs naturally with A1.

**Timeline.** 4 months. Month 1: log analysis + feature design. Month 2:
synthetic attack generation. Month 3: training + tuning. Month 4: deployment
+ dashboard + writeup.

**Risk.** Low.

---

## B2. Latency benchmarking & SLO design for the African Beacon Network

**Research question.** What is the latency cost of federation as a function
of node count *N*? Which architectural change (parallel fan-out, partial-
result streaming, response-cache) yields the largest p95 reduction per
engineering hour?

**User-facing question.** "If I query 12 African Beacons, how long should I
wait before retrying? What SLO can the network credibly promise to clinical
users?"

**Utility.** The aggregator (`afrigend-beacon-network`) is in active
development; its real performance characteristics are unknown. This produces
actionable tuning advice. Benchmarking studies of federated genomic systems
are surprisingly rare; most papers handwave performance.

**Skills learned.**

- *Technical:* OpenTelemetry / distributed tracing, Locust load-testing,
  async Python (asyncio, aiohttp), Prometheus / Grafana, network profiling
  (tcpdump, mtr), connection pooling.
- *Research:* designing controlled experiments on networked systems,
  latency-distribution analysis (p50/p95/p99), drawing meaningful
  conclusions from noisy measurements.

**Knowledge needed.** Comfortable with Linux/Docker — required. Networking
fundamentals (HTTP, DNS, TLS basics) — strongly recommended. Async Python —
self-teach in 2 weeks.

**Difficulty.** 5/10 (medium). Lots of bounded sub-tasks; a methodical
student will do well.

**Timeline.** 4 months. Month 1: tracing setup + initial measurements.
Month 2: load testing. Month 3: optimisation experiments. Month 4: SLO
recommendation + writeup.

**Risk.** Low.

---

# Theme C — Standards & conformance

## C1. Property-based fuzzer for Beacon v2 implementations

**Research question.** How many GA4GH Beacon v2 spec violations exist in
publicly deployed Beacons? Which spec sections produce the highest violation
density (i.e., which parts of the spec are ambiguous)?

**User-facing question.** "Is my Beacon implementation actually compliant?"
(developer tool output.) "Which spec sections need clarifying language?"
(input to the GA4GH working group.)

**Utility.** AfriGen-D would own the only open-source Beacon-v2-specific
fuzzer. Discovers real bugs in real production beacons → publishable as a
tool paper plus a "we found *N* bugs in *N* implementations" empirical study.
Property-based testing is high-signal on a CV.

**Skills learned.**

- *Technical:* Hypothesis library (Python), JSON schema, OpenAPI tooling,
  test-oracle design, structured bug reporting.
- *Research:* spec-driven thinking, systematic exploration vs example-driven
  testing, ethics of bug disclosure.

**Knowledge needed.** Python + good unit-testing intuition — required.
Familiarity with REST APIs and JSON — required. Reading formal specs without
giving up — partly a personality fit.

**Difficulty.** 5/10 (medium). Mechanically not hard; the difficulty is
patience and attention to detail. Best fit for a meticulous student.

**Timeline.** 4 months.

**Risk.** Low. Worst case: tool produces clean Beacons with no bugs → student
writes "limitations and false-negative analysis" and still has a thesis.

---

# Theme D — Clinical & phenotype queries

## D1. Phenopackets-driven cohort discovery on the AfriGen Beacon

**Research question.** What is the smallest schema subset needed to answer
80% of clinically meaningful queries on African cohort data? Where do
phenotype representations diverge across H3Africa cohorts, and what
mapping rules harmonise them?

**User-facing question (clinician/researcher).**
"How many sickle-cell carriers in our cohorts also have variant X in
haemoglobin gene Y? Are there ≥ 5 individuals with HbF persistence and a
*BCL11A* enhancer variant? Which African cohorts contain pediatric
individuals with documented G6PD deficiency?"

**Utility.** Highest user-facing impact in the catalogue. The current Beacon
answers "is variant X present?" but cannot answer "how many sickle-cell
carriers in cohort Y also have variant X?" — the question clinicians actually
ask. Closing this gap turns the Beacon from a demo into a clinical tool.
African pharmacogenomics and rare-disease cohorts are critically
under-discoverable.

**Skills learned.**

- *Technical:* MongoEngine ODM design, JSON schema validation, ontology
  lookup (HPO, OMIM, Mondo), DRF view design, end-to-end testing.
- *Research:* schema design trade-offs, ontology mapping, evaluation against
  clinical query exemplars.

**Knowledge needed.** Python + Django basics (or willingness to learn — the
existing codebase is a strong example). Some genetics/genomics background.
JSON / REST literacy — required.

**Difficulty.** 6/10 (medium). Well-bounded and high-impact. Lots of
sub-tasks of varying difficulty, so good for honours: student can always
retreat to a smaller scope if blocked.

**Timeline.** 5 months.

**Risk.** Low. Even partial implementation (individuals only, no biosamples)
is useful and thesis-able.

---

## D2. Pharmacogenomics-aware Beacon extension (AGMP integration)

**Research question.** Can a star-allele-aware Beacon respond to clinically
meaningful PGx questions faster than ad-hoc SQL on PharmCAT outputs? Do
African star-allele frequencies inferred from the Beacon agree with
published PharmGKB Africa-specific data?

**User-facing question (clinician).**
"How prevalent is *CYP2D6\*17* in our Southern African cohort? Is there at
least one individual with the *CYP2B6\*6/\*6* genotype (relevant to
efavirenz dosing)? Which PGx-relevant variants are observed in our HIV
cohort?"

**Utility.** AGMP is already a sister site of AfriGen-D; tighter integration
into the Beacon is a stated AfriGen-D goal. Pharmacogenomic Beacons are not
a standard yet — the project would help define the pattern.

**Skills learned.**

- *Technical:* CYP / star-allele nomenclature, PharmGKB and CPIC data, REST
  API extension, frontend integration (Next.js / TypeScript if doing UI).
- *Research:* pharmacogenomic biology, clinical relevance reasoning.

**Knowledge needed.** Python + Django — required. Some pharmacology /
genetics interest — required for motivation.

**Difficulty.** 4.5/10 (medium-easy). Smaller research question; mostly
engineering. Good fit for a strong-engineer / weak-statistician student.

**Timeline.** 4 months.

**Risk.** Low.

---

# Theme E — UX & visualisation

## E1. Privacy-aware visualisation of Beacon results

**Research question.** Do researchers' decisions change when shown banded
counts vs raw counts vs DP-noised counts? Which visualisation form yields
the best researcher-trust score given equivalent privacy guarantees?

**User-facing question.** "Should I bother running a follow-up study on
this variant — how rare is rare? Is the data here statistically powered for
my downstream analysis?"

**Utility.** The current frontend (`DatasetResults.tsx`) shows raw counts —
which the privacy literature shows is risky. This project produces
evidence-backed redesigns. HCI-meets-privacy in genomics is genuinely
understudied.

**Skills learned.**

- *Technical:* React + TypeScript, Next.js App Router, Tailwind CSS,
  accessibility basics, user-study tooling.
- *Research:* designing user studies, ethics-board applications, interview
  coding, qualitative + quantitative analysis.

**Knowledge needed.** TypeScript or willingness to learn — required for
implementation. An HCI or research-methods course is a strong plus.

**Difficulty.** 5.5/10 (medium). Difficulty balanced toward research design
rather than coding. Best for a student with HCI inclination, possibly from a
non-CS background.

**Timeline.** 4 months. Note ethics-board approval can eat 2–6 weeks — start
early.

**Risk.** Medium. The ethics timeline is the biggest single risk.
Mitigation: backup task (technical-only redesign without user study).

---

# Theme F — Infrastructure & data engineering

## F1. Bulk-ingest pipeline benchmarking on V7HC-S panel

**Research question.** What is the throughput ceiling of the current
Mongo-based Beacon backend at v7 reference-panel scale? Does an analytical
store (ClickHouse / DuckDB+Parquet) outperform the document store on
Beacon-typical workloads?

**User-facing question.** "Can we host V7HC-S in production without changing
the storage layer? What's the cost-per-query at v7 scale?"

**Utility.** V7HC-S exists on ILIFU but isn't loaded into the Beacon. Whether
the current pipeline can ingest it at scale is unknown. A benchmark answers
the question and produces tuning recommendations. Data engineering skills
are universally hireable.

**Skills learned.**

- *Technical:* Nextflow pipeline development, MongoDB indexing and sharding,
  comparative database evaluation (Mongo vs ClickHouse vs DuckDB+Parquet),
  profiling tools (cProfile, py-spy), benchmarking methodology.
- *Research:* designing fair comparisons across heterogeneous systems,
  choosing evaluation metrics that survive scrutiny.

**Knowledge needed.** Linux + Docker — required. SQL or basic database
concepts — required. Nextflow can be self-taught.

**Difficulty.** 5.5/10 (medium). Lots of moving parts; a methodical student
will produce a strong report.

**Timeline.** 4 months.

**Risk.** Low-medium. ILIFU access scheduling can be a bottleneck; ensure
the student has compute-node SSH access from week 1.

---

# Theme G — Other Beacon types

## G1. Pathogen Beacon for African endemic diseases (TB / HIV / malaria / mpox)

**Research question.** Can a privacy-preserving Beacon over pathogen sequence
data support outbreak-response queries with sub-second latency? What is the
minimum spatio-temporal coarsening that prevents source-case re-identification
while retaining epidemiological utility?

**User-facing question (epidemiologist / public-health official).**
"Has the *katG S315T* isoniazid-resistance mutation been observed in TB
isolates from Western Cape in the last 90 days? Which African countries have
reported the *Plasmodium falciparum* K13 C580Y artemisinin-resistance
mutation since 2025? Is this newly-sequenced HIV pol fragment consistent
with strains already in our network?"

**Utility.** Africa generates pathogen sequence data continuously (NICD,
KEMRI, ACEGID, CERI), but discovery infrastructure is fragmented. Viral
Beacon (CRG) only covers SARS-CoV-2 with European compute. There is *no*
deployed Beacon for HIV, TB, malaria, or mpox — first-mover territory.

**Skills learned.**

- *Technical:* phylogenetics tooling (Nextstrain auspice JSON, pangolin
  lineage, USHER), pathogen-specific bioinformatics (HIV drug-resistance
  interpretation, MTB lineage typing, *Plasmodium* drug-resistance markers),
  GISAID/NCBI data ingestion, Django modelling.
- *Research:* outbreak data ethics, surveillance vs research data
  distinction, geospatial privacy, time-binning trade-offs.

**Knowledge needed.** Bioinformatics fundamentals (alignments, FASTA,
mutation calling) — required. Some interest in microbiology / epidemiology.
Python + Django.

**Difficulty.** 7/10 (medium-high). The pathogen-specific bioinformatics is
the real challenge; the Beacon shape is the easy part.

**Timeline.** 5 months. Pick *one* pathogen — TB is concrete and
politically valuable; HIV is data-rich; malaria is clinically urgent.

**Risk.** Medium. Data access can be slow (DUAs from data providers).
Mitigation: start with public NCBI/GISAID data only.

---

## G2. Methylation Beacon (MBeacon) for African epigenomes

**Research question.** Does the Hagestedt et al. (2019) SVT2 mechanism
preserve utility on African methylation cohorts of realistic size? Are
African EPIC array cohorts more or less vulnerable to the methylation
membership-inference attack than European ones?

**User-facing question (epigenomics researcher).**
"Is hypermethylation at *MGMT* observed in our pediatric ALL cohort? Which
African studies report differential methylation at *AHRR* in tobacco-exposed
individuals?"

**Utility.** Methylation is increasingly recognised as a key intermediate
phenotype linking environment and disease in African populations. There is
no African epigenetics discovery infrastructure. MBeacon was published in
2019 but never productionised; rebuilding it on Beacon v2 + deploying on
real data closes a 7-year gap in the literature.

**Skills learned.**

- *Technical:* Illumina 450K/EPIC methylation data, β-value normalisation,
  R/Bioconductor (minfi), DP mechanisms (sparse vector technique), Django
  modelling.
- *Research:* re-implementing a privacy mechanism from a security venue
  paper, comparing utility curves to original work.

**Knowledge needed.** Statistics + comfort with continuous data (β-values
are 0–1 floats, not discrete). Strong ML/probability fundamentals.

**Difficulty.** 8/10 (hard). Combines the rigour of A2 with new biology.

**Timeline.** 5–6 months.

**Risk.** Medium. Sourcing African methylation data is non-trivial.
Mitigation: start with TCGA / GEO public data, validate, then approach
H3Africa cohorts.

---

## G3. African cancer / CNV Beacon (Progenetix-style on local data)

**Research question.** Are CNV profiles of common cancers (breast, cervical,
oesophageal) in African cohorts distinguishable from published TCGA /
Progenetix profiles? Does Beacon-style discovery accelerate cohort assembly
for African cancer studies?

**User-facing question (cancer researcher).**
"How many oesophageal squamous-cell carcinomas with 11q13 amplification are
available in African biobanks? Which African cancer studies report 8q24
gain in triple-negative breast cancer? Are there ≥ 30 African cervical
cancer samples with HPV16 integration plus 3q26 amplification I could
request?"

**Utility.** African cancer genomics is severely under-represented in
databases like Progenetix (mostly European/Asian samples). A locally hosted,
Beacon-discoverable repository is a real public good. Hangjia Zhao &
Michael Baudis (UZH) maintain Progenetix and would likely collaborate.

**Skills learned.**

- *Technical:* CNV calling and representation, ICD-O ontology, Plotly/D3
  chromosome plots, MongoDB range queries (CNVs are intervals).
- *Research:* cancer ontology mapping, somatic-vs-germline distinction
  (and why it matters for privacy), evaluating against Progenetix as gold
  standard.

**Knowledge needed.** Some cancer genomics interest — required for
motivation. Python + Django + interval/range query thinking.

**Difficulty.** 6/10 (medium). Well-bounded; lots of guidance from
Progenetix docs.

**Timeline.** 5 months.

**Risk.** Low-medium. Data access (need African cancer CNV calls) is the
main uncertainty.

---

## G4. African crop / agricultural Beacon (cassava / sorghum / teff)

**Research question.** What schema extensions does Beacon v2 require to
support germplasm metadata (MCPD passport descriptors) cleanly? Does
Beacon-style discovery improve the findability of African crop pangenome
variants relative to BLAST-and-FTP workflows?

**User-facing question (plant breeder / crop geneticist).**
"Which cassava accessions in the African pangenome carry the *MePSY1*
allele linked to provitamin-A? Are there sorghum lines in African
collections with the *Sb04g005530* drought-tolerance haplotype? Which fonio
accessions show structural variation in agronomically-relevant genes?"

**Utility.** Although AfriGen-D is human-genomics-focused, the African
agricultural genomics community (IITA, Africa Rice, ICRISAT, AOCC) has
substantial sequencing data and zero discovery infrastructure. Bridging
human and crop genomics is strategically valuable for funding. GA4GH Beacon
documentation explicitly mentions plants but no public plant Beacon exists.

**Skills learned.**

- *Technical:* plant genomics conventions, pangenome data formats (VG,
  GraphAligner outputs), MCPD passport-data standard, Django data modelling.
- *Research:* designing standard extensions, engaging with the GA4GH Plant
  data working group.

**Knowledge needed.** Plant biology / agronomy interest — strongly preferred.
Python + Django.

**Difficulty.** 6/10 (medium). Difficulty mostly in the data (plant genomes
are big and weird) not the Beacon part.

**Timeline.** 5 months.

**Risk.** Medium. ILIFU has compute capacity for a small pangenome. Risk of
scope creep into pangenome graph queries (defer to MSc).

---

## G5. Microbiome Beacon for African gut/oral microbiome cohorts

**Research question.** Can a Beacon abstraction support cross-cohort
microbiome discovery despite OTU/ASV/MAG heterogeneity? What metadata
schema enables meaningful federated microbiome queries across African
gut-microbiome cohorts?

**User-facing question (microbiome researcher).**
"Which African cohorts contain *Prevotella copri* at relative abundance
≥ 5%? Are there cohorts with both stunted children and reduced
*Bifidobacterium* abundance? Which functional pathways (e.g., bile-acid
metabolism) are observed in cohorts from rural Kenya vs urban Cape Town?"

**Utility.** H3Africa includes microbiome studies — a Beacon for "is taxon
X / function Y observed in cohort Z" would be unique globally. Microbiome
data sharing is famously chaotic; a discovery layer is sorely needed.

**Skills learned.**

- *Technical:* QIIME2 / DADA2 pipelines, taxonomy databases (SILVA, GTDB),
  functional profiling (HUMAnN, PICRUSt2), Django data modelling.
- *Research:* schema design in an unstandardised area, microbial community
  ecology, data-sharing ethics for stool samples.

**Knowledge needed.** Microbiology / ecology background — required.
Python + R bioinformatics.

**Difficulty.** 7/10 (medium-high). Schema design in an unstandardised
domain is the hard part — needs taste, not just code.

**Timeline.** 5 months.

**Risk.** Medium-high. Schema-design projects can drift; requires a hands-on
co-supervisor with microbiome experience.

---

## G6. Imaging Beacon for African medical imaging cohorts

**Research question.** Can DICOM metadata-only queries support cohort
assembly for medical-AI training without exposing pixel data? Which subset
of RadLex/SNOMED-CT findings produces the most useful Beacon discovery
vocabulary for African TB and diabetic-retinopathy cohorts?

**User-facing question (medical-AI researcher).**
"How many adult chest X-rays with confirmed pulmonary TB and HIV
co-infection are discoverable across African hospitals? Are there ≥ 1,000
retinal images with proliferative diabetic retinopathy from African
populations? Which sites have paired CT/MRI imaging for stroke patients
with neurogenetic-testing data?"

**Utility.** H3Africa and CIDRI-Africa have large TB X-ray and
diabetic-retinopathy image datasets that are not discoverable. An Imaging
Beacon would be high-impact for AI-for-Africa research. No GA4GH-compliant
Imaging Beacon exists; bridging GA4GH with federated-imaging work
(Kaapana, MONAI Federated) is novel.

**Skills learned.**

- *Technical:* DICOM / DICOMweb, medical-imaging metadata, RadLex /
  SNOMED-CT, Django.
- *Research:* the privacy boundary between metadata (safe) and pixels
  (high-risk); designing metadata-only protocols.

**Knowledge needed.** Some medical imaging exposure — strongly recommended.
Python + Django.

**Difficulty.** 7/10 (medium-high). Cross-domain — student must learn DICOM
as a sub-project.

**Timeline.** 5 months.

**Risk.** Medium. Hospital / IRB politics around imaging data. Mitigation:
start with public TB CXR datasets (Shenzhen, Montgomery) before approaching
local cohorts.

---

# Difficulty / fit summary table

| # | Project | Difficulty | Months | African novelty | Publishable? |
|---|---|:-:|:-:|:-:|---|
| A1 | Re-id attacks on African Beacon | 7/10 | 4–5 | ★★★ | Likely |
| A2 | DP noise layer | 8.5/10 | 5–6 | ★★ | Yes |
| A3 | Reconstruction-attack defense | 8/10 | 5–6 | ★★ | Yes (high impact) |
| B1 | Anomaly detection | 5.5/10 | 4 | ★ | Workshop |
| B2 | Latency benchmarking | 5/10 | 4 | ★ | Tool paper |
| C1 | Property-based fuzzer | 5/10 | 4 | ★ | Tool paper |
| D1 | Phenopackets cohort discovery | 6/10 | 5 | ★★ | Cite-able |
| D2 | PharmGKB extension | 4.5/10 | 4 | ★★ | Domain venue |
| E1 | Privacy-aware visualisation | 5.5/10 | 4 | ★ | HCI venue |
| F1 | V7 ingest benchmarking | 5.5/10 | 4 | ★ | Workshop |
| G1 | Pathogen Beacon (TB / HIV / malaria) | 7/10 | 5 | ★★★★ | Yes (high impact) |
| G2 | MBeacon for African epigenomes | 8/10 | 5–6 | ★★★ | Yes |
| G3 | African cancer / CNV Beacon | 6/10 | 5 | ★★★ | Cite-able |
| G4 | Crop / agricultural Beacon | 6/10 | 5 | ★★★★ | First-mover |
| G5 | Microbiome Beacon | 7/10 | 5 | ★★★★ | First-mover |
| G6 | Imaging Beacon (TB CXR / DR) | 7/10 | 5 | ★★★★ | First-mover |

# Cohort designs

If you can run only three students simultaneously, four sensible
combinations:

**Africa-impact cohort.** G1 (Pathogen) + G4 (Crop) + D1 (Phenopackets).
Maximum public-good impact, three under-served domains, complementary
skills.

**Privacy-research cohort.** A1 (Re-id attacks) + A3 (Reconstruction
defense) + G2 (MBeacon). A coherent privacy pipeline; A1's attack output
feeds A3.

**Infrastructure / standards cohort.** B2 (Latency) + C1 (Fuzzer) + F1
(V7 ingest). All three improve operational capacity; cleanest non-overlapping
engineering.

**Mixed showcase cohort.** G1 (Pathogen) + A1 (Re-id) + D1 (Phenopackets).
One of each kind — domain extension, privacy research, clinical utility.
Best for diverse student strengths.

# References

## Live deployments (AfriGen-D)

The Beacons students will actually query as part of their projects:

- **ARDI Beacon** — https://beacon.ardi.africa/
- **AfriGen-D Beacon** — https://beacon.afrigen-d.org/
- **African Beacon Network** (federation aggregator) — https://beacon-network-dev.afrigen-d.dev/

## Foundational papers

- Rambla et al. (2022), *Beacon v2 and Beacon networks: a "lingua franca"
  for federated data discovery in biomedical genomics, and beyond*. Hum
  Mutat 43(6): 791–799. DOI: 10.1002/humu.24369.
- Rueda et al. (2022), *Beacon v2 Reference Implementation: a toolkit to
  enable federated sharing of genomic and phenotypic data*. Bioinformatics
  38(19): 4656–4657. DOI: 10.1093/bioinformatics/btac568.
- Fiume et al. (2019), *Federated discovery and sharing of genomic data
  using Beacons*. Nat Biotechnol 37: 220–224.
- Zhao & Baudis (2025), *pgxRpi: an R/Bioconductor package for user-friendly
  access to the Beacon v2 API*. DOI: 10.1093/bioadv/vbaf172.

## Privacy attacks

- Shringarpure & Bustamante (2015), *Privacy risks from genomic data-sharing
  beacons*. Am J Hum Genet 97(5): 631–646.
- Raisaro et al. (2017), *Addressing Beacon re-identification attacks*.
  J Am Med Inform Assoc 24(4): 799–805. DOI: 10.1093/jamia/ocw167.
- Aziz et al. (2017), *Aftermath of Bustamante attack on genomic Beacon
  service*. BMC Med Genomics 10: 43. DOI: 10.1186/s12920-017-0278-x.
- von Thenen, Ayday, Cicek (2019), *Re-identification of individuals in
  genomic data-sharing beacons via allele inference*. Bioinformatics 35(3):
  365–371. DOI: 10.1093/bioinformatics/bty643.
- Bu, Wang, Tang (2018), *Real-time protection of genomic data sharing in
  Beacon services*. AMIA Jt Summits Transl Sci Proc 2017: 45–54.
- Yilmaz et al. (2025), *Beacon Reconstruction Attack: reconstruction of
  genomes in genomic data-sharing beacons using summary statistics*.
  Bioinformatics 41(6): btaf273.

## Beacon variants

- Hagestedt et al. (2019), *MBeacon: privacy-preserving beacons for DNA
  methylation data*. NDSS Symposium 2019.
- Huang et al. (2025), *Privacy-preserving framework for genomic
  computations via multi-key homomorphic encryption*. Bioinformatics 41(3):
  btae754.
- Pheno-Ranker (Bauer-Mehren et al. 2024), BMC Bioinformatics. DOI:
  10.1186/s12859-024-05993-2.

## Web resources

- GA4GH Beacon: https://www.ga4gh.org/product/beacon-api/
- Beacon Project: https://genomebeacons.org/
- Beacon docs: https://docs.genomebeacons.org/
- Beacon spec: https://github.com/ga4gh-beacon/specification
- Twelve quick tips for deploying a Beacon (2024):
  https://genomebeacons.org/publications/2024-03-01-Beacon-Tips/
- Progenetix (cancer/CNV Beacon): https://docs.progenetix.org/
- Viral Beacon: https://inb-elixir.es/news/viral-beacon-beacon-ocean-sars-cov-2-data
- AfriGen-D: https://afrigen-d.org/
- AGMP: https://agmp.afrigen-d.org/
