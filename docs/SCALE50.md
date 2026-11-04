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
