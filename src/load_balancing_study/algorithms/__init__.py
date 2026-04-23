from load_balancing_study.algorithms.base import LoadBalancingAlgorithm
from load_balancing_study.algorithms.least_connections import LeastConnectionsAlgorithm
from load_balancing_study.algorithms.random_choice import RandomChoiceAlgorithm
from load_balancing_study.algorithms.registry import create_algorithm, list_algorithms, register_algorithm_class
from load_balancing_study.algorithms.round_robin import RoundRobinAlgorithm
from load_balancing_study.algorithms.powerOfTwoChoices import PowerOfTwoChoicesAlgorithm

_BUILTIN_ALGORITHMS: tuple[type[LoadBalancingAlgorithm], ...] = (
    RoundRobinAlgorithm,
    RandomChoiceAlgorithm,
    LeastConnectionsAlgorithm,
    PowerOfTwoChoicesAlgorithm,
)


def register_default_algorithms() -> None:
    for algorithm_class in _BUILTIN_ALGORITHMS:
        register_algorithm_class(algorithm_class)


register_default_algorithms()

__all__ = [
    "LoadBalancingAlgorithm",
    "RoundRobinAlgorithm",
    "RandomChoiceAlgorithm",
    "LeastConnectionsAlgorithm",
    "PowerOfTwoChoicesAlgorithm",
    "register_algorithm_class",
    "create_algorithm",
    "list_algorithms",
    "register_default_algorithms",
]
