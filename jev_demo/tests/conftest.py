import os

import pytest

from jev_demo.repl_client import REPO_ROOT, ReplClient

REPL_BINARY = os.path.join(REPO_ROOT, ".lake/build/bin/repl")


def pytest_collection_modifyitems(config, items):
    """Skip every `lean`-marked test when the REPL binary has not been built."""
    if os.path.exists(REPL_BINARY):
        return
    skip = pytest.mark.skip(reason="REPL binary not built (run `lake build`)")
    for item in items:
        if "lean" in item.keywords:
            item.add_marker(skip)


@pytest.fixture(scope="session")
def repl():
    with ReplClient() as client:
        yield client
