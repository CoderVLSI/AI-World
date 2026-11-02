import pytest
from scripts.storage_preflight import verify_storage


def test_storage_fails_closed_and_preserves_existing_data(tmp_path):
    drive=tmp_path/'MyDrive';drive.mkdir()
    run=drive/'CAITANYA';run.mkdir()
    existing=run/'events.jsonl';existing.write_text('preserve this')
    assert verify_storage(run,drive)['write_fsync_readback']
    assert existing.read_text()=='preserve this'
    assert not list(run.glob('.caitanya-preflight-*'))
    with pytest.raises(ValueError):verify_storage(tmp_path/'ephemeral',drive)
    with pytest.raises(ValueError):verify_storage(tmp_path/'missing'/'run',tmp_path/'missing')


def test_deployment_probe_rejects_mock_and_checks_read_only(tmp_path, monkeypatch):
    import io
    import json
    from urllib.error import HTTPError
    from fastapi.testclient import TestClient
    from caitanya.engine import World
    from caitanya.server import create_app
    from scripts import verify_deployment
    world=World()
    client=TestClient(create_app(world,run_dir=tmp_path,live=False))

    class Response(io.BytesIO):
        status=200

    def open_url(request, timeout):
        url=request.full_url if hasattr(request,'full_url') else request
        method=request.get_method() if hasattr(request,'get_method') else 'GET'
        path=url.removeprefix('http://test')
        response=client.request(method,path)
        if response.status_code>=400:
            raise HTTPError(url,response.status_code,'Rejected',{},None)
        return Response(response.content)

    monkeypatch.setattr(verify_deployment,'urlopen',open_url)
    result=verify_deployment.probe('http://test')
    assert not result['passed']
    assert not result['checks']['backend_is_lfm3']
    assert not result['checks']['successful_inference_observed']
    assert result['checks']['snapshot_rejects_post']
    assert result['checks']['viewer_available']
    assert result['checks']['history_hides_root']
