# Lemmata: Market-Entry, Competitive and Originality Brief
*A pre-submission integrity checker for ML/AI paper authors. Screening date: November 3, 2026. Not legal advice.*

Lemmata is not a copy of any one product. But none of its five checks is new on its own, and the product closest to it already sells the same bundle: Reviewer3 runs reference checks, claim review and code replication for $19 per paper. Lemmata will only stand out on how it works and where it starts. It should run locally, read LaTeX source natively, and attach line-located evidence to every finding. It should lead with main-text-vs-appendix and notation consistency, which almost no one targets, and treat citation-existence checking as a free hook rather than the product.

## TL;DR
- **Originality:** About a dozen tools overlap with Lemmata, and at least five are open-source Claude Code plugins or skills. The overlap is in components, not the overall concept. The idea is not being copied, but Lemmata must not present "citation verification" as novel. No conflicting patent turned up, though Thomson Reuters-origin reference-validation patents need a lawyer's check. "Lemmata" has name-collision risk from existing AI/software companies, Notara is effectively taken in AI software, and SourceLedger is crowded on GitHub and PyPI.
- **Market:** Demand from ML authors is real and policy-driven. ICLR 2026 received 19,525 submissions and ICML 2026 had 23,918 papers enter review. ICLR, ICML and NeurIPS treat hallucinated references as grounds for desk rejection, and arXiv now imposes one-year bans. Paid author-side spend is small, though: my estimate puts the serviceable market at roughly $10–20M a year. Lemmata is a strong course and portfolio project and a credible acquisition-style startup. It is not yet a venture-scale standalone business.
- **Strategy:** Build an open-source, local-first "integrity CI for LaTeX papers" tool. Target Korean ML labs first and global ML authors through GitHub, with a public arXiv report gallery as the growth engine. Make money from lab and institutional seats and conference or workshop partnerships, not per-paper consumer sales. Time the launch to the next major ML deadline cycle.

## Key Findings

### 1. The "why now" is well documented
- **Volume:** ICLR 2026 received 19,525 valid submissions and produced 76,139 reviews from 18,054 reviewers. It accepted 5,355 papers (27.4%). For ICML 2026, 23,918 submissions entered review, about double the previous year, and 6,352 were accepted (26.6%). The opening remarks cited 24,661 submissions from 76,159 authors. NeurIPS 2025's main track received 21,575 valid submissions, up from 9,467 in 2020, and accepted 5,290 (24.52%).
- **Hallucinated citations reach the published record:** GPTZero scanned 4,841 of 5,290 accepted NeurIPS 2025 papers and confirmed 100 hallucinated citations. Its own report gives two paper counts: the text says "spanning over 51 NeurIPS papers", while its table is titled "Across 53 NeurIPS Papers". The independent arXiv analysis 2602.05930 uses 53. This came after GPTZero earlier found 50+ in ICLR 2026 submissions. An independent 2026 arXiv study, "Phantom References", estimates the share of accepted papers with at least one likely hallucinated reference:
  - ICLR 2025: 18.7%
  - ICML 2025: 23.3%
  - NeurIPS 2025: 26.2%
  - USENIX Security 2025: 34.9%

  Under a stricter threshold of at least two such references, the shares are 2.5%, 4.4%, 6.9% and 12.1%.
- **Penalties are now concrete:**
  - ICLR 2026 desk-rejected every paper with confirmed hallucinated references.
  - ICLR built its own automated reference checker. In "A Retrospective on the ICLR 2026 Review Process" (March 31, 2026), it says the checker "had a significant false positive rate". For example, it "would flag a reference to a paper with a non-English title that a submission's authors had translated to English". As a result, each flagged paper was reviewed by at least three humans.
  - ICML 2026 lists hallucinated references among its desk-reject grounds.
  - On May 14, 2026, arXiv's CS section chair Thomas Dietterich announced on X a one-strike rule for "incontrovertible evidence" of unchecked LLM output. Per TechCrunch (May 16), the penalty is "a 1-year ban from arXiv followed by the requirement that subsequent arXiv submissions must first be accepted by a reputable peer-reviewed venue". Section chairs confirm cases, and authors can appeal.
