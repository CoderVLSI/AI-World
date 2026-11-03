"""Open-ended physical experimentation.

Inhabitants can examine, handle, strike, combine, separate, heat, cool, rub and
load-test objects.  The engine only evaluates physics over material properties
(see materials.py); it never matches a product name, never tells anyone what to
invent, and treats failure (cracking, burning, snapping, a bond giving way) as a
real consequence.  Mass is conserved: whatever leaves an object becomes another
object, or is recorded in ``world.ledger`` as dust or combustion products.

Everything an action may do is validated before any state changes, and no
generated text is ever executed.
"""
import copy
import math

from . import materials as M
from .actions import Spec
from .nature import climate
from .physiology import unit_interval

MAX_ID_LIST = 4
TESTS = ("bend", "pull", "drop", "cut", "pound")
METHODS = ("lash", "clay_bond", "stack")
HANDLE_MIN_G = 300
MAX_OBJECT_EVENTS = 12
RAIN_MOISTURE, CLOUD_MOISTURE, CLEAR_MOISTURE = 0.45, 0.22, 0.10
MOISTURE_RATE_PER_HOUR = 0.03


# ------------------------------------------------------------------ helpers
def _roll(world, label, key):
    return unit_interval(world.seed, world.tick, label, key)


def ambient_c(world):
    return climate(world.tick, world.biology.days_per_tick)["temperature_c"]


def _daylight(world):
    hour = climate(world.tick, world.biology.days_per_tick)["hour"]
    return max(0.0, math.sin((hour - 6) / 12 * math.pi)) if 6 <= hour <= 18 else 0.0


def _near(a, obj, distance=1):
    return abs(obj["x"] - a.x) + abs(obj["z"] - a.z) <= distance


def reachable(a, obj):
    return obj["held_by"] == a.id or (obj["held_by"] is None and _near(a, obj))


def total_mass_g(obj):
    return sum(c["mass_g"] for c in obj["components"])


def carried_g(world, aid):
    return sum(total_mass_g(o) for o in world.objects.values() if o["held_by"] == aid)


def _spend(world, a, base):
    return world._spend_energy(a, base)


def _log(world, obj, op, a, inputs=()):
    obj["provenance"].append({"tick": world.tick, "op": op, "agent": a.id, "inputs": list(inputs),
                              "event": f"evt-{len(world.events):09}"})
    obj["provenance"][:] = obj["provenance"][-MAX_OBJECT_EVENTS:]


# ------------------------------------------------------ derived properties
def comp_hardness(c):
    h = M.props(c["material"])["hardness"]
    st = c["state"]
    if st.get("fired"):
        h = max(h, 5.0)
    return h * (1 - 0.4 * st.get("charred", 0))


def comp_toughness(c):
    t = M.props(c["material"])["toughness"]
    st = c["state"]
    if st.get("fired"):
        t = max(t, 28)
    return t * (1 - 0.5 * st.get("charred", 0)) * c["integrity"] / 100


def comp_tensile(c):
    t = M.props(c["material"])["tensile"]
    st = c["state"]
    if st.get("fired"):
        t = max(t, 14)
    return t * (1 - 0.6 * st.get("charred", 0)) * c["integrity"] / 100


def comp_flex(c):
    p = M.props(c["material"])
    return 0 if c["state"].get("fired") else p["flexibility"] * (1 - 0.7 * c["state"].get("charred", 0))


def mass_kg(c):
    return c["mass_g"] / 1000.0


def comp_edge(c):
    return c["edge"]["sharpness"] if c.get("edge") else 0.0


def bond_strength(obj, bond):
    """Strength of an attachment, which can change as binders dry, cure, fire or fray."""
    if bond["method"] == "stack":
        return 0.0
    binder = next((c for c in obj["components"] if c["cid"] == bond.get("binder")), None)
    if bond["method"] == "lash":
        return round(bond["strength"] * (binder["integrity"] / 100 if binder else 1), 3)
    if binder is None:
        return 0.0
    base = 45.0 if binder["state"].get("fired") else 14.0 if binder["moisture"] <= 0.10 else 3.0
    return round(base * bond["fit"] * binder["integrity"] / 100, 3)


def weakest_bond(obj):
    bonds = [(bond_strength(obj, b), i) for i, b in enumerate(obj["bonds"])]
    return min(bonds) if bonds else (None, None)


def has_handle(obj, edge_cid):
    """True when the edge-bearing component is attached to a substantial separate component."""
    sizes = {c["cid"]: c["mass_g"] for c in obj["components"]}
    for b in obj["bonds"]:
        if b["method"] == "stack":
            continue
        for me, other in ((b["a"], b["b"]), (b["b"], b["a"])):
            if me == edge_cid and sizes.get(other, 0) >= HANDLE_MIN_G and other != b.get("binder"):
                return True
    return False


def signature(obj):
    """Generalisable description (no ids) so findings transfer between inhabitants."""
    if obj["kind"] == "fire":
        return "fire"
    parts = sorted(f"{c['material']}[{_form(c)}]" for c in obj["components"])
    methods = sorted({b["method"] for b in obj["bonds"]})
    return "+".join(parts) + (" via " + "/".join(methods) if methods else "")


def _form(c):
    bits = [c["form"]]
    if comp_edge(c) >= 20:
        bits.append("edged")
    if c["state"].get("fired"):
        bits.append("fired")
    if c["state"].get("charred", 0) >= 0.5:
        bits.append("charred")
    return ",".join(bits)


# --------------------------------------------------------- object creation
def _new_id(world):
    oid = f"obj-{world.next_object_id:06}"
    world.next_object_id += 1
    return oid


def _component(world, oid, obj, material, mass_g, form="raw", quality=None, moisture=None, edge=None,
               flaw_scale=1.0, state=None):
    cid = obj["next_cid"]
    obj["next_cid"] += 1
    p = M.props(material)
    key = f"{oid}:{cid}"
    return {"cid": cid, "material": material, "mass_g": round(mass_g, 3), "form": form,
            "quality": round(_roll(world, "quality", key), 3) if quality is None else quality,
            "flaw": round(_roll(world, "flaw", key) * flaw_scale, 3), "integrity": 100.0,
            "moisture": p["moisture0"] if moisture is None else round(moisture, 3),
            "temperature_c": ambient_c(world), "edge": edge, "state": dict(state or {})}


def _object(world, kind, creator, x, z, held_by=None):
    oid = _new_id(world)
    obj = {"id": oid, "kind": kind, "x": x, "z": z, "held_by": held_by, "creator": creator, "owner": creator,
           "created_tick": world.tick, "components": [], "bonds": [], "tests": [], "provenance": [],
           "next_cid": 0}
    world.objects[oid] = obj
    return obj


def _place(world, a, obj, want_held=True):
    """Hold the object if the carrying limit allows, otherwise leave it where the inhabitant stands."""
    if want_held and carried_g(world, a.id) + total_mass_g(obj) <= world.autonomy.experiments.carry_limit_g:
        obj["held_by"] = a.id
    else:
        obj["held_by"] = None
    obj["x"], obj["z"] = a.x, a.z


def _connected_groups(obj):
    parent = {c["cid"]: c["cid"] for c in obj["components"]}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x
    for b in obj["bonds"]:
        for other in (b["b"], b.get("binder")):
            if other is not None and other in parent and b["a"] in parent:
                parent[find(other)] = find(b["a"])
    groups = {}
    for c in obj["components"]:
        groups.setdefault(find(c["cid"]), []).append(c["cid"])
    return sorted(groups.values(), key=lambda g: g[0])


