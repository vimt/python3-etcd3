"""
Common test fixtures and utilities for etcd3 tests.
"""

import contextlib
import os
import signal
import subprocess
from urllib.parse import urlparse

import pytest
from hypothesis import settings
from tenacity import retry, stop_after_attempt, wait_fixed

import etcd3

os.environ["ETCDCTL_API"] = "3"

# Don't set any deadline in Hypothesis
settings.register_profile("default", deadline=None)
settings.load_profile("default")


@contextlib.contextmanager
def _out_quorum():
    try:
        pids = subprocess.check_output(["pgrep", "-f", "--", "--name pifpaf[12]"])
        pids = [int(pid.strip()) for pid in pids.splitlines()]
        try:
            for pid in pids:
                os.kill(pid, signal.SIGSTOP)
            yield
        finally:
            for pid in pids:
                os.kill(pid, signal.SIGCONT)
    except subprocess.CalledProcessError:
        # pifpaf not running, skip quorum disruption
        yield


def new_client(**kwargs):
    """Create a client for the etcd under test (PYTHON_ETCD_HTTP_URL or default)."""
    endpoint = os.environ.get("PYTHON_ETCD_HTTP_URL")
    kwargs.setdefault("timeout", 5)
    if endpoint:
        url = urlparse(endpoint)
        kwargs.setdefault("host", url.hostname)
        kwargs.setdefault("port", url.port)
    return etcd3.client(**kwargs)


@retry(wait=wait_fixed(2), stop=stop_after_attempt(3))
def delete_keys_definitely():
    """Wipe all keys and alarms using a separate, fresh client.

    A fresh client is used on purpose: tests that mock gRPC failures mark the
    tested client's endpoint as failed, so it cannot be used for cleanup.
    """
    with new_client() as client:
        client.delete_prefix("/")
        # Also delete any keys without prefix
        for key, _ in client.get_all():
            client.delete(key)
        for alarm in client.list_alarms():
            client.disarm_alarm(alarm.member_id)


def pytest_collection_modifyitems(items):
    """Tests using the `etcd` fixture need a running etcd: mark them so that
    `pytest -m "not integration"` runs without one."""
    for item in items:
        if "etcd" in getattr(item, "fixturenames", ()):
            item.add_marker(pytest.mark.integration)


class TestBase:
    @contextlib.contextmanager
    def get_clean_etcd(self):
        delete_keys_definitely()
        with new_client() as client:
            yield client
        delete_keys_definitely()

    @pytest.fixture
    def etcd(self):
        with self.get_clean_etcd() as etcd:
            yield etcd
