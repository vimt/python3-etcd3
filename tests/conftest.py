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


class TestBase:
    @contextlib.contextmanager
    def get_clean_etcd(self):
        endpoint = os.environ.get("PYTHON_ETCD_HTTP_URL")
        timeout = 5
        if endpoint:
            url = urlparse(endpoint)
            with etcd3.client(host=url.hostname, port=url.port, timeout=timeout) as client:
                self.delete_keys_definitely(client)
                yield client
        else:
            with etcd3.client() as client:
                self.delete_keys_definitely(client)
                yield client

    @retry(wait=wait_fixed(2), stop=stop_after_attempt(3))
    def delete_keys_definitely(self, client):
        # clean up after fixture goes out of scope
        client.delete_prefix("/")
        # Also delete any keys without prefix
        for key, _ in client.get_all():
            client.delete(key)
        for alarm in client.list_alarms():
            client.disarm_alarm(alarm.member_id)

    @pytest.fixture
    def etcd(self):
        with self.get_clean_etcd() as etcd:
            yield etcd
            # Clean up after test completes
            self.delete_keys_definitely(etcd)