def _split(world, a, obj):
    """Split an object whose bonds no longer connect all of its components."""
    groups = _connected_groups(obj)
    if len(groups) <= 1:
        return [obj]
    result = [obj]
    comps = {c["cid"]: c for c in obj["components"]}
    all_bonds = obj["bonds"]
    obj["components"] = [comps[c] for c in groups[0]]
    obj["bonds"] = [b for b in all_bonds if b["a"] in groups[0]]
    for group in groups[1:]:
        piece = _object(world, "assembly" if len(group) > 1 else "piece", obj["creator"], obj["x"], obj["z"],
                        obj["held_by"])
        piece["owner"], piece["next_cid"] = obj["owner"], obj["next_cid"]
        piece["components"] = [comps[c] for c in group]
        piece["bonds"] = [b for b in all_bonds if b["a"] in group]
        piece["provenance"] = copy.deepcopy(obj["provenance"])
        _log(world, piece, "split_from", a, [obj["id"]])
        result.append(piece)
    for o in result:
        o["kind"] = "assembly" if len(o["components"]) > 1 else "piece"
    return result


def _remove_components(world, a, obj, cids):
    obj["components"] = [c for c in obj["components"] if c["cid"] not in cids]
    obj["bonds"] = [b for b in obj["bonds"]
                    if b["a"] not in cids and b["b"] not in cids and b.get("binder") not in cids]
    if not obj["components"]:
        del world.objects[obj["id"]]
        return []
    return _split(world, a, obj)


def _fracture(world, a, obj, comp, pieces, dust_fraction, hardness_ratio, label="fracture"):
    """Break one single-component object into fragments.  Mass is conserved (dust is ledgered)."""
    material = comp["material"]
    dust = comp["mass_g"] * dust_fraction
    usable = comp["mass_g"] - dust
    weights = [0.5 + _roll(world, "fragment", f"{obj['id']}:{comp['cid']}:{i}") for i in range(pieces)]
    total = sum(weights)
    out = []
    for i, weight in enumerate(weights):
        frag = _object(world, "piece", obj["creator"], a.x, a.z)
        frag["owner"] = obj["owner"]
        edge = M.fracture_edge_sharpness(material, comp["quality"], hardness_ratio)
        c = _component(world, frag["id"], frag, material, usable * weight / total, form="fragment",
                       quality=comp["quality"], moisture=comp["moisture"], flaw_scale=0.6,
                       edge={"sharpness": edge} if edge >= 5 else None, state=comp["state"])
        c["temperature_c"] = comp["temperature_c"]
        frag["components"].append(c)
        _place(world, a, frag)
        _log(world, frag, label, a, [obj["id"]])
        out.append(frag)
    world.ledger["dispersed_g"] = round(world.ledger["dispersed_g"] + dust, 3)
    return out, dust


# ------------------------------------------------------------- observation
def _observe_comp(c):
    p = M.props(c["material"])
    return {"material": c["material"], "form": c["form"], "mass_g": round(c["mass_g"]),
            "hardness": round(comp_hardness(c) * 2) / 2, "density": p["density"],
            "flexibility": round(comp_flex(c) / 5) * 5, "moisture": round(c["moisture"] * 20) / 20,
            "temperature_c": round(c["temperature_c"]), "sharpness": round(comp_edge(c) / 5) * 5,
            "grain": M.grain_label(c["quality"]) if p["fracture"] in ("conchoidal", "splintery") else "none",
            "cracks_visible": c["flaw"] > 0.6, "colour": p["color"]}


def observable_objects(world, a):
    """Nearby or carried objects as the inhabitant perceives them (hidden values omitted)."""
    out = []
    for obj in sorted(world.objects.values(), key=lambda o: o["id"]):
        if obj["held_by"] not in (None, a.id) or (obj["held_by"] is None and not _near(a, obj, 8)):
            continue
        if obj["kind"] == "fire":
            remaining = max(0.0, obj["burn_ticks"]) * world.hours_per_tick
            out.append({"id": obj["id"], "kind": "fire", "x": obj["x"], "z": obj["z"],
                        "burning": world.tick >= obj["start_tick"], "hours_left": round(remaining, 1)})
            continue
        out.append({"id": obj["id"], "kind": obj["kind"], "held": obj["held_by"] == a.id,
                    "x": obj["x"] if obj["held_by"] is None else a.x, "z": obj["z"] if obj["held_by"] is None else a.z,
                    "mass_g": round(total_mass_g(obj)), "owner": obj["owner"],
                    "parts": [f"{c['material']}:{_form(c)}:{round(c['mass_g'])}g" for c in obj["components"]],
                    "attachments": sorted({b["method"] for b in obj["bonds"]})})
    return out[:14]


# ------------------------------------------------------------ action helpers
def _text_id(p, key):
    return isinstance(p.get(key), str) and p[key].strip() != ""


def _get(world, a, oid, allow_fire=False):
    obj = world.objects.get(oid) if isinstance(oid, str) else None
    if obj is None:
        return None, "unknown object"
    if obj["kind"] == "fire" and not allow_fire:
        return None, "a fire cannot be handled"
    if not reachable(a, obj):
        return None, "object out of reach"
    return obj, None


def _parse_ids(text, limit=MAX_ID_LIST):
    if not isinstance(text, str):
        return None
    ids = [t.strip() for t in text.split(",") if t.strip()]
    return ids if 1 <= len(ids) <= limit and len(set(ids)) == len(ids) else None


def _int_in(p, key, low, high):
    return type(p.get(key)) is int and low <= p[key] <= high


def _single(obj):
    return len(obj["components"]) == 1


# ------------------------------------------------------------------ actions
def _pick(world, a, p, payload):
    kind = p["kind"]
    if not isinstance(kind, str) or kind not in M.MATERIALS or M.props(kind).get("liquid"):
        return "unknown or unhandleable material"
    if a.inventory.get(kind, 0) < 1:
        return "no such material carried"
    if carried_g(world, a.id) + M.props(kind)["unit_g"] > world.autonomy.experiments.carry_limit_g:
        return "carrying too much"
    if not _spend(world, a, 1):
        return "insufficient energy"
    a.inventory[kind] -= 1
    obj = _object(world, "piece", a.id, a.x, a.z, held_by=a.id)
    obj["components"].append(_component(world, obj["id"], obj, kind, M.props(kind)["unit_g"]))
    _log(world, obj, "picked", a)
    payload.update(result="piece_held", object_id=obj["id"])


def _stow(world, a, p, payload):
    obj = world.objects.get(p["object_id"]) if isinstance(p["object_id"], str) else None
    if obj is None or obj["held_by"] != a.id or obj["kind"] == "fire":
        return "not holding that object"
    c = obj["components"][0] if _single(obj) else None
    if c is None or c["form"] != "raw" or abs(c["mass_g"] - M.props(c["material"])["unit_g"]) > 0.5 or c["state"]:
        return "only an unmodified whole piece can be stowed"
    if not _spend(world, a, 1):
        return "insufficient energy"
    a.inventory[c["material"]] = a.inventory.get(c["material"], 0) + 1
    del world.objects[obj["id"]]
    payload.update(result="stowed", material=c["material"])


def _take(world, a, p, payload):
    obj, err = _get(world, a, p["object_id"])
    if err:
        return err
    if obj["held_by"] == a.id:
        return "already holding it"
    if any(bond_strength(obj, b) <= 0 for b in obj["bonds"]) or \
            (len(obj["components"]) > 1 and not obj["bonds"]):
        return "a loose stack cannot be lifted as one object"
    if carried_g(world, a.id) + total_mass_g(obj) > world.autonomy.experiments.carry_limit_g:
        return "too heavy to carry with what you hold"
    if not _spend(world, a, 1):
        return "insufficient energy"
    obj["held_by"], obj["x"], obj["z"] = a.id, a.x, a.z
    _log(world, obj, "taken", a)
    payload["result"] = "taken"