- **The hidden insight:** Conferences and arXiv already run, or can cheaply run, citation-existence checks themselves. Authors therefore need a tool that catches problems before the venue's checker does, with few false positives. That is a precision problem, and it favors Lemmata's evidence-linked design.

### 2. The biggest competitive threat is free and conference-endorsed
Google's Paper Assistant Tool (PAT) was offered free to authors at STOC and ICML 2026, and more than 4,700 submissions were reviewed across both venues. In ICML's retrospective:
- 35.4% of authors of theory papers said it found significant gaps that took more than an hour to fix.
- 31% of authors of experimental papers ran new experiments because of it.
- 87.3% said it improved clarity.

NeurIPS 2026 then adopted PAT, giving each eligible author one voucher for one paper. PAT targets deep reasoning and methodology. It does not target bibliographic or consistency hygiene, but it occupies the "pre-submission AI check for ML authors" slot with the venue's endorsement and at zero price.

### 3. Exits and funding in this space are modest
- **GPTZero:** raised $13.5M in total ($3.5M seed in May 2023 co-led by Uncork and Neo; $10M Series A in June 2024 led by Footwork). Superhuman (formerly Grammarly) announced its acquisition on June 23, 2026. Business Insider-sourced reports put GPTZero at "more than 19 million registered users and $30 million in annual recurring revenue". All 30 employees joined Superhuman. PitchBook valued it above $88M; the price was undisclosed.
- **scite:** Research Solutions acquired it in 2023, adding about 21,000 B2C subscribers and $3.6M of annualized subscription revenue. Research Solutions' SEC Exhibit 99.2 (November 27, 2023) gives an "enterprise value at close [of] $14.8M (approximately 4.11x…)", paid roughly half in cash and half in stock. An earnout is added, equal to ending ARR at 18 months × 3.5 minus $14.8M. MarketScreener puts total consideration including the earnout's fair value at about $20.9M; that figure is not in the SEC exhibit.
- **Pangram:** raised $3.98M in total, per Business Wire (June 24, 2025): a $1.25M pre-seed led by Haystack VC plus "more than $2.7 million" in a seed round led by ScOp, with Script Capital and Cadenza. It then raised $9M in July 2026 led by Menlo Ventures.
- **Signals:** raised a $1.1M seed backed by ACS Publications and Enago.
- **Reviewer3:** founded in 2025; raised an early-stage round in March 2026 from E14 Fund and Earthling VC (amount undisclosed).

**So what:** Research-integrity tooling attracts seed money and strategic acquirers. Publishers, writing-tool platforms and research-workflow companies are the natural buyers. The realistic outcome for a solo-founder Lemmata is a $1–5M ARR niche business or an acqui-hire, not a unicorn.

## 1. Competitive Landscape

### 1a. Competitor profiles (verified in this screen unless marked)

