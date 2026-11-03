# Independent evidence audit

This standalone standard-library CLI reads a sanitized evidence.json file. It does not import the simulation, start a model, access Google Drive, modify histories.

```sh
python scripts/audit_evidence.py /path/to/evidence.json --output /path/to/audit.json
```

Exit status 0 means the file is internally consistent with these checks; 1 means it failed. The output includes a SHA-256 of the exact input bytes. Existing input evidence cannot be overwritten through --output.

Checks cover real/model label consistency, source and model revision references, duplicate event/request IDs, committed tick bounds, agent coverage, action totals, inference-counter arithmetic, confirmed before/after state, structured private fields and hidden reflection parameters. A history containing more requests than the current session's inference counter raises a warning because recovery resets process counters.

The integrated exporter includes `origin` and `task_id`. Mechanical execution must reference an earlier recorded intention for the same actor, cannot claim its own model request, and is exempt from before/after state. Real intentions require a model request ID; mock intentions must be explicitly marked `mock_policy`. Mechanical counts are reported separately and never expand real-agent coverage. Legacy exports without `origin` remain supported. Wildlife events are excluded by the producer's `validated_action` source filter. Private LTM, scheduler records and RNG fields are rejected alongside root and memories.

The audit cannot independently authenticate a GPU process, prove events were not fabricated, establish scientific discoveries or identify every secret inside free-form speech. Review original runtime evidence and public authored text before publishing. It does not certify a simulation as conscious or a short benchmark as a civilization.

Validation on 2026-11-02: `python -m pytest -q` passed 47 tests (including 17 new audit tests). The existing five-agent export passed with 50 unique requests and ten actions per identity; the fifty-agent export passed with 100 unique requests and two actions per identity. These are audits of previously recorded files, not additional GPU runs. Base source: dfb78d59491b976286d0c0a7c5fb04c4e9306b69. The work is isolated on codex/evidence-audit in its own worktree; no core engine or shared notebook files were changed.