def _drop(world, a, p, payload):
    obj = world.objects.get(p["object_id"]) if isinstance(p["object_id"], str) else None
    if obj is None or obj["held_by"] != a.id:
        return "not holding that object"
    obj["held_by"], obj["x"], obj["z"] = None, a.x, a.z
    _log(world, obj, "dropped", a)
    payload["result"] = "dropped"


def _inspect(world, a, p, payload):
    subject = p["subject"]
    if not isinstance(subject, str):
        return "invalid subject"
    facts, seen = [], []
    if subject.startswith("inventory:"):
        kind = subject.split(":", 1)[1]
        if kind not in M.MATERIALS or a.inventory.get(kind, 0) < 1:
            return "no such material carried"
        material = kind
        seen = [{"material": kind, "typical_unit_g": M.props(kind)["unit_g"], "colour": M.props(kind)["color"],
                 "hardness": M.props(kind)["hardness"], "density": M.props(kind)["density"],
                 "flexibility": M.props(kind)["flexibility"]}]
    elif subject in world.resources:
        node = world.resources[subject]
        if abs(node["x"] - a.x) + abs(node["z"] - a.z) > 1:
            return "resource out of reach"
        material = node["kind"]
        seen = [{"material": material, "typical_unit_g": M.props(material)["unit_g"], "colour": M.props(material)["color"],
                 "hardness": M.props(material)["hardness"], "density": M.props(material)["density"],
                 "flexibility": M.props(material)["flexibility"]}]
    else:
        obj, err = _get(world, a, subject, allow_fire=True)
        if err:
            return err
        if obj["kind"] == "fire":
            seen = [{"kind": "fire", "burning": world.tick >= obj["start_tick"],
                     "hours_left": round(max(0, obj["burn_ticks"]) * world.hours_per_tick, 1)}]
        else:
            seen = [_observe_comp(c) for c in obj["components"]]
            seen.append({"attachments": [{"method": b["method"], "feels_secure": bond_strength(obj, b) > 0}
                                         for b in obj["bonds"]]})
    if not _spend(world, a, 1):
        return "insufficient energy"
    for entry in seen:
        if "material" in entry:
            m = entry["material"]
            facts += [{"subject": m, "property": "hardness", "value": entry["hardness"]},
                      {"subject": m, "property": "density", "value": entry["density"]},
                      {"subject": m, "property": "flexibility", "value": entry["flexibility"]}]
    payload.update(result="inspected", observed=seen, facts=facts)


def _blow_efficiency(ratio):
    """Energy transferred into the target: collapses when the striker is much softer than the target."""
    r = M.clamp(ratio, 0.0, 2.0)
    return 0.5 * r * r if r < 1 else 0.5 * (1 + 0.65 * (r - 1))


def _strike(world, a, p, payload):
    striker, err = _get(world, a, p["striker"])
    if err:
        return err
    target, err = _get(world, a, p["target"])
    if err:
        return err
    if striker is target:
        return "an object cannot strike itself"
    if not _int_in(p, "force", 1, 10):
        return "force must be 1-10"
    if not _single(target):
        return "target must be a single piece"
    head = max(striker["components"], key=lambda c: (comp_hardness(c), c["mass_g"]))
    tc = target["components"][0]
    if not _spend(world, a, 2 + 0.5 * p["force"]):
        return "insufficient energy"
    hs, ht = comp_hardness(head), comp_hardness(tc)
    ratio_h = hs / max(0.5, ht)
    impact = p["force"] * math.sqrt(total_mass_g(striker) / 1000) * _blow_efficiency(ratio_h)
    resist = comp_toughness(tc) / 10 * math.sqrt(mass_kg(tc)) * (1 - 0.5 * tc["flaw"])
    resist *= 1 + (tc["moisture"] if M.props(tc["material"])["porous"] else 0)
    r = impact / max(1e-6, resist)
    produced, dust = [], 0.0
    if r < 0.5:
        result = "no_effect"
    elif r < 1.0:
        result = "chipped"
        flake_g = min(400.0, tc["mass_g"] * (0.03 + 0.07 * r))
        edge = M.fracture_edge_sharpness(tc["material"], tc["quality"], ratio_h)
        flake = _object(world, "piece", a.id, a.x, a.z)
        flake["owner"] = target["owner"]
        fc = _component(world, flake["id"], flake, tc["material"], flake_g, form="flake", quality=tc["quality"],
                        moisture=tc["moisture"], flaw_scale=0.5, edge={"sharpness": edge} if edge >= 5 else None,
                        state=tc["state"])
        fc["temperature_c"] = tc["temperature_c"]
        flake["components"].append(fc)
        _place(world, a, flake)
        _log(world, flake, "chipped_from", a, [target["id"]])
        tc["mass_g"] = round(tc["mass_g"] - flake_g, 3)
        scar = 0.6 * edge
        if scar >= 5 and scar > comp_edge(tc):
            tc["edge"] = {"sharpness": round(scar, 2)}
        produced = [flake]
        _log(world, target, "struck", a, [striker["id"]])
    else:
        result = "fractured"
        pieces = 2 + min(2, int((r - 1) * 2 + tc["flaw"] * 2))
        produced, dust = _fracture(world, a, target, tc, pieces, 0.02 + 0.02 * min(r, 3), ratio_h)
        del world.objects[target["id"]]
    wear = 0.0
    if r >= 0.5:
        wear = (0.01 * r if hs < ht else 0.001) * head["mass_g"]
        head["mass_g"] = round(head["mass_g"] - wear, 3)
        world.ledger["dispersed_g"] = round(world.ledger["dispersed_g"] + wear, 3)
        if hs < ht and head.get("edge"):
            head["edge"]["sharpness"] = round(max(0.0, head["edge"]["sharpness"] - 5 * r), 2)
        head["integrity"] = round(max(1.0, head["integrity"] - (3 * r if hs < ht else 0.3 * r)), 2)
        _log(world, striker, "used_as_striker", a, [target["id"]])
    label = f"{tc['material']}[grain={M.grain_label(tc['quality'])}]" if M.props(tc["material"])["fracture"] in (
        "conchoidal", "splintery") else tc["material"]
    facts = [{"subject": label, "property": "strike_outcome", "value": result,
              "conditions": {"force": p["force"], "striker": head["material"]}}]
    for piece in produced:
        s = comp_edge(piece["components"][0])
        facts.append({"subject": label, "property": "fresh_edge_sharpness", "value": round(s / 5) * 5})
    payload.update(result=result, impact_to_resistance=round(r, 2), produced=[o["id"] for o in produced],
                   dispersed_g=round(dust + wear, 2), facts=facts)


