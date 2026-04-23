from load_balancing_study.algorithms.base import LoadBalancingAlgorithm

AlgorithmClass = type[LoadBalancingAlgorithm]

_ALGORITHMS: dict[str, AlgorithmClass] = {}


def register_algorithm_class(algorithm_class: AlgorithmClass) -> None:
    name = algorithm_class.name.strip().lower()
    if not name:
        raise ValueError("algorithm name must be a non-empty string")

    existing = _ALGORITHMS.get(name)
    if existing is not None and existing is not algorithm_class:
        raise ValueError(f"algorithm '{name}' is already registered")

    _ALGORITHMS[name] = algorithm_class


def create_algorithm(name: str) -> LoadBalancingAlgorithm:
    normalized_name = name.strip().lower()
    try:
        algorithm_class = _ALGORITHMS[normalized_name]
    except KeyError as exc:
        available = ", ".join(list_algorithms()) or "<none>"
        raise ValueError(f"unknown algorithm '{name}'. Available: {available}") from exc

    return algorithm_class()


def list_algorithms() -> list[str]:
    return sorted(_ALGORITHMS.keys())