| Player | What it does | Target customer | Model / price | Funding / ownership | Founded / HQ | Closeness to Lemmata |
|---|---|---|---|---|---|---|
| **Reviewer3** | Multi-agent AI review with five named checks: Submission Screening, Reference Check, Fatal Flaws, Claim Review, Code Replication. Cross-checks citations against five reference databases and validates code in a sandbox | Authors, reviewers, journals, institutions | $19 one-time review; $29/month unlimited; Teams by quote | Early-stage VC (E14 Fund, Earthling VC), March 2026 | 2025; San Diego and Israel | **Highest (commercial).** Covers checks 1 and 4 plus the code-audit roadmap. Hosted, not local |
| **GPTZero Hallucination Check** (Superhuman) | Flags citations it cannot verify via Google Scholar, PubMed, arXiv, Crossref and DOI/URL checks. Ran the NeurIPS/ICLR scans and worked with ICLR on screening | Educators, authors, reviewers, publishers | Freemium SaaS | Acquired June 2026 (see above) | 2023; Princeton/Toronto roots | High on check 1 only; strongest brand |
| **Google PAT** | Agentic pre-submission feedback on theoretical, logical and empirical flaws | Authors via conference partnerships (STOC, ICML 2026, NeurIPS 2026) | Free (one voucher per author) | Google Research | 2025 | Medium. Overlaps on correctness and consistency; free and endorsed |
| **Refine.ink** | Deep critique of internal logic, notation, internal references, math and proofs. Third-party reviews say its FAQ excludes citation and bibliography management | Theory-heavy STEM and economics authors | $49.99/review; $119.99 for 3; $299.99 for 10; Pro $100/month for 3; first document free | Not found | Oct 2025 (Ben Golub, Yann Calvó López) | Medium-high on checks 2 and 3 |
| **Stanford Agentic Reviewer (paperreview.ai)** | Free AI review grounded in related arXiv work. Analyzes only the first 15 pages of a PDF up to 10 MB. AI–human Spearman correlation 0.42, versus 0.41 between two humans | ML authors | Free | Stanford ML Group (Yixing Jiang, Andrew Ng) | Nov 2025 | Medium on check 5 (related work); PDF-only |
| **Pangram** | AI-generated text detection. Its ICLR 2026 analysis estimated that 21% of reviews were AI-generated | Education, media, enterprises, conferences | SaaS/API | ~$13M total (ScOp, Haystack, Menlo) | 2023; NYC | Low (different job) |
| **scite** (Research Solutions) | "Smart Citations" index (over 1B) classifying how papers are cited; AI assistant | Researchers, institutions, corporates | Subscription | Acquired 2023 | Brooklyn | Medium on check 4 (citation support), but discovery-oriented |
| **Clear Skies** (Papermill Alarm, Oversight) | Paper-mill risk scoring combining LLMs and network analysis | Publishers; integrated into STM Integrity Hub, Frontiers AIRA, KGL Smart Review and eWorkflow | B2B API/licence | Not found | 2022; London | Low (publisher-side fraud) |
| **Signals** | Research evaluation and integrity data graph | Publishers, institutions | B2B | $1.1M seed (ACS Publications, Enago) | n/a | Low |
| **Cactus / Paperpal (incl. Preflight)** | Writing assistant; Preflight submission checks integrated into Frontiers' AIRA | Authors, publishers | Paperpal around $25/month (third-party) | Cactus Communications (private) | India | Low-medium |
| **Manusights, PeerReviewAI, q.e.d Science, thesify, Enago AI Peer Review Lite** | Pre-submission AI manuscript review, mostly biomedical. Some check citations against Crossref, PubMed and OpenAlex | Authors (life sciences) | $39; $49; free; €14.95; $99 | Not verified | Various | Medium on check 1; wrong field focus |

**Not verified in this screen** (feature descriptions are from general knowledge; check before citing in the pitch): Proofig and Imagetwin (image integrity, publisher-side), Morressier (Berlin; conference and publishing workflow), Writefull (Digital Science; academic language), Grammarly/Superhuman and Trinka (writing), Elicit, Consensus, SciSpace, Undermind, NotebookLM, and the OpenAI, Google and Anthropic deep-research tools (literature search and synthesis, relevant to check 5 only), alphaXiv (arXiv discussion layer), YesNoError and the Black Spatula Project (community or AI error-hunting in published papers), CodeOcean and Papers with Code successors (reproducibility), and STM Integrity Hub, Crossref, Clarivate, Elsevier and Springer Nature integrity tooling (publisher-side).

### 1b. The open-source layer (Lemmata's real originality problem)
These tools are free and several share Lemmata's exact delivery model:
- **RefChecker** (Mark Russinovich): validates references from arXiv IDs, PDFs, LaTeX, BibTeX and plain text against Semantic Scholar, OpenAlex, Crossref, DBLP and ACL Anthology. It adds LLM hallucination assessment, auto-generated corrected BibTeX and a web UI. It is the pipeline behind the "Phantom References" study.
- **Bib Check Agent:** an open-source Agent Skill for Claude Code, Codex, Copilot, Gemini CLI and others. It checks every .bib entry against Semantic Scholar, DBLP, Crossref, OpenAlex and arXiv, and targets "hallucinated, wrong, or unsupported" citations.
- **citation-check** (Claude Code skill): fetches cited papers and labels each citation SUPPORTED, PARTLY SUPPORTED, NOT SUPPORTED or UNVERIFIABLE, with a quote and page number. It writes fixes as a LaTeX diff. **This is Lemmata check 4.**
- **academic-writing-agents** (Claude Code plugin): includes a consistency-checker covering terminology, cross-references and figure–text–caption alignment, and a technical reviewer covering math notation. It has a "Prepare this paper for NeurIPS submission" pipeline. **This partly covers checks 2 and 3.**
- **co-researcher** (Claude Code plugin): literature and PRISMA systematic reviews with citations verified against OpenAlex, arXiv and Europe PMC. **This partly covers check 5.**
- **claude-scholar** (check-refs, latex-cleanup), the **harcx** MCP server, **halref** (Jurgens; ACL style), a **BibTeX Checker** Chrome extension (MIT) and **BibTeX Verifier** (MIT, browser-based).
- **Academic prototypes:** RefVerifier (2026) and SemanticCite (2025) verify citation claims against cited full texts. Citation-Integrity provides a benchmark corpus.