def _combine(world, a, p, payload):
    ids = _parse_ids(p["parts"])
    if ids is None or len(ids) < 2:
        return "parts must list 2-4 distinct object ids"
    method = p["method"]
    if method not in METHODS:
        return "unknown attachment method"
    parts = []
    for oid in ids:
        obj, err = _get(world, a, oid)
        if err:
            return err
        parts.append(obj)
    wanted = {"lash": "plant_fiber", "clay_bond": "clay"}.get(method)
    binder = None
    if wanted:
        for obj in reversed(parts):
            if _single(obj) and obj["components"][0]["material"] == wanted and not obj["bonds"]:
                binder = obj
                break
        if binder is None:
            return f"{method} needs a loose {wanted} piece among the parts"
        body = [o for o in parts if o is not binder]
        if len(body) < 2:
            return "need at least two objects besides the binder"
    else:
        body = parts
    if sum(len(o["components"]) for o in parts) > world.autonomy.experiments.max_components:
        return "assembly would exceed the component limit"
    if not _spend(world, a, 3):
        return "insufficient energy"
    merged = _object(world, "assembly", a.id, a.x, a.z)
    mapping = {}
    held = any(o["held_by"] == a.id for o in parts)
    for obj in parts:
        for c in obj["components"]:
            new = copy.deepcopy(c)
            new["cid"] = merged["next_cid"]
            merged["next_cid"] += 1
            mapping[(obj["id"], c["cid"])] = new["cid"]
            merged["components"].append(new)
        for b in obj["bonds"]:
            nb = dict(b, a=mapping[(obj["id"], b["a"])], b=mapping[(obj["id"], b["b"])])
            if b.get("binder") is not None:
                nb["binder"] = mapping[(obj["id"], b["binder"])]
            merged["bonds"].append(nb)
        merged["provenance"] += obj["provenance"]
    merged["provenance"][:] = merged["provenance"][-MAX_OBJECT_EVENTS:]
    heads = [mapping[(o["id"], max(o["components"], key=lambda c: c["mass_g"])["cid"])] for o in body]
    binder_cid = mapping[(binder["id"], binder["components"][0]["cid"])] if binder else None
    comps = {c["cid"]: c for c in merged["components"]}
    links = len(heads) - 1
    for i in range(links):
        left, right = comps[heads[i]], comps[heads[i + 1]]
        small, large = sorted((left["mass_g"], right["mass_g"]))
        fit = M.clamp(1 - abs(math.log10(max(small, 1) / max(large, 1)) - math.log10(0.15)) / 1.6, 0.15, 1.0)
        bond = {"a": heads[i], "b": heads[i + 1], "method": method, "binder": binder_cid, "fit": round(fit, 3),
                "strength": 0.0}
        if method == "lash":
            fibre = comps[binder_cid]
            jitter = 0.85 + 0.3 * _roll(world, "lash", f"{merged['id']}:{i}")
            material_strength = comp_tensile(fibre) * min(1.0, fibre["mass_g"] / links / 150)
            bond["strength"] = round(material_strength * (0.3 + 0.7 * fit) * jitter *
                                     (1 - 0.8 * max(0.0, fibre["moisture"] - 0.3)), 3)
        merged["bonds"].append(bond)
    for obj in parts:
        del world.objects[obj["id"]]
    merged["owner"] = a.id
    if held and carried_g(world, a.id) + total_mass_g(merged) <= world.autonomy.experiments.carry_limit_g:
        merged["held_by"] = a.id
    _log(world, merged, "combined", a, ids)
    strengths = [bond_strength(merged, b) for b in merged["bonds"] if b["method"] == method]
    payload.update(result="assembled", object_id=merged["id"], method=method, parts=len(merged["components"]),
                   facts=[{"subject": signature(merged), "property": "attachment_feels_secure",
                           "value": min(strengths, default=0) > 5}])


def _separate(world, a, p, payload):
    obj, err = _get(world, a, p["object_id"])
    if err:
        return err
    if len(obj["components"]) < 2:
        return "nothing to take apart"
    if not _spend(world, a, 2):
        return "insufficient energy"
    for c in obj["components"]:
        if any(b.get("binder") == c["cid"] for b in obj["bonds"]) and c["material"] == "plant_fiber":
            c["integrity"] = round(max(10.0, c["integrity"] - 25), 2)       # untying frays the fibre
    obj["bonds"] = []
    parts = _split(world, a, obj)
    for part in parts:
        _log(world, part, "separated", a, [obj["id"]])
    payload.update(result="separated", parts=[o["id"] for o in parts])


def _fire_at(world, a, fid):
    fire = world.objects.get(fid) if isinstance(fid, str) else None
    if fire is None or fire["kind"] != "fire":
        return None, "unknown fire"
    if not _near(a, fire, 1):
        return None, "fire out of reach"
    if fire["burn_ticks"] <= 0:
        return None, "the fire has burned out"
    return fire, None


def _burn_energy_j(comp):
    p = M.props(comp["material"])
    if not p["ignition_c"]:
        return 0.0
    return mass_kg(comp) * p["fuel_mj_kg"] * 1e6 * M.clamp(1 - 2 * comp["moisture"], 0.0, 1.0) * \
        (1 + 0.8 * comp["state"].get("charred", 0))


def _feed(world, fire, energy_j):
    fire["burn_ticks"] = round(fire["burn_ticks"] + energy_j / M.FIRE_POWER_W / 3600 / world.hours_per_tick, 4)


def _heat(world, a, p, payload):
    obj, err = _get(world, a, p["subject"])
    if err:
        return err
    if not _int_in(p, "minutes", 5, 240):
        return "minutes must be 5-240"
    source = p["source"]
    if not isinstance(source, str):
        return "invalid heat source"
    hpt = world.hours_per_tick
    fire = None
    if source == "sun":
        glow = _daylight(world) * (0.3 if climate(world.tick, world.biology.days_per_tick)["weather"] == "rain" else 1.0)
        target_c, coupling, hours = ambient_c(world) + M.SUN_BONUS_C * glow, M.AIR_COUPLING_W_K, p["minutes"] / 60
    else:
        fire, err = _fire_at(world, a, source)
        if err:
            return err
        if world.tick < fire["start_tick"]:
            return "the fire has not taken hold yet"
        target_c, coupling = fire["temperature_c"], M.FIRE_COUPLING_W_K
        hours = min(p["minutes"] / 60, fire["burn_ticks"] * hpt)
    if not _spend(world, a, 2):
        return "insufficient energy"
    ticks = max(1, math.ceil(hours / hpt))
    a.busy_until_tick = world.tick + ticks
    for c in obj["components"]:
        c["pinned_until"] = a.busy_until_tick      # stays in the fire / sun for the whole activity
    effects, facts, doomed, fragments = [], [], [], []
    dry_scale = 1.0 if fire else 0.25 + 0.75 * _daylight(world)
    for c in list(obj["components"]):
        before_m = c["moisture"]
        tau = M.time_constant_hours(c["mass_g"], M.props(c["material"])["specific_heat"], coupling)
        c["temperature_c"] = round(M.approach(c["temperature_c"], target_c, hours, tau), 2)
        t_end = c["temperature_c"]
        pr = M.props(c["material"])
        dry = 0.05 * hours * (1 + max(0.0, t_end - 20) / 40) * dry_scale
        c["moisture"] = round(max(0.0, c["moisture"] - dry), 3)
        verdict = "warmed"
        if fire and pr["ignition_c"] and t_end >= pr["ignition_c"]:
            doomed.append(c)
            verdict = "burned_away"
        elif fire and pr["char_c"] and t_end >= pr["char_c"]:
            frac = M.clamp((t_end - pr["char_c"]) / 50, 0.0, 1.0)
            if frac > c["state"].get("charred", 0):
                lost = c["mass_g"] * M.CHAR_MASS_LOSS * (frac - c["state"].get("charred", 0))
                c["mass_g"] = round(c["mass_g"] - lost, 3)
                world.ledger["atmosphere_g"] = round(world.ledger["atmosphere_g"] + lost, 3)
                c["state"]["charred"] = round(frac, 3)
                c["form"] = "charred" if frac >= 0.5 else c["form"]
                verdict = "charred"
        elif fire and pr.get("fires_at_c") and t_end >= 120 and before_m > 0.12:
            fragments.append((c, "steam_cracked"))
            verdict = "shattered_by_steam"
        elif fire and pr.get("fires_at_c") and t_end >= pr["fires_at_c"]:
            c["state"]["fired"] = True
            c["form"] = "fired"
            verdict = "hardened_by_fire"
        elif fire and c["material"] == "stone" and c["flaw"] > 0.7 and t_end >= 400:
            fragments.append((c, "cracked_along_flaw"))
            verdict = "cracked_along_flaw"
        if before_m - c["moisture"] >= 0.03 and verdict == "warmed":
            verdict = "dried"
        effects.append({"material": c["material"], "temperature_c": round(t_end, -1), "result": verdict})
        facts.append({"subject": c["material"] + ("[damp]" if before_m > 0.12 else "[dry]"),
                      "property": f"effect_of_{'fire' if fire else 'sunlight'}_{p['minutes']}min",
                      "value": verdict, "conditions": {"temperature_c": round(t_end, -1)}})
    produced = []
    for c, label in fragments:
        if c in obj["components"]:
            solo = obj if _single(obj) else None
            if solo is not None:
                frags, _ = _fracture(world, a, obj, c, 2 + int(c["flaw"] * 2), 0.03, 1.0, label)
                produced += [f["id"] for f in frags]
                del world.objects[obj["id"]]
                obj = None
                break
            c["integrity"] = round(max(5.0, c["integrity"] - 40), 2)
    burned_ids = [c["cid"] for c in doomed]
    if burned_ids and obj is not None:
        ash = 0.0
        for c in doomed:
            _feed(world, fire, _burn_energy_j(c))
            ash += c["mass_g"] * M.ASH_FRACTION
            world.ledger["atmosphere_g"] = round(world.ledger["atmosphere_g"] + c["mass_g"] * (1 - M.ASH_FRACTION), 3)
        if ash > 0:
            ashp = _object(world, "piece", a.id, a.x, a.z)
            ashp["components"].append(_component(world, ashp["id"], ashp, "ash", ash, form="ash", moisture=0.0))
            _place(world, a, ashp, want_held=False)
        for part in _remove_components(world, a, obj, set(burned_ids)):
            _log(world, part, "heated", a, [source])
            produced.append(part["id"])
    elif obj is not None:
        _log(world, obj, "heated", a, [source])
    payload.update(result="heated", effects=effects, hours=round(hours, 2), busy_ticks=ticks,
                   remaining=produced, facts=facts)


