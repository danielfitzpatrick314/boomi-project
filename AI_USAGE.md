# AI usage notes

Built with Claude (Claude Code) as an active pair through the whole process — idea selection,
architecture, implementation, and debugging — not just code generation from a spec I already had.

**Idea and scope.** Started from the assignment's own "why agent" bar and asked Claude for
several directions. Picked the recall-investigator over a "drug risk briefing" alternative
specifically because its branching logic (chase firm history → check event linkage → weigh
before/after timing) produces a falsifiable verdict, where the alternative risked being "gather
everything and summarize" — closer to search than judgment. Considered adding food data
alongside drugs; Claude flagged that food enforcement records don't carry the `openfda`
NDC/name cross-reference block that drug records do, so the linkage approach wouldn't transfer
for free — cut it rather than build two shallow domains in the time available.

**Where the model helped most.** Architecture-before-code, grounded in live API calls rather
than assumption. Before writing the resolver, we tested the "obvious" join key —
`manufacturer_name` on adverse-event records — against the real API and found it matched 1.68M
of ~2.2M total FAERS records for one small firm: openFDA associates every manufacturer ever
linked to an ingredient with the event, not the reporting company. That test happened *before*
the resolver was written, which changed the design (NDC → generic → brand name preferred,
manufacturer demoted to an explicitly-flagged low-confidence fallback) instead of shipping a
broken join and finding out later.

**Where it led me wrong, and how I caught it.** All of these were caught by actually running
the code against the live API and a real model, not by re-reading it and deciding it looked
right:
- The MCP server code was first written against `mcp.server.fastmcp.FastMCP`, which was stale —
  the installed `mcp==2.0.0` had renamed the class to `mcp.server.mcpserver.MCPServer` (and
  `Tool.inputSchema` to `.input_schema`). Both caught immediately on first run, not guessed at.
- A tool function was named `find_related_adverse_events`, same as the resolver function it
  called — which silently rebinds the import at module scope and would have caused infinite
  recursion the first time that tool was actually invoked. Caught by review before running it.
- `.env` had `ANTHROPIC_MODEL=` (blank) as a template placeholder; `os.environ.get(key, default)`
  only falls back on a *missing* key, not an empty one, so the app sent an empty model string to
  the API and got a cryptic 400. Fixed to `os.environ.get(key) or default`.
- `max_tokens=2048` looked reasonable until a real eval run silently truncated a JSON verdict
  mid-string — the model's extended-thinking tokens count against the same budget as the
  visible output. The eval reported this as "actual: None → FAIL," which could easily have been
  misread as "the agent gave a bad answer" instead of "the harness cut it off." Caught by
  reading the raw transcript, not trusting the pass/fail line. Fixed by raising the budget.
