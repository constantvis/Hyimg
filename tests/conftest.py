# The core's tests run without the plugins installed on this Mac (~/Library/Application Support/Hyimg/plugins, links to the plugins'
# working copies): a test that needs a plugin names it in HYIMG_PLUGINS. The name has no HYIMG_ prefix because the test servers drop
# those from the environment they inherit (server.py plugins()).
import os

os.environ["HY_TEST_ONLY_PLUGINS"] = "1"

# No test leaves a server behind, and none writes into the person's ~/Library/Caches/Hyimg (tests/procguard.py, owner 2026-10-07)
import procguard  # noqa: E402

procguard.install()


def pytest_sessionfinish(session, exitstatus):   # also after ⌃C: the servers this session started and did not stop
    left = procguard.sweep()
    if left:
        print(f"\nprocguard: stopped {len(left)} server(s) a test left running: {left}")
