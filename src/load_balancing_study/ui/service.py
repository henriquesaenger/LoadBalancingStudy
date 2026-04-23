from dataclasses import dataclass, field

from load_balancing_study.algorithms import create_algorithm
from load_balancing_study.benchmark_presets import get_benchmark_preset, get_scenario_preset, resolve_scenario_value
from load_balancing_study.metrics import SimulationMetrics, calculate_metrics
from load_balancing_study.scenarios import (
    BurstScenario,
    ConstantRateScenario,
    ParetoLongTailScenario,
    PoissonArrivalScenario,
    Scenario,
)
from load_balancing_study.servers import ServerConfig
from load_balancing_study.simulation import SimulationEngine, SimulationInput


@dataclass(frozen=True, slots=True)
class ScenarioConfig:
    kind: str = get_benchmark_preset().scenario_kind
    service_time_seconds: float | None = None
    requests_per_second: float | None = None
    service_time_min_seconds: float | None = None
    service_time_alpha: float | None = None
    base_requests_per_second: float | None = None
    burst_requests_per_second: float | None = None
    burst_start_seconds: float | None = None
    burst_end_seconds: float | None = None
    time_resolution_seconds: float | None = None

    def __post_init__(self) -> None:
        normalized_kind = self.kind.strip().lower()
        get_scenario_preset(normalized_kind)
        object.__setattr__(self, "kind", normalized_kind)
        object.__setattr__(
            self,
            "service_time_seconds",
            resolve_scenario_value(normalized_kind, "service_time_seconds", self.service_time_seconds),
        )
        object.__setattr__(
            self,
            "requests_per_second",
            resolve_scenario_value(normalized_kind, "requests_per_second", self.requests_per_second),
        )
        object.__setattr__(
            self,
            "service_time_min_seconds",
            resolve_scenario_value(normalized_kind, "service_time_min_seconds", self.service_time_min_seconds),
        )
        object.__setattr__(
            self,
            "service_time_alpha",
            resolve_scenario_value(normalized_kind, "service_time_alpha", self.service_time_alpha),
        )
        object.__setattr__(
            self,
            "base_requests_per_second",
            resolve_scenario_value(normalized_kind, "base_requests_per_second", self.base_requests_per_second),
        )
        object.__setattr__(
            self,
            "burst_requests_per_second",
            resolve_scenario_value(normalized_kind, "burst_requests_per_second", self.burst_requests_per_second),
        )
        object.__setattr__(
            self,
            "burst_start_seconds",
            resolve_scenario_value(normalized_kind, "burst_start_seconds", self.burst_start_seconds),
        )
        object.__setattr__(
            self,
            "burst_end_seconds",
            resolve_scenario_value(normalized_kind, "burst_end_seconds", self.burst_end_seconds),
        )
        object.__setattr__(
            self,
            "time_resolution_seconds",
            resolve_scenario_value(normalized_kind, "time_resolution_seconds", self.time_resolution_seconds),
        )


@dataclass(frozen=True, slots=True)
class BenchmarkConfig:
    algorithm_names: tuple[str, ...]
    duration_seconds: float = get_benchmark_preset().duration_seconds
    total_requests: int | None = None
    server_count: int = get_benchmark_preset().server_count
    max_concurrent: int = get_benchmark_preset().max_concurrent
    queue_limit: int | None = get_benchmark_preset().queue_limit
    seed: int | None = None
    scenario: ScenarioConfig = field(default_factory=ScenarioConfig)


@dataclass(frozen=True, slots=True)
class BenchmarkResult:
    algorithm_name: str
    metrics: SimulationMetrics


@dataclass(frozen=True, slots=True)
class BenchmarkComparison:
    scenario_name: str
    simulation_input: SimulationInput
    server_ids: tuple[str, ...]
    results: tuple[BenchmarkResult, ...]