def _cool(world, a, p, payload):
    obj, err = _get(world, a, p["subject"])
    if err:
        return err
    node = next((n for n in world.resources.values() if n["kind"] == "water" and n["amount"] > 0
                 and (n["x"], n["z"]) == (a.x, a.z)), None)
    if node is None and a.inventory.get("water", 0) < 1:
        return "no water available"
    if not _spend(world, a, 1):
        return "insufficient energy"
    if node is not None:
        node["amount"] -= 1            # a stream or spring is outside the tracked solid-matter balance
    else:
        a.inventory["water"] -= 1
        world.ledger["dispersed_g"] = round(world.ledger["dispersed_g"] + M.props("water")["unit_g"], 3)
    effects, facts, victims = [], [], []
    for c in obj["components"]:
        pr = M.props(c["material"])
        start_c = c["temperature_c"]
        drop = max(0.0, start_c - 15.0)
        shocked = pr["shock_c"] is not None and drop > pr["shock_c"] * (1 - 0.5 * c["flaw"]) and \
            (c["material"] != "clay" or c["state"].get("fired"))
        verdict = "cooled" if drop > 20 else "wetted"
        if shocked:
            verdict = "shattered_by_thermal_shock"
            victims.append(c)
        else:
            c["temperature_c"] = min(start_c, 15.0)
            if pr["porous"] and not c["state"].get("fired"):
                c["moisture"] = round(min(1.0, c["moisture"] + 0.15), 3)
        effects.append({"material": c["material"], "from_c": round(start_c, -1), "result": verdict})
        facts.append({"subject": c["material"], "property": "quenched_after_heating", "value": verdict,
                      "conditions": {"temperature_drop_c": round(drop, -1)}})
    produced = []
    for c in victims:
        if _single(obj):
            frags, _ = _fracture(world, a, obj, c, 2 + int(c["flaw"] * 2), 0.03, 1.0, "thermal_shock")
            produced += [f["id"] for f in frags]
            del world.objects[obj["id"]]
            obj = None
            break
        c["integrity"] = round(max(5.0, c["integrity"] - 60), 2)
    if obj is not None:
        _log(world, obj, "cooled", a)
    payload.update(result="cooled", effects=effects, remaining=produced, facts=facts)


def _rub(world, a, p, payload):
    first, err = _get(world, a, p["first"])
    if err:
        return err
    second, err = _get(world, a, p["second"])
    if err:
        return err
    beside, err = _get(world, a, p["beside"])
    if err:
        return err
    if len({first["id"], second["id"], beside["id"]}) < 3:
        return "the three objects must be different"
    if not _int_in(p, "force", 1, 10) or not _int_in(p, "minutes", 1, 30):
        return "force must be 1-10 and minutes 1-30"
    more_ids = [] if "also_beside" not in p else _parse_ids(p["also_beside"], 3)
    if more_ids is None:
        return "also_beside must list up to 3 distinct object ids"
    extras = []
    for oid in more_ids:
        if oid in (first["id"], second["id"], beside["id"]):
            return "the objects must be different"
        obj, err = _get(world, a, oid)
        if err:
            return err
        extras.append(obj)
    for obj in (first, second):
        if not _single(obj):
            return "rubbed objects must be single pieces"
    fuel = [beside] + extras
    if any(not _single(o) for o in fuel):
        return "objects beside the contact must be single pieces"
    hpt = world.hours_per_tick
    ticks = max(1, math.ceil(p["minutes"] / 60 / hpt))
    if not _spend(world, a, 0.1 * p["force"] * p["minutes"]):
        return "insufficient energy"
    a.busy_until_tick = world.tick + ticks
    c1, c2 = first["components"][0], second["components"][0]
    mu = (M.props(c1["material"])["friction"] + M.props(c2["material"])["friction"]) / 2
    dry = (M.dryness_factor(c1["moisture"]) + M.dryness_factor(c2["moisture"])) / 2
    rise = M.friction_ignition_rise_c(p["force"], p["minutes"], mu, dry)
    surface = ambient_c(world) + rise
    for c in (c1, c2):
        c["temperature_c"] = round(max(c["temperature_c"], surface), 2)
        dust = c["mass_g"] * 0.001
        c["mass_g"] = round(c["mass_g"] - dust, 3)
        world.ledger["dispersed_g"] = round(world.ledger["dispersed_g"] + dust, 3)
    tinder = beside["components"][0]
    ignition = M.props(tinder["material"])["ignition_c"]
    result = "warm_only"
    fire_id, burned = None, []
    if ignition and tinder["moisture"] <= 0.30 and surface >= ignition:
        energy = sum(_burn_energy_j(o["components"][0]) for o in fuel)
        if energy > 0:
            result = "ignited"
            fire = _object(world, "fire", a.id, a.x, a.z)
            fire.update(start_tick=world.tick + ticks, temperature_c=M.FIRE_TEMPERATURE_C, burn_ticks=0.0)
            _feed(world, fire, energy)
            fire_id = fire["id"]
            ash = 0.0
            for o in fuel:
                c = o["components"][0]
                ash += c["mass_g"] * M.ASH_FRACTION
                world.ledger["atmosphere_g"] = round(world.ledger["atmosphere_g"] + c["mass_g"] * (1 - M.ASH_FRACTION), 3)
                burned.append(o["id"])
                del world.objects[o["id"]]
            if ash > 0:
                ashp = _object(world, "piece", a.id, a.x, a.z)
                ashp["components"].append(_component(world, ashp["id"], ashp, "ash", ash, form="ash", moisture=0.0))
                _place(world, a, ashp, want_held=False)
            _log(world, fire, "kindled", a, [first["id"], second["id"]])
    elif ignition and surface >= 0.8 * ignition:
        result = "smouldering"
    for obj in (first, second):
        _log(world, obj, "rubbed", a, [(second if obj is first else first)["id"]])
    label = f"{c1['material']}-on-{c2['material']}"
    facts = [{"subject": label, "property": "surface_temperature_after_rubbing", "value": round(surface, -1),
              "conditions": {"force": p["force"], "minutes": p["minutes"],
                             "dryness": round(dry, 1)}},
             {"subject": tinder["material"], "property": "response_to_nearby_heat", "value": result,
              "conditions": {"surface_c": round(surface, -1)}}]
    payload.update(result=result, felt_surface_temperature_c=round(surface, -1), busy_ticks=ticks,
                   fire_id=fire_id, consumed=burned, facts=facts)


