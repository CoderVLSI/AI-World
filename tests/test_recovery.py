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