### 1c. Feature-overlap matrix vs. Lemmata
● = core feature; ◐ = partial or adjacent; ○ = absent or not advertised. Based on public documentation, not hands-on testing.

| Tool | (1) Refs exist / metadata | (2) Main vs. appendix | (3) Notation | (4) Citation supports claim | (5) Related-work coverage, logged search | Code-vs-paper | LaTeX-native | Delivery |
|---|---|---|---|---|---|---|---|---|
| **Lemmata (planned)** | ● | ● | ● | ● | ● | ◐ (later) | ● | Local, open source (Claude Code); hosted later |
| Reviewer3 | ● | ◐ | ○ | ● | ○ | ● | ○ | Hosted SaaS |
| GPTZero Hallucination Check | ● | ○ | ○ | ◐ | ○ | ○ | ○ | Hosted SaaS |
| Google PAT | ○ | ◐ | ◐ | ○ | ◐ | ○ | ○ | Hosted, via conferences |
| Refine.ink | ○ | ● | ● | ○ | ○ | ○ | ◐ | Hosted SaaS |
| Stanford Agentic Reviewer | ○ | ○ | ○ | ○ | ● (not logged as a protocol) | ○ | ○ | Hosted, free |
| RefChecker | ● | ○ | ○ | ○ | ◐ (suggest missing) | ○ | ● | Open source, local or hosted |
| Bib Check Agent | ● | ○ | ○ | ◐ | ○ | ○ | ● | Open-source agent skill |
| citation-check skill | ◐ | ○ | ○ | ● | ○ | ○ | ● | Open-source Claude Code skill |
| academic-writing-agents | ◐ | ● | ● | ○ | ◐ | ○ | ● | Open-source Claude Code plugin |
| co-researcher | ● | ○ | ○ | ● | ● | ○ | ○ | Open-source plugin |
| scite | ○ | ○ | ○ | ◐ | ◐ | ○ | ○ | Hosted SaaS |
| Manusights / PeerReviewAI | ● | ○ | ○ | ◐ | ◐ | ○ | ○ | Hosted SaaS |

**Reading the matrix:**
- No single tool combines all five checks with a local, LaTeX-native, evidence-linked report.
- The combination is defensible only weakly, because an author could chain three free plugins to get about 70% of the way.
- The genuinely thin columns are (2) main-text-vs-appendix numeric and settings consistency, and (3) notation, both done deterministically with exact source locations.

## 2. Market Sizing
Figures are labelled **[F] fact (sourced)** or **[E] estimate (my assumption)**.

| Layer | Assumptions | Size |
|---|---|---|
| Researchers worldwide | [F] 8.854M full-time-equivalent researchers in 2018 (UNESCO Science Report 2021). [E] About 11.9M in 2023, derived from UNESCO's 1,486 researchers per million inhabitants × ~8.0B people | Context |
| Manuscript flow, arXiv | [F] 244,031 new arXiv submissions in 2024, including 111,026 primary CS articles plus 14,575 cross-lists (about 45–51% CS). [F, third-party, unconfirmed] 284,486 in 2025 | — |
| ML venue flow | [F] ICLR 2026: 19,525; ICML 2026: ~24.7K total (23,918 reviewed); NeurIPS 2025: 21,575. [E] Including CVPR, ACL/ARR, AAAI, EMNLP, KDD and others, ~150–200K ML/AI submissions a year, many of them resubmissions | — |
| **TAM**: author-side pre-submission integrity checking, all research fields | [E] ~3–4M manuscripts/year × 1.5 submission attempts × $25 blended price | **~$110–150M/yr** |
| + publisher/institution integrity spend | [E] Not reliably quantified in public sources. Treat as upside: a different buyer, with incumbents such as Clear Skies, the STM Integrity Hub and Cactus already embedded | Unquantified |
| **SAM**: LaTeX-based quantitative fields (CS, ML, math, physics, statistics, economics) | [E] ~250–300K LaTeX manuscripts/year (arXiv as proxy) × 1.5 × $25 ≈ $9–11M. Alternatively ~30–50K active ML/quantitative labs × $300/year ≈ $9–15M | **~$10–20M/yr** |
| **SOM** (3 years, solo founder) | [E] 1–3% of SAM through open-source conversion and lab seats | **~$0.1–0.5M ARR** |

