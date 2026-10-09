# The core's tests run without the plugins installed on this Mac (~/Library/Application Support/Hyimg/plugins, links to the plugins'
# working copies): a test that needs a plugin names it in HYIMG_PLUGINS. The name has no HYIMG_ prefix because the test servers drop
# those from the environment they inherit (server.py plugins()).
import os

os.environ["HY_TEST_ONLY_PLUGINS"] = "1"

# No test leaves a server behind, and none writes into the person's ~/Library/Caches/Hyimg (tests/procguard.py, owner 2026-10-07);
# tests/unit/conftest.py installs the same guard when pytest runs tests/unit alone
import procguard  # noqa: E402

procguard.install()


def pytest_sessionfinish(session, exitstatus):   # also after ⌃C: the servers this session started and did not stop, then the cache check
    procguard.finish(session)
