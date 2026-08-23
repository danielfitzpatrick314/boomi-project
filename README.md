# Recall Investigator

An agent that takes a single FDA drug recall and answers the question that actually matters to
a quality/regulatory manager: not just "is this recall a big deal," but **what else should I be
watching because of it** — which other marketed drugs share this manufacturer or this active
ingredient, and are therefore exposed to the same underlying risk. Every claim, on the recall
and on the downstream products it flags, is traced to a specific recall number, NDC record, or
event count the manager can independently check.

## Who this is for

A quality or regulatory manager at a distributor or hospital pharmacy who gets flagged on a
drug recall and has to decide how urgently to act — and, just as often, gets asked "does this
affect anything else we stock?" and currently has no fast way to answer that beyond manual
cross-referencing. Today the first question means manually pulling the firm's recall history
off the FDA site; the second question mostly doesn't get asked at all, because there's no
practical way to answer it by hand. This tool automates the first pass on both and shows its
work.

## What it does

Given a recall number (or a firm name), the agent:
1. Pulls the recall's full detail.
2. Checks the firm's complete recall history for repetition and related root causes.
3. **Cross-references the recalled product against the FDA's directory of currently-marketed
   drugs** to surface other products worth flagging: other drugs from the same manufacturer
   (shared facility/QC risk), and other drugs — from any manufacturer — that share the recalled
   product's active ingredient (shared raw-material supply chain, or a class-wide issue). This
   is the actual point of the tool, not a side effect of investigating one recall — see "Why
   this needed to be agentic" below.
4. Tries to link the specific recalled product to FAERS adverse-event reports, using the most
   precise matching method available (NDC → generic name → brand name → manufacturer name),
   and is explicit about how much to trust whichever method actually worked.
5. Returns a case brief: a verdict (`isolated | watch | systemic | insufficient_data`), a
   deterministic **severity gauge** (Low/Moderate/High/Critical — computed from the recall's own
   FDA classification combined with the verdict, not model-generated, so it can't drift from
   what's actually known), a single **recommended action** — the one line a busy manager reads
   if they read nothing else — a **related-products list**, plain-language supporting findings,
   and the couple of limitations that would actually change the call. The step-by-step trace
   (which tools ran, what each returned, and why) renders right underneath, expanded by default —
   the case brief is always what's on top, but the full unfolding chain is visible below it for
   anyone watching along, not hidden behind a click. A **copy-report** button exports the whole
   finding as Markdown for pasting into Slack, email, or a ticket.

The output is written so nothing in it requires knowing this is an AI agent: no tool names, no
internal field names, no hedge-everything academic tone. The system prompt explicitly forbids
citing things like `find_related_adverse_events` or `manufacturer_name` in the final report —
those are implementation details for the trace, not something a quality manager should have to
parse. What they get instead is a real recall snapshot (firm, drug name, classification, date —
pulled directly from the recall record, not reconstructed from the model's prose, so it's never
at the mercy of the LLM mistranscribing a firm name) plus a case brief written the way a person
would write their own case notes.

**Chasing a lead without leaving the tool.** Two follow-up actions off a finished finding, both
deliberately *not* a straight-to-investigation shortcut, because either a firm or a product name
can match more than one real recall:
- Each related product has a **"check this product's recall history"** button — searches
  openFDA by that specific product name, across any manufacturer, since a related product is
  flagged only for sharing a manufacturer or ingredient with something recalled, not because it
  has history of its own. Confirms or clears that signal instead of just re-searching the whole
  firm.
- The **Firm** search tab lists every recall on record for a firm before drilling into one, and
  falls back to fuzzy substring matching when the exact name doesn't hit — openFDA stores
  `"GlaxoSmithKline"` as one word, so typing it as three separate words (or misspelling it)
  returns nothing on an exact match; the fallback searches per significant word and intersects
  the results so a single coincidentally-shared word doesn't pull in an unrelated firm.

## Why this needed to be agentic

The path through steps 1–4 above branches on what each step finds — which is the actual
judgment call, not a formality. Concretely, in the three worked examples in `eval/`:

- On the isolated case, the agent's first two link attempts (NDC, then a manufacturer-name
  fallback) both failed, so it independently decided to broaden the search itself — trying
  brand name, then a generic-name-plus-date-window query — before concluding "isolated." A
  fixed pipeline would have stopped at the first failed lookup and had nothing further to say.
