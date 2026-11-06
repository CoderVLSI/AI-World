# Before scaling to 50 humans: review findings and the bounded check

Review of main at `1495446`, CPU only (no GPU run, no prompts, tool descriptions, root or experiment data changed).

## Findings (verified unless marked)
* **Movement.** WALK is offered and parses (`inference.py` select_tools/parse_tool); a scripted TRAVEL_TO out of a fire completes in 5-6 ticks, so the
  engine path works. In the two direction-word runs the model chose MOVE/WALK zero times anywhere, with only 3-4 failed calls of ~175, so it was a
  model choice. WALK is 12th in the tool list where MOVE is 2nd (hypothesis: ordering matters; not tested). The real runs did not record TRAVEL_TO
  targets or outcomes; `scripts/hazard_response_diagnostic.py` now does (counts only).
* **Animals.** Deterministic rules (`fauna/ecology.py`, own RNG seed+2718), no model call; birds use the same grid rules; Godot animation is display only.
  Animals eat from the same resource nodes as humans. Real-model agents are the humans only.
* **50 humans.** `population=50` assigns gender round-robin but biological sex independently (`genesis.py`), so labels and biology disagree. Use
  `families=25, children_per_family=0`: 25 women and 25 men, all adults, 50 unique identities, separate memories (tested). Wildlife is not in the count.
* **Scaling.** Decisions are sequential, batch size 1, under a lock (`scheduler.py` run, `inference.py` decide). No batching interface exists. Whether
  batching helps a T4/L4 is unmeasured. Batching would change semantics (all agents in a batch decide from one snapshot).
* **Reliability (CPU, mock, 50 humans).** Checkpoint restore, journal recovery and replay all reproduce the live state exactly; fairness: 28-39 decisions
  per agent in 200 ticks, mean interval 6.3 ticks, max wait 6. At 8 decisions per tick and ~1.8 s per call a real tick is ~15 s (cap 20 s).
* **Fixed here:** a crowded inhabitant saw the 12 lowest-numbered neighbours; `inference.nearest_others` now shows the 12 nearest (ties by id). Mock unchanged.
* **Open:** the model's own observation includes `clothing_color` and `skin_tone` although clothing has no mechanic (owner decision); real runs stop
  deciding at a wall-clock cap, so re-running a seed is not bit-identical (journal replay is unaffected); `observe` is O(N^2) (fine at 50);
  mock tick time drifted 0.08 -> 0.14 s over 200 ticks (cause not found); prompt tokens for crowds are estimated at 3-4.5k vs a 6,144 cap (unmeasured).

## The bounded check: `scripts/scale50_check.py`
50 humans (25 couples) + 72 animals, Isvara and nature forces off, default prompts. Hard limits: wall clock (900 s), rolling failure rate >= 20% over 40
calls, recorded event bytes > 200 MB. Writes counts, categories and seconds only. Metrics: seconds per call (p50/p95), per-tick seconds, tool choices,
failure categories, rejections by reason, decisions per human with a fairness index, wait/interval, prompt tokens, GPU peak, deaths/health,
humans vs wildlife reported separately, and a checkpoint restore check (state equal, zero model calls). Mock: `python scripts/scale50_check.py
--backend mock --out m.json`. Real model needs a CUDA GPU and the owner's go-ahead; without one it writes `unverified_no_gpu` and exits 2.
Not included: a batch-size micro-benchmark (needs a batched decide, to be built only if worthwhile).

## Fixes after the 200-tick far-start run (PR #35, stopped at tick 160 by the failure-rate rule)
* **Used-up nodes are no longer listed to the model** (`inference.visible_resources`): in that run 427 of 528 GATHER_AT requests were rejected as
  "resource unavailable" while only 2 nodes were depleted on the whole map, i.e. the model kept asking for nodes that were still listed with 0 units
  (inferred from that arithmetic; the result file has no per-node record). The engine still keeps the node; an inhabitant's own memory already forgets
  sites seen empty. This changes what the real model sees; mock policy and all fixtures are unchanged.
* **An over-long optional `reason` is cut to its 300-character limit** instead of failing the whole decision (19 of 42 failures were "too long", most
  likely this). Every other text limit still fails, and the message now names the parameter (a fixed label, never model text).
* **Failure detail:** `metrics()["failure_detail"]` counts failures by fixed message label and how many filled the token budget; reported by
  `scripts/scale50_check.py` as `failure_detail`.
