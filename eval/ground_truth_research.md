# Ground truth research for eval/cases.py

Raw queries against `api.fda.gov` used to independently establish the expected
verdict for each eval case, before running the agent. Anyone can re-run these
with `curl` to check the underlying facts.

## Case 1: D-1178-2018 (Westminster Pharmaceuticals LLC) -> expect "systemic"

```
curl -sG "https://api.fda.gov/drug/enforcement.json" \
  --data-urlencode 'search=recalling_firm:"Westminster Pharmaceuticals"' \
  --data-urlencode "limit=10&sort=recall_initiation_date:asc"
```

Result: 10 recalls total, in three date-clustered episodes:

| recall_number | date | class | reason (truncated) |
|---|---|---|---|
| D-1178-2018, D-1179-2018, D-1180-2018, D-1181-2018, D-1182-2018 | 2018-08-03 | Class I | Failed Content Uniformity Specifications: adulterated API |
| D-0300-2019, D-0301-2019, D-0302-2019 | 2018-10-29 | Class II | CGMP Deviations: NDEA impurity |
| D-0581-2025, D-0582-2025 | 2025-08-06 | Class II | CGMP Deviations: N-nitroso-metoprolol nitrosamine above limit |

Three distinct quality-control failures spanning 2018-2025, all manufacturing/impurity
related. This is a repeat pattern, not one bad batch -- "systemic".

## Case 2: D-0455-2023 (Nanomaterials Discovery Corporation) -> expect "isolated"

```
curl -sG "https://api.fda.gov/drug/enforcement.json" \
  --data-urlencode 'search=recalling_firm:"Nanomaterials Discovery Corporation"' \
  --data-urlencode "limit=1"
```

Result: `meta.results.total = 1`. Exactly one recall ever, for chemical contamination
(methanol/acetaldehyde/acetal above limits) in a hand sanitizer. Checked
`patient.drug.openfda.manufacturer_name:"Nanomaterials Discovery Corporation"` against
`/drug/event.json` -> HTTP 404 (zero adverse events linked). No pattern, no linked harm
signal -- "isolated".

## Case 3: D-0620-2026 (Beekeeper's Naturals USA Inc.) -> expect "insufficient_data"

```
curl -sG "https://api.fda.gov/drug/enforcement.json" \
  --data-urlencode 'search=recalling_firm:"BEEKEEPER'"'"'S NATURALS USA INC."' \
  --data-urlencode "limit=1"
```

Result: `meta.results.total = 1`. Only recall on file, initiated 2026-06-01 -- about 2.5
months before this research was done (2026-08-21). No firm history to judge a pattern
from, and not enough time has passed for a meaningful adverse-event trail to exist either
way. The honest call is "too early to tell," not "isolated" -- a real recall that happens
to be recent shouldn't get the same label as a firm with years of clean history.

## The manufacturer_name overcounting problem (why find_related_adverse_events exists)

```
curl -sG "https://api.fda.gov/drug/event.json" \
  --data-urlencode 'search=patient.drug.openfda.manufacturer_name.exact:"Westminster Pharmaceuticals, LLC"' \
  --data-urlencode "limit=1"
```

Result: `meta.results.total = 1,682,659` -- out of ~2.2M total drug adverse-event records
in the entire dataset. A `count` query on the same field showed the top manufacturers by
this metric all cluster in the 1.2-1.7M range (Aurobindo, Camber, Sun Pharma, etc.) --
i.e. this field associates essentially every manufacturer of a given active ingredient
with the event, not the actual reporting company. This is why `resolver.py` treats
manufacturer-name-based event linkage as low-confidence and prefers NDC/generic/brand
matches, and why the MCP tool surfaces a `caveat` string the agent is instructed to
weigh rather than silently trust a number.