**So what:** The author-pays market is real but small. GPTZero reached $30M ARR only by serving education and enterprise horizontally. Lemmata's upside therefore depends on (a) institutional or library licences, (b) conference partnerships modelled on PAT, or (c) expanding beyond ML into other LaTeX fields. The course pitch should present the SOM honestly and argue from timing and wedge, not market size.

## 3. Customers and Buyers

| Buyer | Pain / trigger | Budget line | Purchase process | Willingness-to-pay evidence |
|---|---|---|---|---|
| Individual ML author (PhD student, postdoc) | Fear of desk rejection or an arXiv ban; appendix drift before the deadline | Personal card or the lab's cloud/LLM budget | Instant, self-serve | Reviewer3 $19, Refine $29.99–49.99 and Manusights $39 per paper suggest $20–50 per paper. Free alternatives (PAT, Stanford, OSS) cap this |
| Lab / PI | Reputation risk: one bad paper hurts every co-author | Grant overhead, software or compute line | PI decides; card or purchase order under about $1–2K | [E] $200–600/lab/year is plausible; Reviewer3 and Refine both offer team/pro tiers |
| University library / research office | Institutional integrity, training obligations | Library e-resources or research-integrity office | Procurement, security review, 3–9 months | scite's institutional base and Refine's "institutional subscriptions" show the category exists |
| Conference / workshop | Reviewer load; desk-reject burden; ICLR's false-positive problem | Sponsorship or in-kind | Program chairs; partnership, not purchase | PAT shows conferences will distribute author tools; the price is $0 to the venue |
| Publisher | Paper mills, retractions | Integrity budget | Enterprise sales, 6–18 months | Integrations by Clear Skies, Cactus and Frontiers; ACS invested in Signals |

**Benchmark takeaway:** Per-paper pricing in this space sits between $15 and $50, with $19 as the floor set by Reviewer3. Subscriptions run $25–100/month. Free conference-provided tools set the reference price for many ML authors at zero, which favors an open-source-plus-institutional model.

## 4. Industry Dynamics

### Porter's five forces
| Force | Rating | Rationale |
|---|---|---|
| Rivalry | **High** | 20+ AI review tools; many free open-source citation checkers; well-funded generalists |
| Threat of new entrants | **Very high** | A Claude Code skill can be written in a weekend; frontier models commoditize the core reasoning |
| Substitutes | **High** | Free Google PAT via venues; general deep-research agents; venue-run reference checks; co-authors |
| Buyer power | **High** for individuals (zero switching cost); **medium** for institutions | — |
| Supplier power | **Medium-high** | Dependence on Anthropic (plan, terms, pricing) and on scholarly metadata APIs (rate limits, terms) |

### Trends
- **Policy hardening:**
  - ICLR desk rejections for hallucinated references.
  - ICML 2026 desk-reject grounds that include hallucinated references.
  - The arXiv one-year ban (May 2026).
  - AAAI-26 ran an AI review pilot.
  - ICML 2026 ran a randomized dual-policy experiment on LLM use in review.
- **Conferences as distribution:** the PAT model (STOC → ICML → NeurIPS) shows that venues will push a vetted author tool to every submitter.
- **Consolidation:** Superhuman/GPTZero (2026) and Research Solutions/scite (2023). Writing-platform and research-workflow companies are buying integrity features.
- **Incumbent threat:**
  - **Google** (PAT) and **Superhuman/GPTZero** (citation checking inside a writing layer with 40M daily users, per Superhuman) are the most credible.
  - **Overleaf** (Digital Science) is the most dangerous potential entrant for LaTeX-native checks, because it already holds the source files. I did not verify any announced Overleaf integrity feature.
  - Frontier labs could ship equivalent "paper audit" skills at any time.