* **`--founder-water N`** (World/CLI/script; default 3 = unchanged): 0 starts everyone thirsty about 80 ticks sooner, so a shorter run reaches real need.

## Sight range (`sight_range`, opt-in experiment)
Inhabitants see resource nodes only within 8 tiles and have no terrain information at all, so a thirsty person with no water in sight has nothing to act
on (the 200-tick thirsty-start run, PR #37: mean thirst 69, nobody drank, 52% of choices were SPEAK, 16 of 50 moved at all). `World(sight_range=N)` /
`--sight-range N` (8 to 64; default 8 = unchanged and not recorded) lets them see resource nodes N tiles away (Manhattan), nearest first, up to the usual
16 listed. It is a fact about what a person can see, not advice; nobody is told what to do, and others, works and animals keep their own ranges.
At 32 tiles, 48 of 50 far-start founders see food or water (0 of 50 at 8). It is stored in the checkpoint manifest, so restore and replay keep it.
The question it tests: does a thirsty model act on water it can see? `scripts/scale50_check.py --sight-range 32`.
## Batched decisions (opt-in, off by default)
`TransformersLFM3Backend(batch_size=N)` / `scripts/scale50_check.py --batch-size N` decide up to N inhabitants in one generate call.
* **How:** before a tick's decisions, `Scheduler._prefetch` (a guarded hook: only when the backend offers `batch_size` > 1) takes observations of the
  first `max_decisions_per_tick` inhabitants in the queue at one moment and hands them to the backend in chunks of N; `decide` then returns each batched
  choice when the scheduler asks in its normal order. Each choice is still validated against the world as it is when applied, so conflicts are rejected
  as usual. Who is asked, in what order and how many per tick are unchanged. The per-tick wall-clock cap also limits how many batches start.
* **Semantics that differ (by design, say so when comparing runs):** inhabitants in one batch decide from the same snapshot instead of seeing the
  effects of earlier inhabitants in the same tick. A prompt over the token budget, an unparseable output or a failed item fails alone; if a whole
  batch cannot run (for example out of memory) each item is retried one at a time.
* **Verified (fakes, no GPU):** batch of one equals the ordinary path; one prompt of several fails alone; stale-tick results are never used; fallback;
  counters; the scheduler hook (chunking, one snapshot, cap); nothing changes with batch size 1 or the mock.
* **NOT verified:** that it is faster on a T4 or L4, memory use, and whether greedy decoding with left padding gives the same text as a batch of one.
  `scripts/batch_check.py` measures exactly that on fixed observations (speed, peak memory, failures, and the fraction of choices equal to batch size 1).
  The protected `scheduler.py` has one small guarded addition for the hook; `root.py`, prompts and tool descriptions are untouched.

## The water ladder (`scripts/scenario_ladder.py`): small, fast, one question at a time
Fifty-person runs take about an hour and mostly say "the model did not act". The ladder asks ONE question with a clear pass condition, on 5 inhabitants
for 40 ticks (about 6 minutes per rung on a T4): **does a thirsty inhabitant get to water and drink?** Operator fixture, stated openly: every resource
node is removed, one water node (40 units, renewable) is placed `distance` tiles from the group, and each inhabitant starts thirsty (60/100) with no water and
3 food. PASS means a DRINK that lowered their thirst; a parsed TRAVEL_TO/GATHER_AT is only an intermediate result. Also recorded: who reached the node,
who gathered, and the first ticks. Rungs: R0 water at the group; R1 6 tiles, in sight; R2 16 tiles, sight 32; R3 30 tiles, sight 32; R4 16 tiles, NOT in
sight (exploration). The first rung that fails shows where the model stops. A mock policy passes R0-R3 and fails R4 (checks the harness only).

**First real result (Codex, T4, 5 rungs, 40 ticks each; its push to GitHub was blocked, so the JSON is not in the repo yet):** zero inhabitants gathered water or drank on any rung, including R0 (water at the group), with 280 GATHER_AT and 100 DRINK choices and zero TRAVEL_TO/MOVE/WALK. The first version of the ladder did not record why. It now records, as counts only: whether each chosen tool was on offer (DRINK is only offered when water is carried), whether GATHER_AT named the water node or another id, whether its amount was in range, whether the node was in sight, rejections by reason, and the node's units left. `--node-id` lets you test an id in the usual `resource-0001` style in case the fixture's descriptive id is what confuses the model.
