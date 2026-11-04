"""A crowded inhabitant is shown the neighbours nearest to them, not the lowest-numbered ones."""
from caitanya.inference import nearest_others


def test_the_nearest_twelve_are_kept_whatever_their_ids():
    me = {"x": 50, "z": 50}
    others = [{"id": f"agent-{i:04}", "x": 50 + (i % 9) - 4, "z": 50 + (i // 9) - 3} for i in range(40)]
    kept = nearest_others(others, me)
    assert len(kept) == 12
    farthest_kept = max(abs(o["x"] - 50) + abs(o["z"] - 50) for o in kept)
    nearest_dropped = min(abs(o["x"] - 50) + abs(o["z"] - 50) for o in others if o not in kept)
    assert farthest_kept <= nearest_dropped
    assert kept != others[:12], "not simply the first twelve by id"


def test_ties_are_broken_by_id_so_the_choice_is_deterministic_and_few_are_untouched():
    me = {"x": 0, "z": 0}
    others = [{"id": "agent-0009", "x": 1, "z": 0}, {"id": "agent-0002", "x": 0, "z": 1}, {"id": "agent-0005", "x": -1, "z": 0}]
    assert [o["id"] for o in nearest_others(others, me)] == ["agent-0002", "agent-0005", "agent-0009"]
    assert nearest_others([], me) == []
