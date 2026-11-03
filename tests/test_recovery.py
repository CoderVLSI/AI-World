import json
import pytest
from caitanya.engine import World,Intent,digest

def test_tail_recovery_truncated_write_and_corrupt_newest_image(tmp_path):
    w=World()
    for _ in range(6):w.step()
    w.checkpoint(tmp_path)
    for _ in range(3):w.step()
    bad=w.checkpoint(tmp_path);bad.write_text('{"corrupt":true}',encoding='utf-8')
    aid=next(iter(w.agents))
    w.apply(Intent(aid,w.tick,'MOVE',{'dx':999,'dz':0}))
    for _ in range(3):w.step()
    lines=''.join(json.dumps(e)+'\n' for e in w.events)
    (tmp_path/'events.jsonl').write_text(lines+'{"event_id":',encoding='utf-8')
    restored=World.recover(tmp_path)
    assert restored.tick==12 and digest(restored.state())==digest(w.state())
    assert restored.rejections==w.rejections
    assert digest(restored.events)==digest(w.events)
    restored.step();w.step();assert digest(restored.state())==digest(w.state())

def test_journal_checksum_rejects_valid_json_corruption(tmp_path):
    w=World();w.checkpoint(tmp_path);w.step()
    bad=w.events[-1];bad['payload']['patch'][0]['value']='corruption'
    (tmp_path/'events.jsonl').write_text(json.dumps(bad)+'\n',encoding='utf-8')
    with pytest.raises(ValueError,match='checksum|gap'):World.recover(tmp_path)


def test_incremental_metric_counters_match_a_full_rescan_after_restore_and_recovery(tmp_path):
    w = World(population=6)
    w.checkpoint(tmp_path / "j")
    for _ in range(40):
        w.step()
    (tmp_path / "j" / "events.jsonl").write_text("".join(json.dumps(e) + "\n" for e in w.events), encoding="utf-8")
    for world in (w, World.restore(w.checkpoint(tmp_path / "c")), World.recover(tmp_path / "j")):
        rescan = {"births": sum(e["type"] == "birth" for e in world.events),
                  "validated": sum(e["source"] == "validated_action" for e in world.events)}
        assert world._counts["births"] == rescan["births"] and world._counts["validated"] == rescan["validated"]
        assert world.metrics()["attempted"] == len(world.rejections) + rescan["validated"] > 0
