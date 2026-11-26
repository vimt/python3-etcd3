"""
Tests for lease functionality.
"""

import time

import pytest

from tests.conftest import TestBase

int_types = (int,)
etcd_version = "v3.5"  # Assume recent version for now


class TestLeases(TestBase):
    def test_lease_grant(self, etcd):
        lease = etcd.lease(1)

        assert isinstance(lease.ttl, int_types)
        assert isinstance(lease.id, int_types)

    def test_lease_revoke(self, etcd):
        lease = etcd.lease(1)
        lease.revoke()

    @pytest.mark.skipif(
        etcd_version.startswith("v3.0"), reason="requires etcd v3.1 or higher"
    )
    def test_lease_keys_empty(self, etcd):
        lease = etcd.lease(1)
        assert lease.keys == []

    @pytest.mark.skipif(
        etcd_version.startswith("v3.0"), reason="requires etcd v3.1 or higher"
    )
    def test_lease_single_key(self, etcd):
        lease = etcd.lease(1)
        etcd.put("/doot/lease_test", "this is a lease", lease=lease)
        assert lease.keys == [b"/doot/lease_test"]

    @pytest.mark.skipif(
        etcd_version.startswith("v3.0"), reason="requires etcd v3.1 or higher"
    )
    def test_lease_expire(self, etcd):
        key = "/doot/lease_test_expire"
        lease = etcd.lease(1)
        etcd.put(key, "this is a lease", lease=lease)
        import etcd3.utils as utils

        assert lease.keys == [utils.to_bytes(key)]
        v, _ = etcd.get(key)
        assert v == b"this is a lease"
        assert lease.remaining_ttl <= lease.granted_ttl

        # wait for the lease to expire
        time.sleep(lease.granted_ttl + 2)
        v, _ = etcd.get(key)
        assert v is None
