from abc import ABC, abstractmethod
from collections.abc import Sequence

from load_balancing_study.servers import ServerConfig, ServerState
from load_balancing_study.simulation.models import Request


class LoadBalancingAlgorithm(ABC):
    """Contract for all load-balancing strategies."""

    name: str

    def reset(self, server_configs: Sequence[ServerConfig]) -> None:
        """Reset internal state before a simulation run."""
        _ = server_configs

    @abstractmethod
    def select_server(self, request: Request, server_states: Sequence[ServerState]) -> str | None:
        """Return the selected server_id or None when no server is available."""
        raise NotImplementedError


def online_servers(server_states: Sequence[ServerState]) -> list[ServerState]:
    return [server for server in server_states if server.online]
