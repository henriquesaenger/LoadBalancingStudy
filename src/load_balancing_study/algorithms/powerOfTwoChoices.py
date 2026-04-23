import random
from collections.abc import Sequence

from load_balancing_study.algorithms.base import LoadBalancingAlgorithm, online_servers
from load_balancing_study.servers import ServerConfig, ServerState
from load_balancing_study.simulation.models import Request


class PowerOfTwoChoicesAlgorithm(LoadBalancingAlgorithm):
    name = "Power Of Two Choices"

    def __init__(self, seed: int | None = None) -> None:
        self._rng = random.Random(seed)

    def reset(self, server_configs: Sequence[ServerConfig]) -> None:
        _ = server_configs

    def select_server(self, request: Request, server_states: Sequence[ServerState]) -> str | None:
        _ = request
        candidates = online_servers(server_states)
        if not candidates:
            return None
        elif len(candidates) == 1:
            return candidates[0].server_id
        else:
            sampled = self._rng.sample(candidates, min(2, len(candidates)))
            best = min(sampled, key=lambda state: (state.active_requests, state.queued_requests))
            return best.server_id