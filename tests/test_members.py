"""
Tests for cluster member functionality.
"""

import time

import etcd3.exceptions
from tests.conftest import TestBase, new_client


def _add_member_when_healthy(urls, timeout=20):
    """etcd refuses MemberAdd ("unhealthy cluster") until every member has been
    connected for HealthInterval (5s), e.g. right after the cluster started.
    That error is UNAVAILABLE, which marks the client's endpoint failed, so
    each attempt uses a fresh client."""
    deadline = time.time() + timeout
    while True:
        try:
            with new_client() as client:
                return client.add_member(urls).id
        except etcd3.exceptions.ConnectionFailedError:
            if time.time() > deadline:
                raise
            time.sleep(1)


int_types = (int,)


class TestMembers(TestBase):
    def test_member_list(self, etcd):
        assert len(list(etcd.members)) == 3
        for member in etcd.members:
            assert member.name.startswith("pifpaf")
            for peer_url in member.peer_urls:
                assert peer_url.startswith("http://")
            for client_url in member.client_urls:
                assert client_url.startswith("http://")
            assert isinstance(member.id, int_types) is True

    def test_status_member(self, etcd):
        import etcd3.members

        status = etcd.status()

        assert isinstance(status.leader, etcd3.members.Member) is True
        assert status.leader.id in [m.id for m in etcd.members]

    def test_add_update_remove_member(self, etcd):
        # The new member is never started: the 3 running members keep quorum.
        before = {m.id for m in etcd.members}
        new_id = _add_member_when_healthy(["http://127.0.0.1:2499"])
        new = {m.id: m for m in etcd.members}[new_id]
        try:
            assert new.id not in before
            assert new.peer_urls == ["http://127.0.0.1:2499"]
            assert str(new.id) in str(new)

            new.update(["http://127.0.0.1:2498"])
            updated = {m.id: m for m in etcd.members}[new.id]
            assert updated.peer_urls == ["http://127.0.0.1:2498"]
        finally:
            new.remove()
        assert {m.id for m in etcd.members} == before

    def test_member_active_alarms(self, etcd):
        member = next(etcd.members)
        assert list(member.active_alarms) == []
        etcd.create_alarm(member_id=member.id)
        alarms = list(member.active_alarms)
        assert [a.member_id for a in alarms] == [member.id]
