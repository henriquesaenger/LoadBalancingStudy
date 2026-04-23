from collections.abc import Sequence

from load_balancing_study.algorithms.base import LoadBalancingAlgorithm, online_servers
from load_balancing_study.servers import ServerConfig, ServerState
from load_balancing_study.simulation.models import Request


class RoundRobinAlgorithm(LoadBalancingAlgorithm):
    name = "round-robin"

    def __init__(self) -> None:
        self._next_index = 0

    def reset(self, server_configs: Sequence[ServerConfig]) -> None:
        _ = server_configs
        self._next_index = 0

    def select_server(self, request: Request, server_states: Sequence[ServerState]) -> str | None:
        _ = request
        candidates = online_servers(server_states)
        if not candidates:
            return None

        index = self._next_index % len(candidates)
        self._next_index += 1
        return candidates[index].server_id
