"""The Godot client's animation rules, asset manifest and fetch script (no network, no GPU needed)."""
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
import pytest
from caitanya.engine import World

ROOT = Path(__file__).resolve().parent.parent
GODOT_DIR = ROOT / "godot"
STATES = {"idle", "walk", "rest", "talk", "work", "eat"}


def load_fetch_module():
    spec = importlib.util.spec_from_file_location("fetch_assets", ROOT / "scripts" / "fetch_assets.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def mapped_actions():
    text = (GODOT_DIR / "animation_map.gd").read_text()
    block = re.search(r"const ACTION_STATES := \{(.*?)\n\}", text, re.S).group(1)
    pairs = re.findall(r'"([a-z_]+)":\s*"([a-z]+)"', block)
    moves = re.search(r"const MOVE_ACTIONS := \[(.*?)\]", text).group(1)
    return dict(pairs), re.findall(r'"([a-z_]+)"', moves)


def test_every_animated_action_is_a_real_action_the_engine_can_record():
    """A clip may only be driven by something the simulation records; a typo here would silently never fire."""
    states, moves = mapped_actions()
    world = World()
    vocabulary = {name.lower() for name in world.registry} | {
        "move", "gather", "rest", "eat", "drink", "wait", "speak", "write", "read", "place", "reproduce",
        "withdraw_consent", "care", "give", "teach", "revise", "reflect"}
    unknown = (set(states) | set(moves)) - vocabulary
    assert not unknown, f"animation map names actions the engine does not have: {sorted(unknown)}"
    assert set(states.values()) <= STATES


def test_no_clip_state_is_invented_for_behaviour_the_simulation_cannot_produce():
    text = (GODOT_DIR / "animation_map.gd").read_text().lower()
    states, _ = mapped_actions()
    for forbidden in ("fight", "hunt", "attack", "kill", "run", "pray", "meditat", "worship"):
        assert forbidden not in set(states.values()) and forbidden not in set(states), forbidden
    assert "meditat" not in text.replace("deliberately does not label", "")      # the pose is neutral, never named as such


def test_asset_manifest_is_complete_and_only_uses_known_states():
    manifest = json.loads((GODOT_DIR / "assets" / "manifest.json").read_text())
    assert manifest["characters"]
    for key, c in manifest["characters"].items():
        for field in ("sketchfab_uid", "title", "author", "license", "file", "raw_height", "clips", "role"):
            assert c.get(field), (key, field)
        assert len(c["sketchfab_uid"]) == 32 and c["raw_height"] > 0
        assert "CC Attribution" in c["license"] or "CC0" in c["license"]          # no NonCommercial/NoDerivatives
        assert "idle" in c["clips"] and set(c["clips"]) <= STATES
    assert set(manifest["state_fallbacks"]) <= STATES


def test_attribution_file_credits_every_model_and_matches_the_manifest():
    fetch = load_fetch_module()
    manifest = fetch.load_manifest()
    text = fetch.attributions(manifest)
    for c in manifest["characters"].values():
        assert c["title"] in text and c["author"] in text and c["sketchfab_uid"] in text and c["license"] in text
    committed = GODOT_DIR / "assets" / "ATTRIBUTIONS.md"
    assert committed.exists() and committed.read_text() == text            # regenerate with scripts/fetch_assets.py


def test_fetch_script_refuses_without_a_token_and_never_echoes_one():
    env = {k: v for k, v in os.environ.items() if k != "SKETCHFAB_API_TOKEN"}
    done = subprocess.run([sys.executable, str(ROOT / "scripts" / "fetch_assets.py")], env=env, capture_output=True, text=True)
    assert done.returncode == 2 and "SKETCHFAB_API_TOKEN" in done.stderr
    secret = "sf-test-secret-123"
    done = subprocess.run([sys.executable, str(ROOT / "scripts" / "fetch_assets.py"), "--check"],
                          env=dict(env, SKETCHFAB_API_TOKEN=secret), capture_output=True, text=True)
    assert secret not in done.stdout + done.stderr


def test_model_files_are_not_committed():
    tracked = subprocess.run(["git", "ls-files", "godot/assets"], cwd=ROOT, capture_output=True, text=True).stdout
    assert ".glb" not in tracked and ".png" not in tracked and "characters/" not in tracked


def godot_binary():
    candidates = [os.environ.get("GODOT_BIN"), shutil.which("godot")] + [str(p) for p in (ROOT / "tools" / "godot").glob("Godot_v*_linux.x86_64")]
    return next((c for c in candidates if c and Path(c).exists()), None)


@pytest.mark.skipif(godot_binary() is None, reason="no Godot binary (set GODOT_BIN or run scripts/setup_godot_tools.sh)")
def test_godot_runs_its_own_animation_rule_tests():
    done = subprocess.run([godot_binary(), "--headless", "--path", str(GODOT_DIR), "--script", "res://tests/animation_map_test.gd"],
                          capture_output=True, text=True, timeout=180)
    assert "ANIMATION MAP TESTS: PASS" in done.stdout, done.stdout[-800:] + done.stderr[-400:]
    assert done.returncode == 0


@pytest.mark.skipif(godot_binary() is None, reason="no Godot binary (set GODOT_BIN or run scripts/setup_godot_tools.sh)")
def test_godot_builds_every_animal_and_applies_every_pose_rule():
    done = subprocess.run([godot_binary(), "--headless", "--path", str(GODOT_DIR), "--script", "res://tests/animal_test.gd"],
                          capture_output=True, text=True, timeout=180)
    assert "animal tests: ok" in done.stdout and "FAIL" not in done.stdout, done.stdout[-800:] + done.stderr[-400:]


def test_every_animal_action_the_engine_records_has_a_pose_rule():
    """animal_motion.gd must list exactly the action strings fauna/ecology.py can record (no invented ones)."""
    import re
    engine = set(re.findall(r"""\.action\s*=\s*'([a-z ]+)'""", (ROOT / "fauna" / "ecology.py").read_text()))
    # 'swimming' / 'flying' / 'roaming' come from one conditional expression
    engine |= set(re.findall(r"""'(swimming|flying|roaming)'""", (ROOT / "fauna" / "ecology.py").read_text()))
    motion = re.search(r"const ACTIONS := \[(.*?)\]", (GODOT_DIR / "animal_motion.gd").read_text()).group(1)
    listed = set(re.findall(r'"([a-z ]+)"', motion))
    assert engine == listed, (sorted(engine ^ listed))


def test_every_species_has_its_own_silhouette():
    import re
    from fauna.ecology import SPECIES
    builder = (GODOT_DIR / "animal_builder.gd").read_text()
    specs = set(re.findall(r'^\t"([a-z]+)":\s+\{"kind"', builder, re.M))
    assert set(SPECIES) <= specs, sorted(set(SPECIES) - specs)
