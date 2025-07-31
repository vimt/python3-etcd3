"""
Tests for cluster member functionality.
"""

from tests.conftest import TestBase


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