def _feed_fire(world, a, p, payload):
    fire, err = _fire_at(world, a, p["fire_id"])
    if err:
        return err
    fuel, err = _get(world, a, p["fuel"])
    if err:
        return err
    if not _single(fuel):
        return "fuel must be a single piece"
    c = fuel["components"][0]
    energy = _burn_energy_j(c)
    if not _spend(world, a, 1):
        return "insufficient energy"
    if energy <= 0:
        payload.update(result="would_not_burn", facts=[{"subject": c["material"], "property": "added_to_fire",
                                                          "value": "would_not_burn"}])
        return None
    _feed(world, fire, energy)
    world.ledger["atmosphere_g"] = round(world.ledger["atmosphere_g"] + c["mass_g"] * (1 - M.ASH_FRACTION), 3)
    ash = c["mass_g"] * M.ASH_FRACTION
    del world.objects[fuel["id"]]
    ashp = _object(world, "piece", a.id, a.x, a.z)
    ashp["components"].append(_component(world, ashp["id"], ashp, "ash", ash, form="ash", moisture=0.0))
    _place(world, a, ashp, want_held=False)
    payload.update(result="fuel_burning", hours_left=round(fire["burn_ticks"] * world.hours_per_tick, 1),
                   facts=[{"subject": c["material"] + ("[damp]" if c["moisture"] > 0.2 else "[dry]"),
                           "property": "burn_hours_per_kg", "value": round(
                               energy / max(1e-9, mass_kg(c)) / M.FIRE_POWER_W / 3600, 1)}])


def tool_performance(obj, mode):
    """How well an object works for a motion, derived only from its parts, edges and attachments."""
    comps = obj["components"]
    if not comps:
        return 0.0
    kg = sum(c["mass_g"] for c in comps) / 1000
    edge_comp = max(comps, key=comp_edge)
    sharp = comp_edge(edge_comp)
    handled = sharp > 0 and has_handle(obj, edge_comp["cid"])
    head = max(comps, key=comp_hardness)
    hard = comp_hardness(head)
    if mode == "cut":
        return round(sharp / 100 * (1 + 0.8 * handled), 3)
    if mode == "chop":
        return round(sharp / 100 * (1 + 0.8 * handled) * math.sqrt(kg) * 0.9, 3)
    if mode == "pound":
        return round(hard / 6 * math.sqrt(kg) * (1 + 0.5 * has_handle(obj, head["cid"])), 3)
    if mode == "dig":
        return round(kg ** 0.3 * hard / 8 * (1 + 0.5 * has_handle(obj, head["cid"])) * (1 + sharp / 200), 3)
    return 0.0


def _gather_with(world, a, p, payload):
    node = world.resources.get(p["resource_id"]) if isinstance(p["resource_id"], str) else None
    if not node or (node["x"], node["z"]) != (a.x, a.z) or node["amount"] <= 0:
        return "resource unavailable"
    tool, err = _get(world, a, p["tool_id"])
    if err:
        return err
    if tool["held_by"] != a.id:
        return "hold the tool first"
    if not _spend(world, a, 2):
        return "insufficient energy"
    mode = M.props(node["kind"])["harvest"]
    perf = tool_performance(tool, mode)
    bonus = 2 if perf >= 1.2 else 1 if perf >= 0.6 else 0
    units = min(1 + bonus, node["amount"])
    strength, index = weakest_bond(tool)
    failed = False
    if strength is not None and strength < 6 + 3 * units:
        failed = True
        units = 1
        tool["bonds"][:] = [b for i, b in enumerate(tool["bonds"]) if i != index]
        _split(world, a, tool)
    node["amount"] -= units
    a.inventory[node["kind"]] = a.inventory.get(node["kind"], 0) + units
    edge_comp = max(tool["components"], key=comp_edge) if tool["components"] else None
    if edge_comp and edge_comp.get("edge") and mode in ("cut", "chop"):
        edge_comp["edge"]["sharpness"] = round(max(0.0, edge_comp["edge"]["sharpness"] - 1.5 * units), 2)
    if tool["id"] in world.objects:
        _log(world, tool, "used_to_gather", a, [node["id"]])
    payload.update(result="tool_failed_under_load" if failed else "gathered", units=units, mode=mode,
                   performance=perf, facts=[{"subject": signature(tool), "property": f"performance_gathering_{node['kind']}",
                                             "value": round(perf, 1)},
                                            {"subject": signature(tool), "property": f"units_per_effort_on_{node['kind']}",
                                             "value": units}])