def run_benchmark_comparison(
    config: BenchmarkConfig,
    engine: SimulationEngine | None = None,
) -> BenchmarkComparison:
    normalized_algorithms = _normalize_algorithms(config.algorithm_names)
    _validate_benchmark_config(config, normalized_algorithms)

    simulation_engine = engine or SimulationEngine()
    scenario = _build_scenario(config.scenario)
    servers = _build_servers(config)
    simulation_input = simulation_engine.build_input_from_scenario(
        scenario=scenario,
        duration_seconds=config.duration_seconds,
        total_requests=config.total_requests,
        seed=config.seed,
    )

    server_ids = tuple(server.server_id for server in servers)
    results: list[BenchmarkResult] = []
    for algorithm_name in normalized_algorithms:
        output = simulation_engine.run(
            simulation_input=simulation_input,
            server_configs=servers,
            algorithm=create_algorithm(algorithm_name),
        )
        metrics = calculate_metrics(
            simulation_input=simulation_input,
            simulation_output=output,
            server_ids=server_ids,
        )
        results.append(BenchmarkResult(algorithm_name=algorithm_name, metrics=metrics))

    return BenchmarkComparison(
        scenario_name=scenario.name,
        simulation_input=simulation_input,
        server_ids=server_ids,
        results=tuple(results),
    )


def _normalize_algorithms(algorithm_names: tuple[str, ...]) -> tuple[str, ...]:
    normalized: list[str] = []
    seen: set[str] = set()
    for raw_name in algorithm_names:
        name = raw_name.strip().lower()
        if not name or name in seen:
            continue
        seen.add(name)
        normalized.append(name)

    return tuple(normalized)


def _validate_benchmark_config(config: BenchmarkConfig, algorithm_names: tuple[str, ...]) -> None:
    if not algorithm_names:
        raise ValueError("select at least one algorithm")
    if config.duration_seconds <= 0:
        raise ValueError("duration_seconds must be > 0")
    if config.total_requests is not None and config.total_requests <= 0:
        raise ValueError("total_requests must be > 0 when provided")
    if config.server_count <= 0:
        raise ValueError("server_count must be > 0")
    if config.max_concurrent <= 0:
        raise ValueError("max_concurrent must be > 0")
    if config.queue_limit is not None and config.queue_limit <= 0:
        raise ValueError("queue_limit must be > 0 when provided")
    kind = config.scenario.kind.strip().lower()
    if kind in {"constant", "burst", "poisson"} and config.scenario.service_time_seconds <= 0:
        raise ValueError("service_time_seconds must be > 0")
    if kind in {"constant", "poisson", "pareto-long-tail"} and config.scenario.requests_per_second <= 0:
        raise ValueError("requests_per_second must be > 0")
    if kind == "pareto-long-tail":
        if config.scenario.service_time_min_seconds <= 0:
            raise ValueError("service_time_min_seconds must be > 0")
        if config.scenario.service_time_alpha <= 1:
            raise ValueError("service_time_alpha must be > 1")


def _build_servers(config: BenchmarkConfig) -> list[ServerConfig]:
    return [
        ServerConfig(
            server_id=f"s{index + 1}",
            max_concurrent=config.max_concurrent,
            queue_limit=config.queue_limit,
        )
        for index in range(config.server_count)
    ]


def _build_scenario(config: ScenarioConfig) -> Scenario:
    kind = config.kind.strip().lower()
    if kind == "constant":
        return ConstantRateScenario(
            requests_per_second=config.requests_per_second,
            service_time_seconds=config.service_time_seconds,
            name="ui-constant",
        )
    if kind == "burst":
        return BurstScenario(
            base_requests_per_second=config.base_requests_per_second,
            burst_requests_per_second=config.burst_requests_per_second,
            burst_start_seconds=config.burst_start_seconds,
            burst_end_seconds=config.burst_end_seconds,
            service_time_seconds=config.service_time_seconds,
            time_resolution_seconds=config.time_resolution_seconds,
            name="ui-burst",
        )
    if kind == "poisson":
        return PoissonArrivalScenario(
            requests_per_second=config.requests_per_second,
            service_time_seconds=config.service_time_seconds,
            name="ui-poisson",
        )
    if kind == "pareto-long-tail":
        return ParetoLongTailScenario(
            requests_per_second=config.requests_per_second,
            service_time_min_seconds=config.service_time_min_seconds,
            service_time_alpha=config.service_time_alpha,
            name="ui-pareto-long-tail",
        )

    raise ValueError(f"unsupported scenario kind '{config.kind}'")