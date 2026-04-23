import random
from collections.abc import Sequence

from load_balancing_study.algorithms.base import LoadBalancingAlgorithm, online_servers
from load_balancing_study.servers import ServerConfig, ServerState
from load_balancing_study.simulation.models import Request


class RandomChoiceAlgorithm(LoadBalancingAlgorithm):
    name = "random"

    def __init__(self, seed: int | None = None) -> None:
        self._rng = random.Random(seed)

    def reset(self, server_configs: Sequence[ServerConfig]) -> None:
        _ = server_configs

    def select_server(self, request: Request, server_states: Sequence[ServerState]) -> str | None:
        _ = request
        candidates = online_servers(server_states)
        if not candidates:
            return None

        return self._rng.choice(candidates).server_id
