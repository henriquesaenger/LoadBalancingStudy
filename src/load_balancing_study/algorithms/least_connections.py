from collections.abc import Sequence

from load_balancing_study.algorithms.base import LoadBalancingAlgorithm, online_servers
from load_balancing_study.servers import ServerConfig, ServerState
from load_balancing_study.simulation.models import Request


class LeastConnectionsAlgorithm(LoadBalancingAlgorithm):
    name = "least-connections"

    def reset(self, server_configs: Sequence[ServerConfig]) -> None:
        _ = server_configs

    def select_server(self, request: Request, server_states: Sequence[ServerState]) -> str | None:
        _ = request
        candidates = online_servers(server_states)
        if not candidates:
            return None

        selected = min(
            candidates,
            key=lambda server: (
                server.active_requests,
                server.queued_requests,
                server.server_id,
            ),
        )
        return selected.server_id
