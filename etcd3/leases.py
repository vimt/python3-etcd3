from typing import TYPE_CHECKING, List, Optional, Sequence

from . import etcdrpc

if TYPE_CHECKING:
    from .client import MultiEndpointEtcd3Client


class Lease:
    """
    A lease.

    :ivar id: ID of the lease
    :ivar ttl: time to live for this lease
    """

    def __init__(
        self,
        lease_id: int,
        ttl: int,
        etcd_client: Optional["MultiEndpointEtcd3Client"] = None,
    ) -> None:
        self.id = lease_id
        self.ttl = ttl

        self.etcd_client = etcd_client

    @property
    def _client(self) -> "MultiEndpointEtcd3Client":
        if self.etcd_client is None:
            raise ValueError("This lease is not bound to an etcd client")
        return self.etcd_client

    def _get_lease_info(self) -> etcdrpc.LeaseTimeToLiveResponse:
        return self._client.get_lease_info(self.id)

    def revoke(self) -> None:
        """Revoke this lease."""
        self._client.revoke_lease(self.id)

    def refresh(self) -> List[etcdrpc.LeaseKeepAliveResponse]:
        """Refresh the time to live for this lease."""
        return list(self._client.refresh_lease(self.id))

    @property
    def remaining_ttl(self) -> int:
        return self._get_lease_info().TTL

    @property
    def granted_ttl(self) -> int:
        return self._get_lease_info().grantedTTL

    @property
    def keys(self) -> Sequence[bytes]:
        return self._get_lease_info().keys
