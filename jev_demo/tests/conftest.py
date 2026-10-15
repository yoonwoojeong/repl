import os

import pytest

from jev_demo.repl_client import REPO_ROOT, ReplClient


@pytest.fixture(scope="session")
def repl():
    if not os.path.exists(os.path.join(REPO_ROOT, ".lake/build/bin/repl")):
        pytest.skip("REPL binary not built (run `lake build`)")
    with ReplClient() as client:
        yield client
