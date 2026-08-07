import json
from importlib.metadata import distribution

import quimb.tensor as qtn

import ole_pepo


def test_pinned_quimb_pepo_api_is_available():
    assert (
        ole_pepo.PINNED_QUIMB_COMMIT
        == "3c89529fe0a3487133a3928201691161e110abdf"
    )
    direct_url = json.loads(distribution("quimb").read_text("direct_url.json"))
    assert direct_url["vcs_info"]["commit_id"] == ole_pepo.PINNED_QUIMB_COMMIT
    assert hasattr(qtn, "CircuitPEPOSimpleUpdate")