def _test(world, a, p, payload):
    obj, err = _get(world, a, p["object_id"])
    if err:
        return err
    test, mag = p["test"], p["magnitude"]
    if test not in TESTS or not _int_in(p, "magnitude", 1, 10):
        return "test must be one of " + ", ".join(TESTS) + " with magnitude 1-10"
    target = p.get("target")
    if test in ("cut", "pound"):
        if not isinstance(target, str) or target not in M.MATERIALS or M.props(target).get("liquid"):
            return "cut and pound need a target material"
    if not obj["components"]:
        return "nothing to test"
    if not _spend(world, a, 2 + 0.3 * mag):
        return "insufficient energy"
    sig = signature(obj)
    kg = total_mass_g(obj) / 1000
    result, measured, facts = "held", {}, []
    load = None
    if test == "pull":
        load = 12.0 * mag
        weak_bond, idx = weakest_bond(obj)
        # In an assembly the load travels through the attachments; a lone piece carries it itself.
        comps = [(comp_tensile(c) * mass_kg(c) ** (2 / 3) * 1.5 * (1 - 0.5 * c["flaw"]), c) for c in obj["components"]]
        weak_comp = min(comps, key=lambda t: t[0])
        candidates = []
        if weak_bond is not None and weak_bond < load:
            candidates.append((weak_bond, "bond", idx))
        if weak_bond is None and weak_comp[0] < load:
            candidates.append((weak_comp[0], "component", weak_comp[1]))
        if candidates:
            strength, kind, ref = min(candidates, key=lambda t: t[0])
            if kind == "bond":
                result = "attachment_gave_way"
                obj["bonds"].pop(ref)
                parts = _split(world, a, obj)
                measured = {"failed_at_load": round(strength, 1), "parts": [o["id"] for o in parts]}
            else:
                result = "snapped"
                if _single(obj):
                    frags, _ = _fracture(world, a, obj, ref, 2, 0.02, 1.0, "snapped_in_tension")
                    del world.objects[obj["id"]]
                    measured = {"failed_at_load": round(strength, 1), "parts": [f["id"] for f in frags]}
                else:
                    ref["integrity"] = round(max(5.0, ref["integrity"] - 50), 2)
                    measured = {"failed_at_load": round(strength, 1), "damaged": ref["material"]}
        else:
            margin = (weak_bond if weak_bond is not None else weak_comp[0]) / load
            if margin < 1.25:
                for b in obj["bonds"]:
                    if b["method"] == "lash":
                        b["strength"] = round(b["strength"] * 0.9, 3)
                result = "held_but_strained"
            measured = {"load_held": round(load, 1)}
        facts.append({"subject": sig, "property": "pull_test", "value": result,
                      "conditions": {"load": round(load, 1)}})
    elif test == "bend":
        load = 8.0 * mag
        worst = None
        for c in obj["components"]:
            cap = comp_tensile(c) * 0.8 * mass_kg(c) ** (2 / 3) * (1 - 0.5 * c["flaw"]) * 1.5
            deflection = M.clamp(load / (cap + 1) * comp_flex(c) * 3, 0, 200)
            if worst is None or cap < worst[0]:
                worst = (cap, c, deflection)
        cap, c, deflection = worst
        if load > cap:
            if comp_flex(c) < 10 and _single(obj):
                result = "snapped"
                frags, _ = _fracture(world, a, obj, c, 2, 0.02, 1.0, "snapped_in_bending")
                del world.objects[obj["id"]]
                measured = {"broke_at_load": round(cap, 1), "parts": [f["id"] for f in frags]}
            else:
                result = "bent_permanently"
                c["integrity"] = round(max(5.0, c["integrity"] - 30), 2)
                measured = {"deflection_mm": round(deflection)}
        else:
            measured = {"deflection_mm": round(deflection)}
        facts.append({"subject": sig, "property": "bend_test", "value": result,
                      "conditions": {"load": round(load, 1)}})
    elif test == "drop":
        height = 0.3 * mag
        energy = kg * 9.81 * height
        broke = []
        for c in obj["components"]:
            cap = comp_toughness(c) * mass_kg(c) ** (2 / 3) * 0.35 * (1 - 0.5 * c["flaw"])
            if comp_flex(c) < 10 and energy > cap:
                broke.append(c)
        weak_bond, idx = weakest_bond(obj)
        if broke and _single(obj):
            result = "fractured_on_impact"
            frags, _ = _fracture(world, a, obj, broke[0], 2 + int(broke[0]["flaw"] * 2), 0.03, 1.0, "dropped")
            del world.objects[obj["id"]]
            measured = {"height_m": round(height, 2), "parts": [f["id"] for f in frags]}
        elif weak_bond is not None and weak_bond < 5 * mag * math.sqrt(kg):
            result = "attachment_gave_way"
            obj["bonds"].pop(idx)
            parts = _split(world, a, obj)
            measured = {"height_m": round(height, 2), "parts": [o["id"] for o in parts]}
        else:
            measured = {"height_m": round(height, 2)}
        facts.append({"subject": sig, "property": "drop_test", "value": result,
                      "conditions": {"height_m": round(height, 1)}})
    else:  # cut / pound
        hard_target = M.props(target)["hardness"]
        work_load = 5.0 * mag
        weak_bond, idx = weakest_bond(obj)
        if test == "cut":
            edge_comp = max(obj["components"], key=comp_edge)
            sharp = comp_edge(edge_comp)
            handled = sharp > 0 and has_handle(obj, edge_comp["cid"])
            depth = 12 * (sharp / 100) * (1 + 0.8 * handled) * math.sqrt(3.0 / max(0.5, hard_target)) * (0.5 + 0.1 * mag)
            wear = 0.8 * mag * hard_target / max(1.0, comp_hardness(edge_comp)) if sharp > 0 else 0.0
            measured = {"depth_mm_per_stroke": round(depth, 1), "edge_wear": round(wear, 1), "handled": bool(handled)}
            metric = ("cut_depth_mm_into_" + target, round(depth, 1))
            if weak_bond is not None and handled and weak_bond < work_load:
                result = "attachment_gave_way"
                obj["bonds"].pop(idx)
                measured["parts"] = [o["id"] for o in _split(world, a, obj)]
            elif sharp > 0:
                edge_comp["edge"]["sharpness"] = round(max(0.0, sharp - wear), 2)
                result = "cut" if depth >= 1 else "scratched"
            else:
                result = "no_edge"
        else:
            head = max(obj["components"], key=comp_hardness)
            handled = has_handle(obj, head["cid"])
            power = comp_hardness(head) * math.sqrt(kg) * (1 + 0.5 * handled) * (0.5 + 0.1 * mag)
            crush = power / (hard_target * M.props(target)["toughness"] / 10 + 0.1)
            measured = {"crushing_ratio": round(crush, 2), "handled": bool(handled)}
            metric = ("pounding_power_vs_" + target, round(power, 1))
            if comp_hardness(head) < 0.8 * hard_target:
                result = "tool_damaged"
                head["integrity"] = round(max(5.0, head["integrity"] - 15), 2)
                lost = head["mass_g"] * 0.01
                head["mass_g"] = round(head["mass_g"] - lost, 3)
                world.ledger["dispersed_g"] = round(world.ledger["dispersed_g"] + lost, 3)
            elif weak_bond is not None and handled and weak_bond < work_load:
                result = "attachment_gave_way"
                obj["bonds"].pop(idx)
                measured["parts"] = [o["id"] for o in _split(world, a, obj)]
            else:
                result = "target_crushed" if crush >= 1.0 else "no_effect"
        facts.append({"subject": sig, "property": metric[0], "value": metric[1],
                      "conditions": {"magnitude": mag}})
        facts.append({"subject": sig, "property": f"{test}_test_vs_{target}", "value": result})
    if obj["id"] in world.objects:
        obj["tests"].append({"tick": world.tick, "agent": a.id, "test": test, "magnitude": mag,
                             "target": target, "result": result})
        obj["tests"][:] = obj["tests"][-MAX_OBJECT_EVENTS:]
    payload.update(result=result, measured=measured, facts=facts)


def _hand_over(world, a, p, payload):
    obj = world.objects.get(p["object_id"]) if isinstance(p["object_id"], str) else None
    if obj is None or obj["held_by"] != a.id:
        return "not holding that object"
    other = world.agents.get(p["target_id"]) if isinstance(p["target_id"], str) else None
    if other is None or not other.alive or other.id == a.id or abs(other.x - a.x) + abs(other.z - a.z) > 2:
        return "recipient unavailable or not nearby"
    if carried_g(world, other.id) + total_mass_g(obj) > world.autonomy.experiments.carry_limit_g:
        return "recipient cannot carry it"
    obj["held_by"], obj["owner"] = other.id, other.id
    _log(world, obj, "handed_over", a, [other.id])
    payload.update(result="handed_over", recipient=other.id)
    return None


# ---------------------------------------------------------------- dynamics
def advance_objects(world):
    """Cooling, drying, weathering, burning fires, and objects dropped by the dead."""
    if not world.objects:
        return
    hpt = world.hours_per_tick
    amb = ambient_c(world)
    weather = climate(world.tick, world.biology.days_per_tick)["weather"]
    wet_target = {"rain": RAIN_MOISTURE, "cloudy": CLOUD_MOISTURE}.get(weather, CLEAR_MOISTURE)
    for oid in sorted(world.objects):
        obj = world.objects[oid]
        holder = world.agents.get(obj["held_by"]) if obj["held_by"] else None
        if obj["held_by"] and (holder is None or not holder.alive):
            obj["held_by"] = None
            if holder is not None:
                obj["x"], obj["z"] = holder.x, holder.z
        if obj["kind"] == "fire":
            if world.tick > obj["start_tick"]:
                obj["burn_ticks"] = round(obj["burn_ticks"] - 1 - (0.5 if weather == "rain" else 0), 4)
                if obj["burn_ticks"] <= 0:
                    del world.objects[oid]
                    world.emit("fire_out", None, {"object_id": oid, "x": obj["x"], "z": obj["z"]}, "world_rule")
            continue
        if holder is not None:
            obj["x"], obj["z"] = holder.x, holder.z
        for c in obj["components"]:
            if world.tick < c.get("pinned_until", 0):
                continue
            tau = M.time_constant_hours(c["mass_g"], M.props(c["material"])["specific_heat"], M.AIR_COUPLING_W_K)
            c["temperature_c"] = round(M.approach(c["temperature_c"], amb, hpt, tau), 3)
            if M.props(c["material"])["porous"]:
                target = min(wet_target, 0.05) if c["state"].get("fired") else wet_target
                rate = 1 - math.exp(-MOISTURE_RATE_PER_HOUR * hpt)
                c["moisture"] = round(c["moisture"] + (target - c["moisture"]) * rate, 4)