- On the systemic case, the agent noticed that five of the firm's ten recalls were issued the
  same day for the same root cause and should be counted as *one* incident, not five, and that
  the firm's later recalls involved a *different* root cause (nitrosamine impurities, not the
  original content-uniformity issue) — a distinction that changed its answer from a naive
  "10 recalls = clearly systemic" to a more carefully qualified verdict (see AI_USAGE.md for
  how this specific case shifted the eval, twice).
- On the recent-recall case, the agent had to decide whether "no adverse events found" meant
  "clean" or "too soon to tell" — there's no query that answers that distinction; it requires
  weighing the recall's age against what "no results" can and can't mean.
- On the related-products step specifically: the cross-reference tool routinely returns dozens
  of results (one manufacturer had ~180 other listed products), and dumping all of them would be
  useless noise. The agent has to pick the handful actually worth a person's attention and write
  a *specific* reason for each — "same distributor, and their quality-oversight gaps plausibly
  extend to this product" reads differently for an oral tablet than for an injectable, and the
  agent adjusts for that. When the cross-reference comes back empty (common — the NDC directory
  only covers currently-marketed products, so older or OTC items often aren't in it), the agent
  says so plainly instead of omitting the section, because "we checked and found nothing" is a
  different, useful signal from "we didn't check."

None of that is "look up a recall and template an email." If your read on that argument is
that this could still be a fixed if/else script — I'd push back specifically on the second
bullet: knowing that "5 same-day recalls with an identical stated reason" should collapse to
one incident, while "3 recalls years apart with a *different* stated reason each" should not
automatically collapse into one "pattern," is exactly the kind of judgment call that doesn't
reduce to a threshold on recall *count*.

## Architecture

```
src/fda_mcp/          MCP server exposing openFDA drug data as 7 tools (stdio transport)
  openfda_client.py     thin HTTP client over api.fda.gov + the NDC directory, handles pagination/retries/zero-results
  resolver.py            adverse-event linkage (NDC/name fallback chain), related-product cross-referencing, firm fuzzy-matching
  server.py               the MCP server itself
src/agent/
  investigator.py        Claude tool-use loop wired to the MCP server over stdio; the actual agent
src/web/api.py         FastAPI backend: streams the same investigator loop to the browser over SSE
frontend/               React + Vite + Tailwind + Framer Motion UI for the web API
scripts/run_investigation.py   CLI: run one investigation, print the full tool-call trace + verdict
eval/
  cases.py                3 hand-researched ground-truth cases
  ground_truth_research.md   the raw openFDA queries used to establish each case's expected answer
  run_eval.py              runs the agent against all 3, writes full transcripts to eval/results/
tests/                   27 tests: client/resolver/linkage logic against the live openFDA API,
                           plus report-parsing and validation logic (no API calls)
```

MCP is the tool-delivery layer: the agent has no direct access to openFDA, only to the 7 tools
the server exposes, over a real stdio MCP connection (not an in-process function call). The
7th tool, `find_related_products`, is the one the related-products feature runs on — it queries
the FDA's NDC directory (`/drug/ndc.json`) by manufacturer and by active ingredient, which is a
separate dataset from the enforcement/event endpoints the rest of the build uses. The web UI
doesn't bypass any of this — `src/web/api.py` calls the exact same `run_investigation` loop as
the CLI, just with its per-tool-call callback bridged onto a Server-Sent Events stream instead of
printed to a terminal, so the browser can render each tool call as it happens.

The agent's final answer is itself a tool call, `submit_report` — a locally-defined tool (not
served over MCP, since it's not an openFDA operation) with a strict JSON schema, passed to Claude
alongside the 7 MCP tools. This isn't just tidiness: asking a model to hand-write JSON as a plain
text response is a real, demonstrated failure mode (see AI_USAGE.md for two different ways it
went wrong in this build), where tool-call arguments are constructed through schema-guided
generation and can't come back as malformed JSON. That still isn't a complete guarantee — a
required field can come back missing, since the schema is a strong hint to the model, not a
server-enforced contract — so `submit_report`'s payload is validated against a real pydantic
model before being accepted, and a failed validation is sent back to the model as a normal
tool-result error, letting it resubmit within the same investigation rather than the user seeing
a dropped result.

## Setup

Requires Python 3.11+.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

**Before running anything below, open `.env` and set `ANTHROPIC_API_KEY` to a real key.**
`.env.example` ships with every value blank on purpose (it's a template, not a real config) —
`cp`-ing it alone does not get you a working key, it just gets you the file to edit. Skipping
this step fails fast now with one clear line (`ANTHROPIC_API_KEY is not set...`) instead of a
buried async stack trace, but it still won't run without a real key either way.

Run one investigation:
```bash
python scripts/run_investigation.py --recall-number D-1178-2018
python scripts/run_investigation.py --firm "Westminster Pharmaceuticals"
```

Run the eval (3 cases, writes full transcripts to `eval/results/`):
```bash
cd eval && python run_eval.py
```

Run the tests (hits the live openFDA API, no key needed for this part):
```bash
pytest tests/ -v
```

### Web UI

A small React frontend that watches the agent investigate in real time — each tool call
streams in as it happens, followed by the verdict.

```bash
# terminal 1 -- backend (from repo root, venv active, .env set as above)
cd src && uvicorn web.api:app --reload --port 8000

# terminal 2 -- frontend
cd frontend && npm install && npm run dev
```

Open the URL Vite prints (usually http://localhost:5173). The dev server proxies `/api/*` to
the backend on port 8000. Click one of the three example chips for an instant real run, enter
any recall number or firm name, or click any item in the right-hand "Recent recalls" feed (real,
current recalls pulled from `/api/recent-recalls`, de-duped so a same-day multi-strength recall
reads as one story, with the actual drug name as the headline — not just the firm — and a
"search coverage" link out to real-time news results) to investigate that specific incident.

While an investigation is running, a plain status card sits at the top — "Investigating {query}",
the current step in one line, and an explicit "a summary will appear here" note — so it's always
clear the tool is working even before the log below it says anything specific. The step-by-step
log itself is expanded by default, right underneath, and keeps updating live: the point isn't to
hide the process, it's to make sure the plain-language answer is never competing with it for the
top of the screen. Once the verdict lands, the case brief takes the status card's place at the
top and the (still-expanded) log stays right below it — collapsible if you want it out of the
way, but visible unless you ask it not to be.

Once a finding lands, its "Related products to watch" entries are clickable too: clicking one
kicks off a *new* investigation of that product's manufacturer, so you can chase a lead (e.g.
"does this other labeler using the same active ingredient have its own recall history?") without
leaving the tool. That path exercises a real edge case worth knowing about: most clicks land on
a manufacturer with no recall history at all, which isn't an error — the agent short-circuits to
a clean "no FDA recall on record" finding rather than trying to force a recall-shaped answer onto
data that has none. See AI_USAGE.md for how this surfaced as a real 14-minute hang before it was
fixed.

First visit shows a one-time "who's asking?" screen (pharmacist / researcher / other, with a
free-text option) before the tool itself. This isn't cosmetic — each answer is persisted
server-side to `data/identifications.jsonl` via `POST /api/identify` (a real append-only log,
inspectable directly or via `GET /api/identify/summary` for role counts), so it's actual usage
data, not a UI gesture with nothing behind it. Remembered per-browser via localStorage so it
doesn't nag on return visits.

**On reliability.** A slow step and a genuinely stuck one used to look identical — static "..."
dots either way, and a timeout that was, in an earlier pass, tuned from a guess rather than data.
That guess was wrong: it assumed anything past ~60-90s must be stuck, and was cutting off
investigations that were still legitimately working. Real fix came from instrumenting the agent
loop itself (`agent/investigator.py` logs per-turn duration, token counts, and extended-thinking
token counts) and reading the actual numbers: this model does substantial extended thinking by
default, and a turn with real reasoning to do — weighing a verdict, deciding which related
products are worth flagging — routinely takes 15-35 seconds on its own. A normal 5-turn
investigation legitimately totals 60-90+ seconds; that's not a stall, it's the model thinking.
Timeouts are now sized against that real data (120s per model call, 240s overall ceiling) instead
of a guess, and the exact query that had been timing out completed cleanly afterward with a
detailed, correct finding. The per-turn logging stays on permanently — it's genuinely useful
observability, not just how this got diagnosed.

The UI reflects the corrected picture too: a server-sent heartbeat every 3 seconds drives a live
elapsed-time counter (so a real hang is still visually distinguishable from a working-but-slow
step — the clock either keeps ticking or it doesn't), with reassurance copy that now says what's
actually true ("real reasoning, not a lookup") instead of implying anything past a minute is
abnormal. A failed investigation still gets a one-click Retry button regardless of cause. Full
diagnostic trail — including the wrong first diagnosis and how it got corrected — is in
AI_USAGE.md.

## Evidence it does what I claim

`eval/` is the receipts, not just a claim. All 3 cases pass (27/27 tests too) as of the last run in this repo
(`eval/results/*.json` has the full transcript for each — every tool call, every result, the
final verdict). The ground truth for each case was researched by hand against the live API
*before* running the agent (`eval/ground_truth_research.md` has the raw queries), and one case
(`westminster-systemic`) accepts two verdicts rather than one — documented in `eval/cases.py` —
because on the first run the agent's answer ("watch") turned out to be a more careful read of
the data than my own hand-written ground truth ("systemic"). I judged that a finding worth
keeping, not a bug worth prompting away. Full story in AI_USAGE.md.

## What I deliberately cut

- **Devices and food, not just drugs.** openFDA's `openfda` cross-reference block (which links
  a recall to its NDC/generic/brand name) only exists in the drug endpoints in the shape this
  build relies on — food enforcement records don't carry it, so the linkage logic doesn't
  generalize for free. Scoped to drugs to go deep rather than shallow across three domains.
- **Related-products coverage is real but incomplete, and I'm upfront about it in the output
  itself, not just here.** The NDC directory only lists currently-marketed products, so older,
  discontinued, or OTC-monograph items (common among older recalls) are often invisible to the
  cross-reference — the recalled product's *own* NDC record failed to resolve in 2 of the 3 eval
  cases. "Same manufacturer" is also based on the NDC *labeler* (the marketing/distribution
  company), not the physical manufacturing site, so a facility-level issue at a contract
  manufacturer could span labelers this tool won't connect. Both caveats are baked into the
  tool's own output, not just documented here — see `find_related_products`' `caveat` field.
- **No chemical-similarity signal, only same-ingredient.** The third example I was asked for
  ("chemically similar drugs") would need real cheminformatics (structure comparison, drug-class
  relationships) that openFDA doesn't provide — I considered using the SPL-derived
  `pharm_class_cs`/`pharm_class_epc` fields as a proxy for drug class but didn't have time to
  validate whether that's actually a meaningful signal here versus noise; cut rather than ship
  something I hadn't verified.
- **No pagination past 1000 results.** `search_recalls_by_firm` and friends cap at openFDA's
  single-request limit. Fine for every firm I tested (none had more than 10 recalls); would
  break silently-ish (truncated, not wrong) for a firm with hundreds.
- **No entity resolution across subsidiaries/DBAs/acquisitions.** `resolve_firm_name_match`
  handles suffix noise (LLC/Inc/Corp) and one specific punctuation gap I found (see AI_USAGE.md),
  not "Firm X, formerly known as Firm Y" or "Firm X, a subsidiary of Firm Z."
- **No proactive scanning.** The agent investigates one recall at a time, on request. It doesn't
  watch for new recalls and decide which ones are worth investigating — that's a real next step,
  not this build.
- **3-case eval, not a large one.** I picked 3 real cases and verified each by hand rather than
  generating a large set I couldn't personally check. Worth more here than volume I didn't trust.

## What I'd do next with more time

- Expand the eval set past 3 cases, and add a case specifically designed to test the
  same-day-multi-strength-recall collapsing logic in isolation (the agent inferred this
  correctly, but it's currently only exercised as a side effect of the systemic case).
- Try NDC-based linkage against `/drug/label.json` too, to cross-check FAERS reaction terms
  against the product's own labeled warnings — would let the agent reason about whether an
  adverse event is an *expected*, already-labeled risk versus a genuinely new signal.
- Sharpen the `isolated` vs. `insufficient_data` boundary further — I fixed the obvious case
  (a firm's only recall being very recent) with an explicit rule in the system prompt, but
  didn't stress-test edges like "firm's only recall is 8 months old."
- Firm entity resolution (subsidiaries/DBAs) would meaningfully change the systemic/isolated
  read for firms that reorganize or get acquired — currently invisible to this tool.
- Validate `pharm_class_cs`/`pharm_class_epc` (SPL-derived chemical structure and pharmacologic
  class fields, available in the NDC directory) as a third related-products signal alongside
  same-manufacturer and same-ingredient — would get closer to "chemically similar drugs," the
  one related-products angle I didn't ship because I hadn't verified it's actually meaningful.
- Add real news-article linking instead of a search-results link. openFDA has no press-coverage
  field, so today's "Coverage" link is a constructed news-search query (always real, never a
  guessed article URL) — a proper version would need a news/search API integration, which is a
  new external dependency I didn't want to add without discussing scope first.

## Time spent

~6 hours.
