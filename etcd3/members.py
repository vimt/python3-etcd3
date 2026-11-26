from typing import TYPE_CHECKING, Iterator, List, Optional

if TYPE_CHECKING:
    from .client import Alarm, MultiEndpointEtcd3Client


class Member:
    """
    A member of the etcd cluster.

    :ivar id: ID of the member
    :ivar name: human-readable name of the member
    :ivar peer_urls: list of URLs the member exposes to the cluster for
                     communication
    :ivar client_urls: list of URLs the member exposes to clients for
                       communication
    """

    def __init__(
        self,
        id: int,
        name: str,
        peer_urls: List[str],
        client_urls: List[str],
        etcd_client: Optional["MultiEndpointEtcd3Client"] = None,
    ) -> None:
        self.id = id
        self.name = name
        self.peer_urls = peer_urls
        self.client_urls = client_urls
        self._etcd_client = etcd_client

    @property
    def _client(self) -> "MultiEndpointEtcd3Client":
        if self._etcd_client is None:
            raise ValueError("This member is not bound to an etcd client")
        return self._etcd_client

    def __str__(self) -> str:
        return (
            f"Member {self.id}: peer urls: {self.peer_urls}, client "
            f"urls: {self.client_urls}"
        )

    def remove(self) -> None:
        """Remove this member from the cluster."""
        self._client.remove_member(self.id)

    def update(self, peer_urls: List[str]) -> None:
        """
        Update the configuration of this member.

        :param peer_urls: new list of peer urls the member will use to
                          communicate with the cluster
        """
        self._client.update_member(self.id, peer_urls)

    @property
    def active_alarms(self) -> Iterator["Alarm"]:
        """Get active alarms of the member.

        :returns: Alarms
        """
        return self._client.list_alarms(member_id=self.id)
