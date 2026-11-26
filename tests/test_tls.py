"""
TLS tests against real etcd servers started by this module.

Certificates are generated with openssl at test time. Two servers are started:
one with server-side TLS only, and one that also requires client certificates
(mutual TLS). Skipped when the etcd or openssl binaries are not available.
"""

import shutil
import socket
import subprocess
import time

import grpc
import pytest

import etcd3
from etcd3 import etcdrpc

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        not (shutil.which("etcd") and shutil.which("openssl")),
        reason="needs the etcd and openssl binaries",
    ),
]


def _free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _openssl(*args, cwd):
    subprocess.run(["openssl", *args], cwd=cwd, check=True, capture_output=True)


def _issue(name, ext, cwd):
    _openssl(
        "req", "-newkey", "rsa:2048", "-nodes", "-keyout", f"{name}.key",
        "-out", f"{name}.csr", "-subj", f"/CN={name}", cwd=cwd,
    )  # fmt: skip
    (cwd / f"{name}.ext").write_text(ext)
    _openssl(
        "x509", "-req", "-in", f"{name}.csr", "-CA", "ca.crt", "-CAkey", "ca.key",
        "-CAcreateserial", "-out", f"{name}.crt", "-days", "1",
        "-extfile", f"{name}.ext", cwd=cwd,
    )  # fmt: skip


@pytest.fixture(scope="module")
def certs(tmp_path_factory):
    d = tmp_path_factory.mktemp("certs")
    _openssl(
        "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-keyout", "ca.key",
        "-out", "ca.crt", "-days", "1", "-subj", "/CN=python-etcd3-test-ca", cwd=d,
    )  # fmt: skip
    _issue(
        "server",
        # etcd's embedded gateway dials itself with the server cert, so it
        # needs clientAuth as well as serverAuth.
        "subjectAltName=DNS:localhost,IP:127.0.0.1\n"
        "extendedKeyUsage=serverAuth,clientAuth\n",
        d,
    )
    _issue("client", "extendedKeyUsage=clientAuth\n", d)
    return d


def _start_etcd(certs, tmp_path, client_cert_auth):
    port, peer_port = _free_port(), _free_port()
    peer = f"http://127.0.0.1:{peer_port}"
    url = f"https://127.0.0.1:{port}"
    args = [
        "etcd", "--name", "tls", "--data-dir", str(tmp_path / "data"),
        "--listen-client-urls", url, "--advertise-client-urls", url,
        "--listen-peer-urls", peer, "--initial-advertise-peer-urls", peer,
        "--initial-cluster", f"tls={peer}",
        "--cert-file", str(certs / "server.crt"),
        "--key-file", str(certs / "server.key"),
    ]  # fmt: skip
    if client_cert_auth:
        # etcd requires client certificates whenever a trusted CA is set
        args += ["--client-cert-auth", "--trusted-ca-file", str(certs / "ca.crt")]
    log = open(tmp_path / "etcd.log", "wb")
    proc = subprocess.Popen(args, stdout=log, stderr=subprocess.STDOUT)
    kwargs = {"host": "127.0.0.1", "port": port, "ca_cert": str(certs / "ca.crt")}
    if client_cert_auth:
        kwargs["cert_key"] = str(certs / "client.key")
        kwargs["cert_cert"] = str(certs / "client.crt")
    deadline = time.time() + 20
    while True:
        try:
            with etcd3.client(timeout=2, **kwargs) as c:
                c.status()
            break
        except Exception:
            if proc.poll() is not None or time.time() > deadline:
                proc.kill()
                log.close()
                raise RuntimeError(
                    "etcd failed to start:\n" + (tmp_path / "etcd.log").read_text()
                ) from None
            time.sleep(0.2)
    return proc, log, kwargs


@pytest.fixture(scope="module")
def tls_etcd(certs, tmp_path_factory):
    """Server-side TLS only; yields client kwargs."""
    proc, log, kwargs = _start_etcd(certs, tmp_path_factory.mktemp("tls"), False)
    yield kwargs
    proc.terminate()
    proc.wait(10)
    log.close()


@pytest.fixture(scope="module")
def mtls_etcd(certs, tmp_path_factory):
    """Mutual TLS (--client-cert-auth); yields client kwargs incl. client cert."""
    proc, log, kwargs = _start_etcd(certs, tmp_path_factory.mktemp("mtls"), True)
    yield kwargs
    proc.terminate()
    proc.wait(10)
    log.close()


class TestTLS:
    def test_secure_channel_ca_cert_only(self, tls_etcd):
        with etcd3.client(timeout=5, **tls_etcd) as client:
            assert client.uses_secure_channel is True
            client.put("/doot/tls", "secure")
            assert client.get("/doot/tls")[0] == b"secure"
            client.delete("/doot/tls")

    def test_secure_channel(self, mtls_etcd):
        with etcd3.client(timeout=5, **mtls_etcd) as client:
            assert client.uses_secure_channel is True
            client.put("/doot/mtls", "secure")
            assert client.get("/doot/mtls")[0] == b"secure"
            events, cancel = client.watch("/doot/mtls")
            client.put("/doot/mtls", "watched")
            assert next(events).value == b"watched"
            cancel()
            client.delete("/doot/mtls")

    def test_mtls_without_client_cert_rejected(self, mtls_etcd):
        kwargs = {k: v for k, v in mtls_etcd.items() if not k.startswith("cert_")}
        with etcd3.client(timeout=5, **kwargs) as client:
            with pytest.raises((etcd3.exceptions.ConnectionFailedError, grpc.RpcError)):
                client.get("/doot/mtls")

    def test_plaintext_client_against_tls_server_fails(self, tls_etcd):
        with etcd3.client(
            host=tls_etcd["host"], port=tls_etcd["port"], timeout=2
        ) as client:
            with pytest.raises((etcd3.exceptions.ConnectionFailedError, grpc.RpcError)):
                client.get("/doot/tls")

    def test_user_pwd_auth_over_tls(self, tls_etcd):
        """Over TLS the token is also attached as gRPC call credentials."""
        with etcd3.client(timeout=5, **tls_etcd) as admin:
            auth = etcdrpc.AuthStub(admin.channel)
            auth.RoleAdd(etcdrpc.AuthRoleAddRequest(name="root"))
            auth.UserAdd(etcdrpc.AuthUserAddRequest(name="root", password="pwd"))
            auth.UserGrantRole(
                etcdrpc.AuthUserGrantRoleRequest(user="root", role="root")
            )
            auth.AuthEnable(etcdrpc.AuthEnableRequest())
            try:
                with etcd3.client(
                    timeout=5, user="root", password="pwd", **tls_etcd
                ) as client:
                    assert client.call_credentials is not None
                    client.put("/doot/tls-auth", "v")
                    assert client.get("/doot/tls-auth")[0] == b"v"
                    client.delete("/doot/tls-auth")
            finally:
                token = auth.Authenticate(
                    etcdrpc.AuthenticateRequest(name="root", password="pwd")
                ).token
                md = (("token", token),)
                auth.AuthDisable(etcdrpc.AuthDisableRequest(), metadata=md)
                auth.UserDelete(etcdrpc.AuthUserDeleteRequest(name="root"))
                auth.RoleDelete(etcdrpc.AuthRoleDeleteRequest(role="root"))