- The first real 3-case eval run scored 1/3 against my hand-written ground truth. I didn't
  treat that as "prompt the model until it matches my labels." I read both disagreements: one
  (a firm's only recall being very recent, labeled "isolated" instead of "insufficient_data")
  was a genuine gap in the verdict definitions, so I added an explicit recency rule to the
  system prompt. The other (a firm with three recall episodes over 7 years, called "watch"
  instead of my expected "systemic") turned out to be the model correctly noticing that the
  episodes had *different* root causes and that five same-day recalls were one incident, not
  five — a more careful read than my own ground truth. I updated the eval to accept both
  verdicts for that case, with the reasoning documented in `eval/cases.py`, rather than tune the
  prompt to force agreement with a label I no longer fully stood behind.

**What I'd double-check if I had more time:** whether the recency-rule fix generalizes past the
one case that exposed it (e.g. an 8-month-old single recall), and whether the same-day-recall
collapsing logic holds up on a firm with a messier history than the three cases I hand-checked.

**Frontend pass.** Added a React/Framer Motion UI streaming the same `run_investigation` loop
over SSE, reusing the tested backend unchanged. One real bug here worth flagging: while
verifying it visually, entrance animations appeared permanently stuck mid-transition (elements
frozen at partial opacity). I initially suspected React 19 StrictMode double-invoking effects
and removed it, which didn't fix it. Root cause turned out to be requestAnimationFrame
throttling in the automated browser tool I was using to check the UI (confirmed directly by the
tool reporting the pane as "hidden," and by forcing a window resize, which flushes a repaint and
visibly un-freezes the animation). That's a testing-harness artifact specific to headless/CDP
browser automation, not a bug a real user hitting the page in a normal focused tab would see —
but it's the kind of claim worth being explicit about rather than asserting confidently from a
screenshot that might itself be misleading.

**Visual design pass.** First UI draft leaned hard into "AI product" signifiers — glowing
gradient blobs, glassmorphism, spring-bounce transitions, a pulsing "live agent" badge. Got
direct feedback that it read as demo-ware rather than something a regulatory professional would
trust with a real decision. Rebuilt the visual language around a flatter, denser, Bloomberg-
terminal-adjacent aesthetic: solid bordered panels instead of blur, muted/desaturated status
colors instead of neon, a serif wordmark for gravitas, and motion that's fast and functional
(~200ms) instead of cinematic. The lesson wasn't "add restraint" in the abstract -- it was
naming the specific tells (glow, blur, bounce, ping animations, marketing-hero copy) and cutting
each one individually; "make it more professional" as a prompt to myself wouldn't have caught
the ping-ring animation on its own.

**Output redesign.** Separate feedback, and the more important one: even with the visual pass
done, the *output itself* still read as a tech demo, because the evidence bullets were things
like "find_related_adverse_events returned 0 total_events via manufacturer_name (low
confidence)" -- a debug trace wearing a UI, not a deliverable. The fix wasn't styling, it was
the schema: added a `recommended_action` field (the one line a manager reads if they read
nothing else, explicitly instructed to be a concrete next step, not a restatement of the
verdict), rewrote the system prompt to flatly forbid citing tool or field names in the final
report, and pulled the recall snapshot (firm/product/classification/date) directly from the
`get_recall` tool result into a dedicated `case` object instead of trusting the model to
transcribe it correctly in prose. On the frontend, the step-by-step trace -- which I was told to
keep, since watching the agent's process is part of what makes this feel agentic rather than
scripted -- now collapses to a one-line summary the moment a verdict lands, so the case brief is
what's actually in front of the user, with the trace one click away for anyone auditing the
reasoning. Re-ran the 3-case eval after the schema change to confirm it still passes 3/3 and
spot-checked all three `recommended_action` outputs by hand before trusting them.

**Course correction on the actual mission.** The most important feedback I got wasn't about the
UI at all -- it was that the whole build had drifted into "is this one recall isolated or
systemic," which is a narrower question than the one worth asking: given a recall, what *else*
is at risk downstream. I'd built the isolated/systemic framing early and kept polishing around
it without questioning whether it was still the right center of gravity. The fix was a new tool
(`find_related_products`, querying openFDA's NDC directory by manufacturer and by active
ingredient) and a rewrite of the system prompt to make that tool mandatory on every
investigation, not an optional extra. Two things worth flagging about how this went:
- I tested the tool against real recalls before wiring it into the agent (same discipline as the
  manufacturer_name overcounting check earlier) and found the recalled product's own NDC record
  frequently fails to resolve -- 2 of 3 eval cases -- because the directory only covers
  currently-marketed products and older recalls' NDCs have since expired out of it. Built a
  free-text fallback (guess a searchable name from the product description) *before* shipping,
  rather than discovering the gap from a user report.
