"""geography-v1 is frozen, and every production caller asks the world which generator it was created with."""
import ast
import hashlib
import json
from pathlib import Path
import pytest
from caitanya import nature
from caitanya.engine import World
from conftest import IdleBackend

ROOT = Path(__file__).resolve().parent.parent
GOLDEN = json.loads((ROOT / "tests" / "fixtures" / "geography_v1_golden.json").read_text(encoding="utf-8"))


def tiles_digest(seed, width, depth, **kw):
    h = hashlib.sha256()
    for x in range(0, width, 2):
        for z in range(0, depth, 2):
            h.update(json.dumps(nature.geography(x, z, width, depth, seed, **kw), sort_keys=True).encode())
    return h.hexdigest()


def test_geography_v1_is_byte_for_byte_what_it_was_before_the_dispatch_existed():
    """The golden digests were computed from the function as it stood on main before this change."""
    for key, want in GOLDEN.items():
        seed, size = key.split(":")
        width, depth = (int(v) for v in size.split("x"))
        assert tiles_digest(int(seed), width, depth) == want, key
        assert tiles_digest(int(seed), width, depth, version="geography-v1") == want, key


def test_an_unknown_generator_is_refused_not_silently_replaced():
    with pytest.raises(ValueError):
        nature.geography(5, 5, 64, 64, 1, version="geography-v99")


def test_a_world_uses_the_generator_recorded_in_its_genesis_plan(monkeypatch):
    w = World(seed=3, population=2, backend=IdleBackend())
    assert w.geography_version == "geography-v1"
    assert w.terrain_at(40, 40) == nature.geography(40, 40, w.width, w.depth, w.seed)
    monkeypatch.setitem(nature.GEOGRAPHY_GENERATORS, "test-flat", lambda x, z, width, depth, seed: dict(biome="grassland", elevation=1.0, walkable=True))
    w.manifest["genesis"]["generators"]["terrain"] = "test-flat"
    assert w.terrain_at(40, 40) == dict(biome="grassland", elevation=1.0, walkable=True)
    del w.manifest["genesis"]                       # a world with no genesis record is a v1 world
    assert w.geography_version == "geography-v1"


def test_no_production_code_bypasses_the_world_when_it_has_one():
    """Every call of geography() in caitanya/ and fauna/ passes a version (only genesis does, from its own plan); the rest use world.terrain_at."""
    offenders = []
    for folder in ("caitanya", "fauna"):
        for path in (ROOT / folder).rglob("*.py"):
            for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
                if isinstance(node, ast.Call):
                    f = node.func
                    name = f.id if isinstance(f, ast.Name) else f.attr if isinstance(f, ast.Attribute) else ""
                    if name == "geography" and len(node.args) + len(node.keywords) < 6 and path.name != "nature.py":
                        offenders.append(f"{path.relative_to(ROOT)}:{node.lineno}")
    assert not offenders, offenders