## 5. White Space and Positioning

**Where Lemmata can win:**
1. **Precision over recall, with evidence.** Venues already flag candidate hallucinations, and ICLR admits significant false positives. Authors want each issue located to file and line, with the source evidence attached, so they can fix it in minutes. Lemmata's evidence-linked findings fit this need.
2. **Internal consistency of LaTeX source.** Main text vs. appendix numbers, hyperparameters, theorem restatements, broken or mismatched cross-references, and notation drift. Most commercial tools are PDF-first and do not do this deterministically.
3. **Privacy by architecture.** Local execution on the author's own Claude plan means the manuscript never leaves the machine. Hosted competitors can only offer policy-level assurances; Reviewer3, for example, cites its cloud providers' SOC 2 certifications rather than its own.
4. **A public benchmark gallery.** A reproducible gallery of reports on public arXiv papers, with precision measured against labelled sets such as GPTZero's 100 NeurIPS cases and the Phantom References data, builds credibility as GPTZero's NeurIPS scan did.

**Recommended wedge:** "`lemmata check` before you hit submit". This is a one-command, open-source Claude Code plugin for LaTeX ML papers. Make checks 2 and 3 the hero features, bundle check 1 as table stakes, and keep check 4 in beta with explicit confidence labels.

**Beachhead:** Korean ML graduate labs (Korea University first, then KAIST, SNU, POSTECH and Yonsei), entered through ML conference deadline cycles. Korea-first is a distribution tactic, not a market. The product is English-language and global from day one, and the GitHub launch is global.

**GTM playbook drawn from comparables:**
- **GPTZero:** a viral public scan of a famous venue (NeurIPS) earned press, followed by a venue partnership with ICLR. Replicate this with a careful, non-accusatory gallery.
- **PAT:** conference endorsement. Pitch workshop chairs, or Korean venues such as the KCC/KSC and KDD Korea tracks, on a free pilot with a published retrospective.
- **Refine:** founder-led social proof from named academics, plus credit packs and seasonal discounts.

## 6. Business Model and Unit Economics

| Option | Fit for a solo founder | Notes |
|---|---|---|
| **Open-source core (bring your own Claude plan)** | ★★★★★ | Near-zero marginal cost; builds adoption and trust; no revenue on its own |
| Hosted API-key version, per paper ($15–25) or subscription ($15–29/month) | ★★★ | [E] At a token cost of ~$2–6 per full run (≈0.5–2M tokens, mostly cited-paper text), gross margin is ~70–85% at $19–25. Refine reports that its frontier-model runs come close to losing money, so model-cost discipline matters |
| **Lab/team seats ($300–600/lab/year)** | ★★★★ | Best near-term revenue; PI purchase under card limits |
| Institutional/library licence | ★★ | Long procurement and security reviews; pursue after there are reference labs |
| B2B to conferences and publishers | ★★ | High credibility but slow; conferences expect free; publishers already have Clear Skies, the STM Integrity Hub and Cactus |

**Key risks:**
1. Platform risk: Claude Code terms, pricing and plan limits.
2. Commoditization by free open-source tools and PAT.
3. False-positive harm. Publicly flagging named authors risks reputational damage and legal claims, so gallery reports need careful wording and an appeal path.
4. Limited bandwidth as a solo founder.
5. Metadata API rate limits and terms.

## 7. Originality / Freedom-to-Operate Screen (Not Legal Advice)

### 7a. Am I copying someone?
- **No single product is substantially the same as the full Lemmata concept.** The closest commercial analogue is Reviewer3, with reference checks, claim review and code replication, but it is hosted, PDF/manuscript-based and not LaTeX-local. The closest delivery-model analogues are the Claude Code plugins and skills Bib Check Agent, citation-check, academic-writing-agents and co-researcher.
- **Each individual check has clear prior art.** Ideas and functional features are generally not protected by copyright; code is. What to do:
  1. Do not copy code from these repositories unless their licences allow it, and comply with those licences (attribution, notice files).
  2. Acknowledge the prior art in the pitch and README. Investors and reviewers will find it anyway.
  3. Claim originality only for the integration: LaTeX-located evidence, consistency checks, the per-paper LLM-wiki, logged related-work search and the public benchmark.