# ----------------------------------------------------- registry and tooling
def registry(world=None):
    min_age = world.autonomy.experiments.min_age_years if world is not None else 6.0
    table = {
        "PICK": ({"kind"}, set(), _pick), "STOW": ({"object_id"}, set(), _stow),
        "TAKE": ({"object_id"}, set(), _take), "DROP": ({"object_id"}, set(), _drop),
        "INSPECT": ({"subject"}, set(), _inspect),
        "STRIKE": ({"striker", "target", "force"}, set(), _strike),
        "COMBINE": ({"parts", "method"}, set(), _combine), "SEPARATE": ({"object_id"}, set(), _separate),
        "HEAT": ({"subject", "source", "minutes"}, set(), _heat), "COOL": ({"subject"}, set(), _cool),
        "RUB": ({"first", "second", "force", "minutes", "beside"}, {"also_beside"}, _rub),
        "FEED_FIRE": ({"fire_id", "fuel"}, set(), _feed_fire),
        "TEST": ({"object_id", "test", "magnitude"}, {"target"}, _test),
        "GATHER_WITH": ({"resource_id", "tool_id"}, set(), _gather_with),
        "HAND_OVER": ({"target_id", "object_id"}, set(), _hand_over),
    }
    return {name: Spec(frozenset(req), run, frozenset(opt), min_age=min_age, skill="experimentation")
            for name, (req, opt, run) in table.items()}


_S = {"type": "string"}
_ID = {"type": "string", "maxLength": 40}
TOOL_PARAMETERS = {
    "PICK": {"kind": _S}, "STOW": {"object_id": _ID}, "TAKE": {"object_id": _ID}, "DROP": {"object_id": _ID},
    "INSPECT": {"subject": _ID},
    "STRIKE": {"striker": _ID, "target": _ID, "force": {"type": "integer", "minimum": 1, "maximum": 10}},
    "COMBINE": {"parts": {"type": "string", "maxLength": 120}, "method": {"type": "string", "enum": list(METHODS)}},
    "SEPARATE": {"object_id": _ID},
    "HEAT": {"subject": _ID, "source": _ID, "minutes": {"type": "integer", "minimum": 5, "maximum": 240}},
    "COOL": {"subject": _ID},
    "RUB": {"first": _ID, "second": _ID, "force": {"type": "integer", "minimum": 1, "maximum": 10},
            "minutes": {"type": "integer", "minimum": 1, "maximum": 30}, "beside": _ID,
            "also_beside": {"type": "string", "maxLength": 120}},
    "FEED_FIRE": {"fire_id": _ID, "fuel": _ID},
    "TEST": {"object_id": _ID, "test": {"type": "string", "enum": list(TESTS)},
             "magnitude": {"type": "integer", "minimum": 1, "maximum": 10}, "target": _S},
    "GATHER_WITH": {"resource_id": _ID, "tool_id": _ID},
    "HAND_OVER": {"target_id": _ID, "object_id": _ID},
}
TOOL_OPTIONAL = {"RUB": {"also_beside"}, "TEST": {"target"}}
TOOL_DESCRIPTIONS = {
    "PICK": "Take one carried unit of a material and hold it as a separate object you can handle and test.",
    "STOW": "Put an unmodified whole held piece back into your carried supplies.",
    "TAKE": "Pick up an object lying at or next to your position.",
    "DROP": "Put a held object down where you stand.",
    "INSPECT": "Examine an object, a nearby resource id, or 'inventory:<material>' to observe its properties.",
    "STRIKE": "Strike a target object with a striker object using force 1-10, then observe what happens to both.",
    "COMBINE": "Attach objects. parts is a comma-separated list of object ids. method: lash (the list must include a loose plant_fiber piece), clay_bond (must include a loose clay piece) or stack (loose, not attached).",
    "SEPARATE": "Take an assembled object apart into its components.",
    "HEAT": "Hold an object in a burning fire (source is the fire id) or in sunlight (source is 'sun') for 5-240 minutes and observe what changes.",
    "COOL": "Dunk an object in water, using carried water or a water source at your position.",
    "RUB": "Press and rub two objects together with force 1-10 for 1-30 minutes while another object lies beside the contact point; also_beside may list further objects.",
    "FEED_FIRE": "Add an object to a nearby burning fire.",
    "TEST": "Apply a load to an object to see how it behaves: bend, pull, drop, or cut/pound against a target material. magnitude 1-10.",
    "GATHER_WITH": "Gather from a resource at your position while using a held object as a tool; the result depends on how that object performs.",
    "HAND_OVER": "Give a held object to a nearby inhabitant.",
}


def tool_filters():
    """Availability predicates over an observation (keeps the offered tool list short)."""
    objs = lambda obs: obs.get("objects", [])
    held = lambda obs: [o for o in objs(obs) if o.get("held")]
    near = lambda obs, a: [o for o in objs(obs) if o.get("held") or abs(o["x"] - a["x"]) + abs(o["z"] - a["z"]) <= 1]
    carried = lambda a: any(a["inventory"].get(k, 0) > 0 for k in M.MATERIALS if not M.props(k).get("liquid"))
    return {
        "PICK": lambda obs, a: carried(a), "STOW": lambda obs, a: bool(held(obs)),
        "TAKE": lambda obs, a: any(not o.get("held") and o["kind"] != "fire" for o in near(obs, a)),
        "DROP": lambda obs, a: bool(held(obs)),
        "INSPECT": lambda obs, a: bool(near(obs, a)) or carried(a) or bool(obs["resources"]),
        "STRIKE": lambda obs, a: len([o for o in near(obs, a) if o["kind"] != "fire"]) >= 2,
        "COMBINE": lambda obs, a: len([o for o in near(obs, a) if o["kind"] != "fire"]) >= 2,
        "SEPARATE": lambda obs, a: any(o["kind"] == "assembly" for o in near(obs, a)),
        "HEAT": lambda obs, a: bool([o for o in near(obs, a) if o["kind"] != "fire"]),
        "COOL": lambda obs, a: bool([o for o in near(obs, a) if o["kind"] != "fire"]) and (
            a["inventory"].get("water", 0) > 0 or any(n["kind"] == "water" and (n["x"], n["z"]) == (a["x"], a["z"]) for n in obs["resources"])),
        "RUB": lambda obs, a: len([o for o in near(obs, a) if o["kind"] != "fire"]) >= 3,
        "FEED_FIRE": lambda obs, a: bool(held(obs)) and any(
            o["kind"] == "fire" and abs(o["x"] - a["x"]) + abs(o["z"] - a["z"]) <= 1 for o in objs(obs)),
        "TEST": lambda obs, a: bool(near(obs, a)),
        "GATHER_WITH": lambda obs, a: bool(held(obs)) and any(n["amount"] > 0 and (n["x"], n["z"]) == (a["x"], a["z"]) for n in obs["resources"]),
        "HAND_OVER": lambda obs, a: bool(held(obs)) and bool(obs["others"]),
    }
