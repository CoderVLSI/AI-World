"""Structured, bounded, private long-term memory (no extra model instances).

Each inhabitant owns ``agent.ltm``.  Nothing here is shared between inhabitants
except through explicit, journaled social acts (witnessing, SHARE_KNOWLEDGE,
TEACH, reading a written work), and every transferred item keeps its origin and
is *not* treated as true: hearsay stays ``unverified`` until the receiver's own
experience corroborates or contradicts it.

Categories
----------
episodic       what happened
practical      structured observations ("subject / property / value") with evidence
hypotheses     the inhabitant's own unverified explanations
relationships  tallies of important social experiences
procedural     reusable sequences of actions that produced a measured result
cultural       information learned from others or from written works
places         where resources were seen (spatial memory)

Nothing from a previous life, the root registry or any scripture is ever added:
a newborn starts with an empty store and acquires knowledge only by ordinary
observation and social contact.
"""
import math
import re

from .actions import Spec
from .lifecycle import age
from .nature import EDIBLE

CATEGORIES = ("episodic", "practical", "hypotheses", "procedural", "cultural")
EXPERIMENT_ACTIONS = frozenset({"INSPECT", "STRIKE", "COMBINE", "SEPARATE", "HEAT", "COOL", "RUB", "FEED_FIRE",
                                "TEST", "GATHER_WITH"})
SOCIAL_ACTIONS = frozenset({"GIVE", "CARE", "TEACH", "SPEAK", "HAND_OVER", "REPRODUCE"})
LIMIT_KEYS = {"episodic": "episodic_limit", "practical": "practical_limit", "hypotheses": "hypothesis_limit",
              "cultural": "cultural_limit", "procedural": "procedural_limit"}
OWN, WITNESSED, HEARSAY, WRITTEN = "own_observation", "observed_demonstration", "hearsay", "written_work"
CONFIDENCE = {OWN: 0.6, WITNESSED: 0.45, HEARSAY: 0.3, WRITTEN: 0.3}
MAX_TEXT = 220
SAMPLES = 8
STOP = {"the", "and", "for", "with", "into", "from", "that", "this", "test", "effect"}
_WORDS = re.compile(r"[a-z_]{3,}")


# ---------------------------------------------------------------- storage
def ensure(a):
    ltm = a.ltm
    if not ltm:
        ltm.update(next_id=0, episodic=[], practical=[], hypotheses=[], procedural=[], cultural=[],
                   relationships={}, places={}, recent_ops=[])
    return ltm


def tokens(*parts):
    out = set()
    for part in parts:
        out |= {w for w in _WORDS.findall(str(part).lower().replace("_", " ").replace("[", " ").replace("]", " "))
                if w not in STOP}
    return sorted(out)


def _retention(entry, now_tick):
    recency = math.exp(-max(0, now_tick - entry["tick"]) / 3000)
    return entry["importance"] * 0.6 + entry.get("confidence", 0.3) * 0.3 + recency * 0.1


def _add(world, a, category, entry):
    ltm = ensure(a)
    entry["id"] = f"m-{ltm['next_id']:06}"
    ltm["next_id"] += 1
    entry.setdefault("tick", world.tick)
    entry["text"] = entry.get("text", "")[:MAX_TEXT]
    bucket = ltm[category]
    bucket.append(entry)
    limit = getattr(world.autonomy.memory, LIMIT_KEYS[category])
    while len(bucket) > limit:
        bucket.remove(min(bucket, key=lambda e: (_retention(e, world.tick), e["id"])))
    return entry


def find(a, entry_id, categories=CATEGORIES):
    ltm = ensure(a)
    for category in categories:
        for entry in ltm[category]:
            if entry["id"] == entry_id:
                return category, entry
    return None, None


def _event_id(world):
    return f"evt-{max(0, len(world.events) - 1):09}"