### 7b. Patents found (screening only)
| Patent | Owner (origin) | Relevance | Note |
|---|---|---|---|
| US8201085B2 (from US20080320579A1), "Method and system for validating references" | Thomson Reuters origin (now likely Clarivate) | **Medium-high for check 1**: automatically validates cited references against an authority database | Priority ~2007. The 20-year term may run until about 2027–2028 unless maintenance fees lapsed. **Lawyer to confirm status** |
| US8676780B2 / US20120072422A1 / EP2583204A2, citation processing and reference validation | Thomson Reuters origin | **Medium-high for check 1**: extracts embedded metadata and compares it to an authority database | Priority ~2010–2011, so possibly in force until about 2030–2031. **Lawyer to confirm claims, status and family** |
| US20120324349A1 (validated citations) | Thomson Reuters origin | Medium | Application status unverified |
| US12353469B1, "Verification and citation for language model outputs" | Amazon Technologies | Low: RAG answers over the user's own documents with SQL numeric verification (finance domain) | Different claimed method |

I found no patents on checking a paper against its code or on manuscript main-text-vs-appendix consistency. That search was not exhaustive, and KIPO and EPO were not searched directly.

### 7c. Name screening
| Name | Findings | Risk |
|---|---|---|
| **Lemmata** | "LEMMATA SAVINGS BANK" (USPTO serial 97552809, class 36 banking, California Bank of Commerce; registered April 2024 per Trademarkelite; a second filing, 97552850). Lemmata, Inc. (Palo Alto, 2023, AI analytics platform, lemmata.co). LEMMATA LIMITED (London, AI business-intelligence software). A Berkeley "Lemmata" (2021, AI language services, listed as out of business). No USPTO class 9/42 filing for plain "LEMMATA" found | **Medium.** Different services, but the same AI/software space risks common-law and passing-off conflicts and confusion in search results. The .co domain is taken |
| **Notara** | notara.ai, a live "company AI operating system" that works with Claude, Codex and Cursor over MCP (direct overlap in AI software). Notara Inc. (NYC, 1996, marketing software; M&A per PitchBook). notara.ee (Estonian AI vision) | **High: avoid** |
| **SourceLedger** | No trademark filing found, but at least five GitHub/PyPI projects use the name, including a research-provenance package and a "verifiable RAG with validated citations" runtime | **Medium-high:** namespace clash, weak distinctiveness |

**Recommendation:** Keep "Lemmata" as the course codename only. Before any public launch, choose a coined, distinctive name and clear it properly.

### 7d. Open-source licence and data-terms considerations (to verify)
- **PDF fallback:** PyMuPDF is AGPL-licensed (a copyleft licence that also covers network use). Prefer permissive or Apache-licensed alternatives (e.g., pypdf, pdfminer.six, GROBID under Apache-2.0) if a hosted version is planned.
- **Metadata sources:** OpenAlex and DBLP data are openly licensed. Crossref metadata is largely open, but polite-pool and etiquette rules apply. The arXiv API and Semantic Scholar API have their own terms, including rate limits and possible commercial-use conditions. Read them before running a hosted service.
- **arXiv papers in the gallery:** Many arXiv papers carry only arXiv's non-exclusive distribution licence. Link to papers rather than re-hosting PDFs, quote minimally, and consider limiting the gallery to CC-BY papers or adding an author opt-out.
- **Claude Code plugin:** Check Anthropic's terms for distributing plugins and for any future hosted or commercial API use.
- **Your own licence:** Apache-2.0 gives patent-grant protection. AGPL would deter hosted clones but slow institutional adoption.

### 7e. Checklist for a lawyer (Korea plus US)
1. Legal status, claims and remaining term of US8201085B2, US8676780B2 and their EP/KR family members, and a freedom-to-operate opinion for check 1.
2. Full knock-out searches in USPTO TESS/TSDR, EUIPO eSearch, WIPO Global Brand Database and KIPRIS (classes 9, 42 and possibly 41) for the final name.
3. Licence compatibility of every dependency, and of any code borrowed from the open-source tools above.
4. Defamation and reputational risk of publishing reports that name authors' errors (Korean criminal defamation law is stricter than US law). Use wording such as "unverified" or "could not be matched", not "fabricated".
5. Copyright in quoting arXiv papers, and the terms of service of the metadata APIs.
6. University IP policy at Korea University for work built in a graduate course, including who owns the code.
7. Privacy-claim substantiation, so that "manuscripts never leave your machine" is accurate given the calls Claude Code makes to Anthropic's API.