- Making related-product manufacturers clickable (so a user can chase "does this other labeler
  have its own recall history?") surfaced a real bug I would not have found otherwise: querying
  a manufacturer with zero recall history caused the agent to hang for 14 minutes with no error,
  because the system prompt's protocol assumed a recall always exists to investigate, and the
  Anthropic client had no request timeout. Both are now fixed (explicit "zero recalls is a valid,
  fast answer" branch in the prompt; a 90s client timeout as a backstop), but I only found this
  by actually clicking through the feature end-to-end in the browser after wiring it up, not by
  reasoning about it in the abstract. It's a good example of why "add a clickable link" is never
  just a frontend change here -- every new interaction path is a new path through the agent loop
  that needs to actually be run, not just coded.

**Feed and citation fixes.** Two smaller but concrete pieces of feedback: the recent-recalls feed
was leading with the firm name and a one-word reason ("CGMP"), not what drug was actually
recalled, and there was no way to find outside coverage of a recall. For the first, openFDA's
structured `brand_name`/`generic_name` fields are frequently empty on enforcement records (this
was already known from the earlier resolver work), so I wrote a small parser
(`extract_product_name`) that pulls the drug name from the free-text description, handling the
one real edge case that broke a naive "split on first comma" -- descriptions where the drug name
itself contains a parenthetical with a comma inside it (e.g. "Levothyroxine and Liothyronine
(Thyroid Tablets, USP)"). For the second, I was not willing to fabricate or guess at a specific
news article URL -- that would risk a broken or simply wrong link presented as if it were real
coverage. Shipped a constructed news-search link instead (always a real, working URL, honestly
labeled as a search, not a specific source) rather than pretending to have found an article I
hadn't.

**Theme reversal.** After the earlier pass toward a dark, Bloomberg-terminal aesthetic, the next
round of feedback was that it had overshot into "hacker vibe" -- dark, low-contrast, harder to
read than it should be for something meant to look legitimate. In hindsight this was predictable:
dark UIs read as developer/terminal tooling by default, and getting them to read as "enterprise
compliance software" instead takes real restraint that a terminal-inspired palette works against
from the start. Real regulatory/quality software (the category this is imitating) is almost
always light -- flipped the whole token set to a white-surface/off-white-background palette,
recalibrating every semantic color for contrast on white rather than muting them for a dark
background, and simplified the background from a grid-textured near-black to a flat, quiet gray.
Kept the structural decisions from the earlier pass (flat panels, no blur, minimal motion, serif
wordmark) since those weren't the problem -- only the color direction was. Caught every leftover
hardcoded `text-white`/`bg-black` utility by grepping across the frontend rather than eyeballing
each file, since a light-theme pass that leaves even a few dark-mode-only classes in place
produces invisible text, not just a slightly-off look.

**Separating "what's happening" from "what you need to read."** Feedback after that: during a
run, the trace was the *only* thing on screen, which made it feel like required reading even
though it was always meant as optional detail. The fix was to stop treating the trace as the
default view of "running" state and add a calm status card (`ProgressStatus`) as the actual
default -- current step in plain language, plus an explicit "a summary will appear here" line --
with the trace collapsed by default and opt-in via a toggle, not forced open. Small thing I
almost missed while wiring this up: `find_related_products` had no entry in the frontend's
tool-label map, so it was rendering its raw Python function name in the trace instead of a
human label ("Cross-referencing related products") -- easy to miss because it only shows up if
someone actually expands the log, which is exactly the opt-in path this change made less common,
so it was worth fixing now rather than letting it become a stale surprise later.

**A real correctness bug: I put invalid JSON in the JSON schema.** Reported symptom: "I didn't
see any summary on the one I just ran." Went looking for a UI bug first and didn't find one --
the render logic for the verdict card was correct. The actual cause was upstream: when I added
the `related_products` field to the system prompt's schema example, I annotated it with `//`
line comments explaining the 0-6-entries constraint, directly inside the JSON block shown to the
model as the exact shape to output. `//` comments aren't valid JSON. On some fraction of runs the
model would echo that pattern into its real output, which failed to parse, which the backend
correctly treated as "no verdict" -- so what looked like "no summary" was actually a silent
parse failure. Two fixes: moved the constraint out of the JSON block into plain prose above it
(the actual bug), and hardened `_parse_final_json` to also try stripping stray `//` lines and
extracting the outer `{...}` from surrounding prose before giving up (defense in depth, in case
the model deviates in some other way I haven't seen yet). Added unit tests
(`tests/test_investigator_parsing.py`) that pin both the comment-stripping and prose-extraction
paths so this class of bug can't quietly regress. Lesson: a schema shown to a model as "the exact
shape to produce" needs to actually be valid in that format itself, comments-as-documentation
included -- the model will pattern-match the example, not just the intent behind it.

**Welcome screen and role capture.** New full-screen gate before the tool: three role cards
(pharmacist / researcher / other-with-free-text) plus a skip option, each choice POSTed to a new
`/api/identify` endpoint that appends a real record (role, optional detail, timestamp) to
`data/identifications.jsonl` -- deliberately not a fake/cosmetic gesture, since "build data on
who uses this" only means something if there's a real file behind it someone could go read.
Remembered per-browser via localStorage so it's a one-time gate, not a nag. The transition itself
(welcome screen blurring/scaling out while the main tool fades/slides in underneath, both
mounted briefly at once) uses Framer Motion's default `AnimatePresence` overlap behavior rather
than `mode="wait"` -- a hard sequential swap would have been simpler but reads as a page change,
not a reveal. Separately, found and fixed a real cross-cutting issue while doing this: Tailwind
v4's preflight doesn't restore `cursor: pointer` on `<button>` the way v3 did (native buttons
default to `cursor: default`), so every clickable button in the app -- not just the recall-feed
items the feedback specifically called out -- had the wrong cursor. Fixed with one global rule
in `index.css` instead of hunting down and patching every button individually.

**Chasing the "no summary" bug further, and finding it was worse than the first fix.** The
user hit a real error and pasted the raw output: right after the `"summary"` string closed,
there was a `</summary>\n<parameter name="evidence">` fragment, and the entire `"evidence"` key
was missing from the object -- the model had leaked what looked like XML-style tool-call syntax
into the middle of a JSON string value. That's a different, stranger failure than the `//`
comment bug from earlier, and it meant the earlier fix (a more forgiving text parser) wasn't
addressing the actual root cause: I was still asking the model to hand-write JSON as a plain-text
final answer and hoping it came out clean.

The real fix was architectural, not another parser patch: added a `submit_report` tool with a
proper JSON schema and had the agent call it as its final action instead of writing JSON in
prose. Tool arguments are constructed from a schema-guided generation process, which rules out
the stray-bracket/comment class of corruption outright -- `call.input` is *always* a syntactically
valid dict by the time the SDK hands it back. But testing this immediately taught me something
non-obvious: a JSON schema's `required` array is a strong hint to the model, not something the
Anthropic API enforces server-side. So the same run could, in principle, still submit a report
missing a required field or (theoretically) with leftover corruption inside a string value.
Rather than trust that away, added `_validate_report`: real pydantic validation against the
`InvestigationResult` model already defined in `fda_mcp/models.py` (previously written but never
actually wired into the runtime path -- it was documentation-only), plus a regex check for the
exact `</tag>` / `<parameter` leak pattern just observed. If either check fails, the code doesn't
silently drop the result or fall back to guessing -- it sends the validation error back to the
model as a `tool_result` with `is_error: true` and lets it resubmit within the same conversation,
the same self-correction mechanism the agent already uses for its own MCP tool calls. Unit tests
(`test_validate_report_*`) pin the missing-field and leaked-tag cases directly so this doesn't
quietly regress. Re-ran the exact recall from the bug report several times afterward to build
confidence rather than trusting a single clean run.

**A genuinely stuck investigation, diagnosed live instead of guessed at.** User reported a run
that "looks frozen" and asked me to confirm which it was before fixing anything. I didn't
guess -- checked the actual backend process: `ps` showed it alive and responsive to `/api/health`,
but `tail` on its logs showed the last real activity (an openFDA HTTP call) was 3.5+ minutes in
the past with nothing since, well past any of the per-call timeouts already in place. That ruled
out "just slow" and confirmed "genuinely stuck." The gap: my earlier fix put a timeout on the
Anthropic *client*, but that only bounds a single call -- the SDK's default `max_retries=2` means
a transient error can silently retry with each attempt getting its own fresh timeout, and nothing
wrapped the *investigation as a whole*, so a stall anywhere (a slow generation, a retry storm, an
MCP round-trip) had no ceiling and the SSE stream would just stop sending bytes with no error and
no signal to the frontend that anything was wrong.

Fixed with defense in depth rather than one patch: capped `max_retries=1` and tightened the
per-call timeout; added an explicit timeout around the MCP `session.call_tool()` path too (hadn't
been covered before); and, most importantly, wrapped the *entire* investigation in
`asyncio.wait_for(..., timeout=150)` in the API layer as an unconditional backstop — whatever the
underlying cause, a stuck request now becomes a clear "Investigation timed out, try again" error
within a known bound instead of silence. Also added a heartbeat: a separate task pushes an
elapsed-time event over SSE every 3 seconds independent of tool-call progress, and the frontend
now shows a live-ticking timer with escalating reassurance copy past 20s and 60s. This was the
direct answer to "show a better loading animation" -- a ticking counter is also a falsifiable
liveness signal: if it stops ticking, something really is frozen (a rendering bug), and if it
keeps ticking through a slow step, that's *working*, not *stuck*, and now the user can tell the
difference at a glance instead of asking me.

Verified end-to-end rather than trusting the code: reproduced the same stall live (a second run
on a different recall also stalled after its 4th tool call), watched the elapsed timer climb
through both the 20s and 60s reassurance tiers correctly, and watched the 150s ceiling fire and
produce a clean, readable error with the investigation log preserved underneath -- then confirmed
retrying immediately afterward started a fresh run with no leftover state.

**I missed half the ask, and the stall came back.** Two follow-up problems from the same report.
First: I'd built an elapsed-time counter into the top status card but never touched the actual
thing that was asked about -- the "Deciding next step..." indicator at the bottom, which was
still a static icon plus three 1px dots barely changing opacity. Solved the wrong half of the
problem and reported it as done; should have re-read the original ask ("a better loading
animation at the bottom") more literally before moving on. Rebuilt it to be unmistakably
animated: a spinning icon in a breathing halo, plus a 6px chat-style bouncing dot indicator --
sized and staged so it can't be mistaken for static, matching the actual request instead of a
nearby thing I'd already built.

Second, and more important: the same 150s-timeout stall happened again on retry, so I checked
the backend logs again rather than assuming the earlier fix was sufficient. Then it happened a
*third* time on `D-0455-2023` -- the single simplest case in this whole project (one recall, no
history, no related products), previously the fastest and most reliable case all session. That
ruled out my leading theory (large tool-call payloads, e.g. a 95-recall firm history, bloating
context enough to slow generation) -- a near-empty case has almost no context to bloat. Trimmed
`search_recalls_by_firm`'s default result cap from 50 to 20 anyway (a real, if secondary,
improvement -- no investigation needs 50 full recall records to judge a pattern), but stopped
short of claiming that as *the* fix, since the evidence didn't support it being the primary
cause. Shortened both timeouts instead (95s overall, was 150s; 40s per model call, was 60s) on
the empirical grounds that nothing had ever self-recovered between 90s and 150s in any test --
every stall observed ran out the full clock, so a shorter ceiling only removes dead waiting, not
real recovery time. Added a one-click Retry button to the error card so recovering from a stall
doesn't require noticing the form re-enabled itself. Then retried the exact failed query and it
succeeded normally in under 15 seconds with identical code and inputs -- the signature of
transient latency on the model API itself, not a deterministic bug in the investigation logic.
Said so plainly rather than claiming the reliability problem was solved: the mitigations (faster
failure, one-click recovery, smaller payloads) reduce the pain, but if this is provider-side
variability on a specific model, no amount of application-level timeout tuning makes it stop
happening, and I don't have visibility into Anthropic's infrastructure to confirm that's the
actual cause versus just the most consistent explanation the evidence supports.

**Correction to the above: that diagnosis was wrong, and I should have gathered the data before
writing it, not after.** The user pushed back -- rightly -- on "probably provider-side latency"
as an explanation that conveniently required no further work from me, and asked for an actual
connection/health check instead of another round of guessing. Did three things in order, each
gating the next: (1) checked for a stray `ANTHROPIC_BASE_URL` pointing somewhere unexpected --
clean, pointed at the standard endpoint; (2) timed a bare `curl` to the API directly, outside my
application entirely -- 388ms connect+TLS, and three trivial `messages.create()` calls at
1-1.5s each, so the network path and the account/model were both demonstrably healthy; (3) added
real per-turn instrumentation (duration, input/output tokens, thinking tokens) directly into the
agent loop and ran the *exact* recall that had just failed for the user.

That's what actually explained it. Turn 2 of that run: 35.1 seconds, 3,126 output tokens, 1,092
of them extended thinking the model does by default on this ID without me requesting it. Turn 4:
26.4 seconds, 974 thinking tokens. Total for a normal, successful 5-turn run: ~83 seconds --
right at the 95s ceiling I'd shortened it to in the *previous* fix, on the strength of a claim
("nothing self-recovers between 90s and 150s") that I never actually verified against real
timing data, only against a handful of failures after I'd already tightened the timeout. That
was circular: shortening the timeout first and then observing "nothing recovers past it" doesn't
show the timeout was correctly placed, it shows the timeout was cutting things off before they
could recover. Reverted the direction entirely -- 120s per call (was 40s), 240s overall (was
95s) -- sized against the real 15-35s-per-turn figures instead of a guess, and re-ran the exact
failed query end-to-end: completed cleanly in ~40 seconds with a genuinely strong finding (it
noticed the same "empty capsule" manufacturing defect recurring a decade apart for the same
firm). Also fixed the timing instrumentation itself once it turned out to be silently producing
no output: uvicorn's own startup logging config disables any Python logger that already exists
at the time it runs its `dictConfig`, and `investigator.py` gets imported (creating its logger)
before that happens, while `httpx`'s logger only worked because it's created lazily, later. Gave
the logger its own handler instead of depending on ambient config. The instrumentation is
staying in permanently, not just as a one-off diagnostic -- turn-level timing and token counts
are worth having in the logs regardless.

The actual lesson isn't "measure things instead of guessing," stated that abstractly -- it's
that I had a *specific* piece of contrary evidence available the whole time (this model does
substantial extended thinking by default, which I'd already noted once earlier in this build)
and didn't connect it to "large tool outputs plus real reasoning plausibly just takes a while"
until asked to actually check. A plausible-sounding external explanation is still a guess if
nothing was measured to support it over the boring internal one.