# --------------------------------------------------------- practical facts
def _is_number(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _cond_key(fact):
    return json_key(fact.get("conditions", {}))


def json_key(value):
    import json
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def _consistent_number(samples, value):
    mean = sum(samples) / len(samples)
    spread = math.sqrt(sum((s - mean) ** 2 for s in samples) / len(samples))
    return abs(value - mean) <= max(3 * spread, 0.35 * abs(mean), 4.0)


def learn_fact(world, a, fact, origin, category="practical"):
    """Record or reinforce an observation; hearsay about the same thing is checked against it."""
    ltm = ensure(a)
    subject, prop, value = fact["subject"], fact["property"], fact["value"]
    cond = _cond_key(fact)
    mine = origin["type"] in (OWN, WITNESSED)
    entry = next((e for e in ltm["practical"] if e["subject"] == subject and e["property"] == prop and e["cond"] == cond), None)
    if entry is None:
        text = f"{subject}: {prop} = {value}" + (f" when {fact['conditions']}" if fact.get("conditions") else "")
        entry = _add(world, a, "practical", {
            "subject": subject, "property": prop, "cond": cond, "conditions": fact.get("conditions", {}),
            "value": value, "samples": [value] if _is_number(value) else [], "outcomes": {} if _is_number(value) else {str(value): 1},
            "count": 1, "origins": [origin], "status": "observed", "confidence": CONFIDENCE[origin["type"]],
            "importance": 0.6, "text": text, "tags": tokens(subject, prop), "revisions": [],
            "independent": origin["type"] == OWN})
    else:
        entry["count"] += 1
        entry["origins"] = (entry["origins"] + [origin])[-6:]
        if _is_number(value) and entry["samples"]:
            ok = _consistent_number(entry["samples"], value)
            entry["samples"] = (entry["samples"] + [value])[-SAMPLES:]
            entry["value"] = round(sum(entry["samples"]) / len(entry["samples"]), 2)
            entry["text"] = f"{subject}: {prop} = {entry['value']} (n={entry['count']})"[:MAX_TEXT]
        else:
            counts = entry["outcomes"]
            counts[str(value)] = counts.get(str(value), 0) + 1
            ok = len(counts) == 1
            entry["value"] = max(counts, key=lambda k: (counts[k], k))
        if ok:
            entry["confidence"] = round(min(0.95, entry["confidence"] + 0.1), 3)
            if entry["status"] != "variable":
                entry["status"] = "corroborated"
        else:
            entry["status"] = "variable"
            entry["revisions"].append({"tick": world.tick, "note": "later observations did not agree", "value": value})
            entry["revisions"][:] = entry["revisions"][-6:]
        if origin["type"] == OWN:
            entry["independent"] = True
    if mine:
        _test_hearsay(world, a, subject, prop, cond, value)
    return entry


def _test_hearsay(world, a, subject, prop, cond, value):
    """Own experience re-examines what others claimed about the same thing."""
    for claim in ensure(a)["cultural"]:
        if claim.get("subject") != subject or claim.get("property") != prop or claim.get("cond") != cond:
            continue
        practical = next((e for e in a.ltm["practical"] if e["subject"] == subject and e["property"] == prop
                          and e["cond"] == cond), None)
        if practical is None:
            continue
        claimed = claim["value"]
        if _is_number(claimed) and _is_number(practical["value"]):
            agrees = abs(claimed - practical["value"]) <= max(0.35 * abs(practical["value"]), 4.0)
        else:
            agrees = str(claimed) == str(practical["value"]) or str(claimed) in practical.get("outcomes", {})
        status = "corroborated" if agrees else "contradicted"
        if claim["status"] != status:
            claim["revisions"].append({"tick": world.tick, "from": claim["status"], "to": status,
                                       "evidence": practical["id"]})
            claim["status"] = status
            claim["confidence"] = round(min(0.9, claim["confidence"] + 0.3) if agrees else claim["confidence"] * 0.3, 3)


# ------------------------------------------------------------ hooks
def note_surroundings(world, a):
    """Spatial memory: remember where resources were seen (updated when the inhabitant is asked to decide)."""
    ltm = ensure(a)
    seen = {}
    for node in world.resources.values():
        if abs(node["x"] - a.x) + abs(node["z"] - a.z) <= 8 and node["amount"] > 0:
            seen.setdefault(node["kind"], []).append(node)
    for kind, nodes in seen.items():
        sites = {tuple(s[:2]): s for s in ltm["places"].get(kind, [])}
        for node in sorted(nodes, key=lambda n: (abs(n["x"] - a.x) + abs(n["z"] - a.z), n["id"]))[:3]:
            sites[(node["x"], node["z"])] = [node["x"], node["z"], node["amount"], world.tick]
        ltm["places"][kind] = sorted(sites.values(), key=lambda s: -s[3])[:4]


def _relationship(world, a, other_id, key):
    ltm = ensure(a)
    rel = ltm["relationships"].setdefault(other_id, {})
    rel[key] = rel.get(key, 0) + 1
    rel["last_tick"] = world.tick
    if len(ltm["relationships"]) > world.autonomy.memory.relationship_limit:
        oldest = min(ltm["relationships"], key=lambda k: ltm["relationships"][k]["last_tick"])
        del ltm["relationships"][oldest]


def _episode(world, a, action, params, payload, importance):
    result = payload.get("result", payload.get("outcome", ""))
    detail = ", ".join(f"{k}={v}" for k, v in params.items() if k in ("force", "minutes", "method", "test", "magnitude", "kind", "target", "source"))
    _add(world, a, "episodic", {"text": f"{action.lower()} {detail} -> {result}".strip(), "importance": importance,
                                "tags": tokens(action, detail, result), "event": _event_id(world), "confidence": 0.9})


def _procedure(world, a, action, params, payload):
    """Remember the recent chain of experimental steps when it produced a measured, useful result."""
    ltm = ensure(a)
    generic = {k: v for k, v in params.items() if k in ("force", "minutes", "method", "test", "magnitude", "target", "kind", "source")}
    ltm["recent_ops"].append({"action": action, "params": generic, "result": payload.get("result", "")})
    ltm["recent_ops"][:] = ltm["recent_ops"][-6:]
    useful = payload.get("result") in ("ignited", "hardened_by_fire") or any(
        f["property"].startswith(("cut_depth", "pounding_power", "performance_gathering")) and _is_number(f["value"]) and f["value"] >= 8
        for f in payload.get("facts", []))
    if useful and not any(p["steps"] == ltm["recent_ops"] for p in ltm["procedural"]):
        _add(world, a, "procedural", {"steps": list(ltm["recent_ops"]), "outcome": payload.get("result"),
                                      "importance": 0.8, "confidence": 0.6, "text": "sequence leading to: " + str(payload.get("result")),
                                      "tags": tokens(*[o["action"] for o in ltm["recent_ops"]], payload.get("result", ""))})


def after_action(world, a, action, params, payload):
    """Update memories after any accepted action (also used for mechanical steps)."""
    if not world.autonomy.memory.enabled or age(world, a) < 3:
        return
    cfg = world.autonomy.memory
    ensure(a)
    if action in EXPERIMENT_ACTIONS:
        importance = 0.9 if payload.get("result") in ("ignited", "hardened_by_fire", "tool_failed_under_load") else 0.4
        _episode(world, a, action, params, payload, importance)
        origin = {"type": OWN, "event": _event_id(world), "tick": world.tick}
        for fact in payload.get("facts", []):
            learn_fact(world, a, fact, origin)
        _procedure(world, a, action, params, payload)
        witnesses = [b for b in world.agents.values() if b.alive and b.id != a.id and age(world, b) >= 3
                     and abs(b.x - a.x) + abs(b.z - a.z) <= cfg.witness_distance]
        for b in witnesses:
            ensure(b)
            seen = {"type": WITNESSED, "source_agent": a.id, "event": _event_id(world), "tick": world.tick}
            for fact in payload.get("facts", []):
                learn_fact(world, b, fact, seen)
            _add(world, b, "episodic", {"text": f"watched {a.id} {action.lower()} -> {payload.get('result', '')}",
                                        "importance": 0.3, "tags": tokens(action, payload.get("result", ""), a.id),
                                        "event": _event_id(world), "confidence": 0.8})
            _relationship(world, b, a.id, "watched_experiments")
    elif action in SOCIAL_ACTIONS:
        target = params.get("target_id")
        _episode(world, a, action, params, payload, 0.5)
        if action == "GIVE" and target in world.agents:
            _relationship(world, a, target, "gifts_given")
            _relationship(world, world.agents[target], a.id, "gifts_received")
        elif action == "HAND_OVER" and target in world.agents:
            _relationship(world, a, target, "objects_given")
            _relationship(world, world.agents[target], a.id, "objects_received")
        elif action == "CARE" and target in world.agents:
            _relationship(world, a, target, "care_given")
            _relationship(world, world.agents[target], a.id, "care_received")
        elif action == "TEACH" and target in world.agents:
            _relationship(world, a, target, "taught")
            b = world.agents[target]
            _relationship(world, b, a.id, "taught_by")
            _add(world, b, "cultural", {"text": f"{params['topic']}: {params['text']}", "subject": None,
                                        "origin": {"type": HEARSAY, "source_agent": a.id, "chain": [a.id], "tick": world.tick},
                                        "status": "unverified", "confidence": CONFIDENCE[HEARSAY], "importance": 0.4,
                                        "tags": tokens(params["topic"], params["text"]), "revisions": []})
        elif action == "SPEAK":
            for b in world.agents.values():
                if b.id != a.id and b.alive and abs(b.x - a.x) + abs(b.z - a.z) <= 5:
                    _relationship(world, b, a.id, "heard_from")
    elif action == "READ":
        work = world.works.get(params.get("work_id"))
        if work and work.get("claims"):
            for claim in work["claims"]:
                _receive_claim(world, a, claim, {"type": WRITTEN, "work_id": work["id"], "author": work["creator_agent_id"],
                                                 "revision": work["revision"], "tick": world.tick})
            _episode(world, a, action, {}, {"result": f"read findings in {work['id']}"}, 0.5)
    elif action in ("WRITE", "REVISE", "BORN"):
        _episode(world, a, action, {}, payload, 0.3)


def _receive_claim(world, b, claim, origin):
    """Add a second-hand claim as unverified cultural knowledge, checked against what b already observed."""
    ensure(b)
    cond = json_key(claim.get("conditions", {}))
    existing = next((e for e in b.ltm["cultural"] if e.get("subject") == claim["subject"]
                     and e.get("property") == claim["property"] and e.get("cond") == cond
                     and e["origin"].get("source_agent") == origin.get("source_agent")
                     and e["origin"].get("work_id") == origin.get("work_id")), None)
    if existing:
        return existing
    chain = list(claim.get("chain", [])) + ([origin["source_agent"]] if origin.get("source_agent") else [])
    entry = _add(world, b, "cultural", {
        "subject": claim["subject"], "property": claim["property"], "cond": cond,
        "conditions": claim.get("conditions", {}), "value": claim["value"],
        "text": f"{claim['subject']}: {claim['property']} = {claim['value']}",
        "origin": dict(origin, chain=chain, original_status=claim.get("status")), "status": "unverified",
        "confidence": round(min(0.4, CONFIDENCE[origin["type"]], claim.get("confidence", 0.3) * 0.6), 3),
        "importance": 0.5, "tags": tokens(claim["subject"], claim["property"]), "revisions": []})
    own = next((e for e in b.ltm["practical"] if e["subject"] == claim["subject"] and e["property"] == claim["property"]
                and e["cond"] == cond), None)
    if own:
        _test_hearsay(world, b, claim["subject"], claim["property"], cond, own["value"])
    return entry


# ------------------------------------------------------------- retrieval
def situation_tags(world, a):
    tags = set()
    for node in world.resources.values():
        if abs(node["x"] - a.x) + abs(node["z"] - a.z) <= 8 and node["amount"] > 0:
            tags.add(node["kind"])
    tags |= {k for k, v in a.inventory.items() if v > 0}
    for obj in world.objects.values():
        if obj["held_by"] == a.id or (obj["held_by"] is None and abs(obj["x"] - a.x) + abs(obj["z"] - a.z) <= 2):
            tags |= {c["material"] for c in obj["components"]}
            tags |= {"fire"} if obj["kind"] == "fire" else set()
    for b in world.agents.values():
        if b.alive and b.id != a.id and abs(b.x - a.x) + abs(b.z - a.z) <= 8:
            tags.add(b.id)
    if a.thirst >= 50:
        tags |= {"water", "thirst", "dehydration"}
    if a.hunger >= 50:
        tags |= {"food", "hunger", "starvation"} | set(EDIBLE)
    if a.task:
        tags.add(a.task["kind"].lower())
    tags |= {m["action"].lower() for m in a.memories[-3:] if "action" in m}
    return tags


def _score(entry, tags, now_tick, hours_per_tick):
    overlap = len(tags & set(entry.get("tags", ())))
    age_hours = (now_tick - entry["tick"]) * hours_per_tick
    penalty = 1.5 if entry.get("status") in ("contradicted", "variable") else 0.0
    return 2.0 * overlap + 1.5 * entry["importance"] + entry.get("confidence", 0.3) + math.exp(-age_hours / 72) - penalty


def recall(world, a):
    """The few memories most relevant to the present situation, within the configured size budget."""
    cfg = world.autonomy.memory
    if not a.ltm:
        return []
    tags = situation_tags(world, a)
    scored = []
    for category in CATEGORIES:
        for entry in a.ltm[category]:
            scored.append((-_score(entry, tags, world.tick, world.hours_per_tick), entry["id"], category, entry))
    scored.sort(key=lambda t: t[:2])
    items, used = [], 0
    for kind, relevant in (("water", a.thirst >= 40), ("food", a.hunger >= 40)):
        kinds = ("water",) if kind == "water" else EDIBLE
        if relevant:
            sites = [(s, k) for k in kinds for s in a.ltm["places"].get(k, [])]
            if sites:
                (x, z, amount, seen), k = min(sites, key=lambda t: (abs(t[0][0] - a.x) + abs(t[0][1] - a.z), t[0][3] * -1))
                items.append({"id": "place", "kind": "place", "text": f"{k} was seen at x={x}, z={z}, {world.tick - seen} ticks ago (amount {amount})"})
    for rid, rel in sorted(a.ltm["relationships"].items(), key=lambda kv: -kv[1]["last_tick"])[:2]:
        if rid in tags:
            items.append({"id": rid, "kind": "relationship", "text": ", ".join(f"{k}={v}" for k, v in sorted(rel.items()) if k != "last_tick")})
    for _, _, category, entry in scored:
        if len(items) >= cfg.recall_items:
            break
        item = {"id": entry["id"], "kind": category, "text": entry["text"], "status": entry.get("status", "recorded"),
                "confidence": entry.get("confidence")}
        origin = entry.get("origin") or (entry.get("origins") or [{}])[-1]
        if origin.get("type") in (HEARSAY, WITNESSED, WRITTEN):
            item["source"] = origin.get("source_agent") or origin.get("author") or origin.get("work_id")
        items.append(item)
    out = []
    for item in items:
        used += len(item["text"]) + 40
        if used > cfg.recall_chars and out:
            break
        out.append(item)
    return out[:cfg.recall_items]


# ----------------------------------------------------------- memory actions
def _hypothesize(world, a, p, payload):
    if not isinstance(p["statement"], str) or not p["statement"].strip() or len(p["statement"]) > 300:
        return "invalid statement"
    if not isinstance(p["subject"], str) or not p["subject"].strip() or len(p["subject"]) > 80:
        return "invalid subject"
    entry = _add(world, a, "hypotheses", {"text": p["statement"].strip(), "subject": p["subject"].strip(),
                                          "status": "unverified", "confidence": 0.3, "importance": 0.6,
                                          "origin": {"type": "own_hypothesis", "tick": world.tick},
                                          "tags": tokens(p["subject"], p["statement"]), "revisions": [], "evidence": []})
    payload.clear()                       # private: the statement never enters the public journal
    payload["result"] = "hypothesis_recorded"
    a.memories.append({"tick": world.tick, "recorded_hypothesis": entry["id"]})


def _assess(world, a, p, payload):
    category, entry = find(a, p["entry_id"], ("hypotheses", "practical", "cultural"))
    if entry is None:
        return "unknown memory entry"
    if p["verdict"] not in ("supported", "contradicted", "uncertain"):
        return "verdict must be supported, contradicted or uncertain"
    ev_cat, evidence = find(a, p["evidence_id"], ("practical", "episodic"))
    if evidence is None or evidence["id"] == entry["id"]:
        return "evidence must be a different entry of your own observations or events"
    if p["verdict"] != "uncertain":
        subject = (entry.get("subject") or "").lower()
        haystack = " ".join([evidence.get("subject") or "", evidence["text"]]).lower()
        if not (set(tokens(subject)) & set(tokens(haystack))) and not (set(entry.get("tags", ())) & set(evidence.get("tags", ()))):
            return "the evidence does not concern the same thing"
    old_status = entry["status"]
    if p["verdict"] == "supported":
        entry["confidence"] = round(min(0.8, entry["confidence"] + 0.2), 3)
        entry["status"] = "supported"
    elif p["verdict"] == "contradicted":
        entry["confidence"] = round(entry["confidence"] * 0.4, 3)
        entry["status"] = "contradicted"
    entry.setdefault("evidence", []).append(evidence["id"])
    entry.setdefault("revisions", []).append({"tick": world.tick, "from": old_status, "to": entry["status"],
                                              "evidence": evidence["id"], "verdict": p["verdict"]})
    entry["revisions"][:] = entry["revisions"][-6:]
    payload.clear()
    payload["result"] = "belief_" + p["verdict"]


def _claim_from(entry):
    if entry.get("subject") is None or "property" not in entry:
        return None
    return {"subject": entry["subject"], "property": entry["property"], "value": entry["value"],
            "conditions": entry.get("conditions", {}), "status": entry["status"], "confidence": entry["confidence"],
            "chain": (entry.get("origin") or {}).get("chain", [])}


def _share(world, a, p, payload):
    b = world.agents.get(p["target_id"]) if isinstance(p["target_id"], str) else None
    if b is None or not b.alive or b.id == a.id or abs(b.x - a.x) + abs(b.z - a.z) > 2:
        return "recipient unavailable or not nearby"
    if age(world, b) < 3:
        return "recipient is too young for symbolic learning"
    category, entry = find(a, p["entry_id"], ("practical", "cultural"))
    claim = _claim_from(entry) if entry else None
    if claim is None:
        return "no such structured finding to share"
    if not world._spend_energy(a, 1):
        return "insufficient energy"
    origin = {"type": HEARSAY, "source_agent": a.id, "tick": world.tick}
    received = _receive_claim(world, b, claim, origin)
    _relationship(world, a, b.id, "taught")
    _relationship(world, b, a.id, "taught_by")
    _add(world, b, "episodic", {"text": f"{a.id} told me: {entry['text']}", "importance": 0.4, "tags": tokens(entry["text"], a.id),
                                "event": _event_id(world), "confidence": 0.7})
    payload.clear()
    payload.update(result="knowledge_shared", recipient=b.id, recipient_status=received["status"])


def _write_findings(world, a, p, payload):
    title = p["title"]
    ids = [t.strip() for t in p["entry_ids"].split(",") if t.strip()] if isinstance(p["entry_ids"], str) else []
    if not isinstance(title, str) or not title.strip() or len(title) > 100 or not 1 <= len(ids) <= 5 or len(set(ids)) != len(ids):
        return "give a title and 1-5 distinct entry ids"
    claims = []
    for entry_id in ids:
        category, entry = find(a, entry_id, ("practical", "cultural"))
        claim = _claim_from(entry) if entry else None
        if claim is None:
            return "every entry must be one of your structured findings"
        claims.append(claim)
    if not world._spend_energy(a, 2):
        return "insufficient energy"
    wid = f"work-{len(world.works):06}"
    text = "; ".join(f"{c['subject']}: {c['property']} = {c['value']} [{c['status']}]" for c in claims)[:2000]
    world.works[wid] = dict(id=wid, creator_agent_id=a.id, created_tick=world.tick, revision=1, x=a.x, z=a.z,
                            title=title.strip(), text=text, history=[], claims=claims,
                            provenance_event_id=f"evt-{len(world.events):09}")
    a.skills["writing"] = a.skills.get("writing", 0) + 1
    payload.update(result="findings_written", work_id=wid, claims=len(claims))


def _compare(world, a, p, payload):
    if not all(isinstance(p[k], str) and p[k].strip() for k in ("first", "second")):
        return "invalid subjects"
    rows = {}
    for key in ("first", "second"):
        needle = p[key].lower()
        rows[p[key]] = [{"property": e["property"], "value": e["value"], "status": e["status"], "n": e["count"]}
                        for e in ensure(a)["practical"] if needle in e["subject"].lower()][:8]
    a.memories.append({"tick": world.tick, "comparison": rows})
    a.memories[:] = a.memories[-40:]
    _add(world, a, "episodic", {"text": f"compared {p['first']} with {p['second']}", "importance": 0.3,
                                "tags": tokens(p["first"], p["second"]), "event": _event_id(world), "confidence": 0.9})
    payload.clear()
    payload.update(result="compared", entries=sum(len(v) for v in rows.values()))


def registry(world=None):
    table = {"HYPOTHESIZE": ({"statement", "subject"}, _hypothesize, 6.0), "ASSESS": ({"entry_id", "verdict", "evidence_id"}, _assess, 6.0),
             "SHARE_KNOWLEDGE": ({"target_id", "entry_id"}, _share, 3.0), "WRITE_FINDINGS": ({"title", "entry_ids"}, _write_findings, 6.0),
             "COMPARE": ({"first", "second"}, _compare, 6.0)}
    return {name: Spec(frozenset(req), run, min_age=age_min) for name, (req, run, age_min) in table.items()}


TOOL_PARAMETERS = {
    "HYPOTHESIZE": {"statement": {"type": "string", "maxLength": 300}, "subject": {"type": "string", "maxLength": 80}},
    "ASSESS": {"entry_id": {"type": "string"}, "verdict": {"type": "string", "enum": ["supported", "contradicted", "uncertain"]},
               "evidence_id": {"type": "string"}},
    "SHARE_KNOWLEDGE": {"target_id": {"type": "string"}, "entry_id": {"type": "string"}},
    "WRITE_FINDINGS": {"title": {"type": "string", "maxLength": 100}, "entry_ids": {"type": "string", "maxLength": 120}},
    "COMPARE": {"first": {"type": "string", "maxLength": 80}, "second": {"type": "string", "maxLength": 80}},
}
TOOL_DESCRIPTIONS = {
    "HYPOTHESIZE": "Privately record an explanation you suspect about a subject. It stays unverified until you assess it against evidence.",
    "ASSESS": "Revise your confidence in one of your remembered entries (by id) as supported, contradicted or uncertain, citing a different remembered observation or event as evidence.",
    "SHARE_KNOWLEDGE": "Tell a nearby inhabitant one of your remembered findings (by entry id). They record it as a claim, not as established fact.",
    "WRITE_FINDINGS": "Write a text recording 1-5 of your remembered findings (comma-separated entry ids) so others may read it later.",
    "COMPARE": "Recall what you have observed about two subjects (for example material names) side by side.",
}


def tool_filters():
    recalled = lambda obs: obs.get("recalled", [])
    structured = lambda obs: [r for r in recalled(obs) if r["kind"] in ("practical", "cultural")]
    near = lambda obs, a: [b for b in obs["others"] if abs(b["x"] - a["x"]) + abs(b["z"] - a["z"]) <= 2 and b.get("age_years", 25) >= 3]
    return {"HYPOTHESIZE": lambda obs, a: a.get("age_years", 25) >= 6,
            "ASSESS": lambda obs, a: len(recalled(obs)) >= 2,
            "SHARE_KNOWLEDGE": lambda obs, a: bool(structured(obs)) and bool(near(obs, a)),
            "WRITE_FINDINGS": lambda obs, a: bool(structured(obs)),
            "COMPARE": lambda obs, a: bool(structured(obs))}


# ---------------------------------------------------------------- metrics
def knowledge_metrics(world):
    """Measured counts only: nothing here judges whether a belief is true."""
    totals = dict(practical=0, hypotheses=0, cultural=0, procedural=0, episodic=0, contradictions=0, revisions=0)
    observers = {}
    transfers = {"hearsay": 0, "witnessed": 0, "written": 0}
    for aid, agent in world.agents.items():
        ltm = agent.ltm
        if not ltm:
            continue
        for category in ("practical", "hypotheses", "cultural", "procedural", "episodic"):
            totals[category] += len(ltm[category])
        for entry in ltm["cultural"]:
            if entry.get("status") == "contradicted":
                totals["contradictions"] += 1
            kind = (entry.get("origin") or {}).get("type")
            transfers["written" if kind == WRITTEN else "hearsay"] += 1
        for entry in ltm["practical"] + ltm["cultural"] + ltm["hypotheses"]:
            totals["revisions"] += len(entry.get("revisions", []))
        for entry in ltm["practical"]:
            if any(o["type"] == WITNESSED for o in entry["origins"]):
                transfers["witnessed"] += 1
            if entry.get("independent"):
                observers.setdefault((entry["subject"], entry["property"], entry["cond"]), set()).add(aid)
    verified = sum(1 for who in observers.values() if len(who) >= 2)
    return dict(totals, transfers=transfers, independently_reproduced_findings=verified,
                recalls=world.scheduler.data["totals"].get("memory_recalls", 0),
                recalled_items=world.scheduler.data["totals"].get("memory_items", 0))