## 8. Recommendations

### Executive so-what
1. Reposition from "AI integrity checker" (crowded) to **"integrity CI for LaTeX papers: every finding has a line number and evidence"**.
2. Lead with consistency checks 2 and 3 and treat citation existence (check 1) as a free hook. Measure and publish precision.
3. Distribute as open source plus a gallery. Monetize lab seats first and pursue conference partnerships second.
4. Fix the name before going public.

### 90-day plan (aligned to course presentations 2 and 3; adjust to actual course dates)
| Window | Build | Validate | Course deliverable |
|---|---|---|---|
| Days 1–30 (→ presentation 2) | v0.1 plugin: LaTeX parser with source locations; checks 1, 2 and 3; HTML report | Labelled evaluation set: GPTZero's NeurIPS 100 plus 30 self-annotated appendix-inconsistency cases; report precision and recall. 10 user interviews with Korea University ML students | Problem definition, competitor matrix (this report), demo on 10 public arXiv papers, early precision numbers |
| Days 31–60 | Check 4 (beta, confidence-labelled); per-paper LLM-wiki; public gallery of ~50 CC-BY arXiv ML papers | 3–5 design-partner labs in Korea; track issues found and fixed per paper | Iterate on the name; legal checklist sent to the university tech-transfer or IP office |
| Days 61–90 (→ presentation 3 / IR pitch) | Check 5 with a logged, reproducible search protocol; packaging; launch on GitHub and Hacker News, timed to the next ML deadline (the ICML 2027 deadline is typically late January; confirm) | Stars and installs, weekly active papers, % of findings accepted by authors, 1 workshop or venue pilot conversation | IR pitch with traction metrics, honest SOM, business model, risks |

### Investor-pitch talking points
- **Why now:**
  - Submissions have doubled: NeurIPS went from 9,467 in 2020 to 21,575 in 2025, and ICML 2026 roughly doubled to 23,918.
  - Venues now desk-reject for hallucinated references, and arXiv bans for a year.
  - Venues' own checkers produce false positives, so authors need to pre-clear.
  - Agentic coding tools now let a local tool read a whole LaTeX project.
- **Why this approach:** local-first privacy, LaTeX-native line-level evidence, and deterministic consistency checks that a large language model alone does not reliably do. Precision will be shown on public benchmarks.
- **Why this team:** the founder is the user (an ML graduate researcher), with information-extraction and text-mining expertise aligned with the course. The one-person team is the weakness. Address it with open-source contributors, design-partner labs and an advisor from a research-integrity or conference-chair background.
- **Comparables:** GPTZero ($30M ARR, acquired by Superhuman), scite (acquired at $14.8M enterprise value at close plus an ARR-based earnout, per Research Solutions' SEC Exhibit 99.2), Pangram ($9M raise in 2026) and Reviewer3 (VC-backed in 2026) show strategic-buyer appetite.

## Caveats
- Several figures are vendor-reported or come from third-party review sites rather than primary sources. These include Reviewer3's paper count and satisfaction rate, Refine's and Reviewer3's prices (taken from a competitor's blog), and the 2025 arXiv totals. GPTZero's "more than 19 million registered users and $30 million in annual recurring revenue" is from reports citing Business Insider on the June 23, 2026 Superhuman deal, not a company filing. Re-check these on primary pages before the IR pitch.
- Reports differ on the GPTZero NeurIPS count: GPTZero's own report says "over 51" papers in its text and 53 in its table title. They also differ on the ICML 2026 accepted count (6,352 vs. 6,552; the 26.6% rate matches 6,352).
- TAM, SAM and SOM are my estimates with stated assumptions. Public data on publisher integrity spend was not found.
- Competitor rows marked "not verified" and the Overleaf threat come from general knowledge, not this screen's research.
- The trademark and patent screen used web-accessible databases and aggregators, not direct KIPRIS, EUIPO or USPTO TSDR queries. It is a screening, not a clearance or a freedom-to-operate opinion.