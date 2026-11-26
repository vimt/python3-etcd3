"""
Tests for username/password authentication against a real etcd.
"""

import grpc
import pytest

import etcd3
from etcd3 import etcdrpc
from tests.conftest import new_client

pytestmark = pytest.mark.integration

USER = "root"
PASSWORD = "pwd"


@pytest.fixture
def auth_enabled():
    """Enable etcd auth with a root user for the duration of a test."""
    with new_client() as admin:
        auth = etcdrpc.AuthStub(admin.channel)
        auth.RoleAdd(etcdrpc.AuthRoleAddRequest(name="root"))
        auth.UserAdd(etcdrpc.AuthUserAddRequest(name=USER, password=PASSWORD))
        auth.UserGrantRole(etcdrpc.AuthUserGrantRoleRequest(user=USER, role="root"))
        auth.AuthEnable(etcdrpc.AuthEnableRequest())
        try:
            yield
        finally:
            # Always restore an auth-less cluster, or every later test fails.
            token = auth.Authenticate(
                etcdrpc.AuthenticateRequest(name=USER, password=PASSWORD)
            ).token
            auth.AuthDisable(etcdrpc.AuthDisableRequest(), metadata=(("token", token),))
            auth.UserDelete(etcdrpc.AuthUserDeleteRequest(name=USER))
            auth.RoleDelete(etcdrpc.AuthRoleDeleteRequest(role="root"))


class TestAuth:
    def test_user_pwd_auth(self, auth_enabled):
        with new_client(user=USER, password=PASSWORD) as client:
            assert client.metadata == (("token", client.metadata[0][1]),)
            client.put("/doot/auth", "secret")
            value, _ = client.get("/doot/auth")
            assert value == b"secret"
            assert client.delete("/doot/auth") is True

    def test_auth_watch(self, auth_enabled):
        with new_client(user=USER, password=PASSWORD) as client:
            events, cancel = client.watch("/doot/auth-watch")
            client.put("/doot/auth-watch", "v")
            event = next(events)
            cancel()
            assert event.value == b"v"

    def test_auth_lease_and_lock(self, auth_enabled):
        with new_client(user=USER, password=PASSWORD) as client:
            lease = client.lease(10)
            client.put("/doot/auth-lease", "v", lease=lease)
            assert lease.keys == [b"/doot/auth-lease"]
            lease.revoke()
            with client.lock("auth-lock", ttl=10) as lock:
                assert lock.is_acquired()

    def test_auth_maintenance_calls(self, auth_enabled):
        with new_client(user=USER, password=PASSWORD) as client:
            assert isinstance(client.hash(), int)
            assert client.status().version

    def test_wrong_password(self, auth_enabled):
        with pytest.raises(grpc.RpcError) as excinfo:
            new_client(user=USER, password="wrong")
        assert excinfo.value.code() == grpc.StatusCode.INVALID_ARGUMENT

    def test_unauthenticated_request_rejected(self, auth_enabled):
        with new_client() as client, pytest.raises(grpc.RpcError):
            client.get("/doot/auth")

    def test_user_or_pwd_alone_raises(self):
        with pytest.raises(Exception, match="both user and password"):
            etcd3.client(user="usr")
        with pytest.raises(Exception, match="both user and password"):
            etcd3.client(password="pwd")
