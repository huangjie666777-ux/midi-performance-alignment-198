from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def _post(examples, ref_name, perf_name, **params):
    defaults = dict(reference_track=1, reference_channel=0,
                    performance_track=0, performance_channel=0)
    defaults.update(params)
    return client.post(
        "/align",
        data=defaults,
        files={
            "reference": ("r.mid", examples[ref_name], "audio/midi"),
            "performance": ("p.mid", examples[perf_name], "audio/midi"),
        })


def test_health():
    assert client.get("/health").json() == {"status": "ok"}


def test_align_ok(examples):
    resp = _post(examples, "reference.mid", "performance.mid")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_cost"] == 5
    assert body["counts"]["extra"] == 1


def test_align_rejected_with_location(examples):
    resp = _post(examples, "reference.mid", "invalid_orphan_off.mid")
    assert resp.status_code == 422
    detail = resp.json()["detail"]
    assert detail["file"] == "performance"
    assert detail["track"] == 0
    assert detail["event"] == 0


def test_align_rejected_reference_side(examples):
    resp = _post(examples, "invalid_type2.mid", "performance.mid")
    assert resp.status_code == 422
    assert resp.json()["detail"]["file"] == "reference"


def test_channel_form_validation(examples):
    resp = _post(examples, "reference.mid", "performance.mid",
                 performance_channel=16)
    assert resp.status_code == 422

