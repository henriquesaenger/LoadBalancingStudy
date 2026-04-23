import argparse
import json
import sys
from dataclasses import asdict, dataclass
from typing import Any

from load_balancing_study.algorithms import create_algorithm, list_algorithms
from load_balancing_study.benchmark_presets import get_benchmark_preset, get_scenario_preset
from load_balancing_study.metrics import SimulationMetrics, calculate_metrics
from load_balancing_study.scenarios import (
    BurstScenario,
    ConstantRateScenario,
    ParetoLongTailScenario,
    PoissonArrivalScenario,
)
from load_balancing_study.servers import ServerConfig
from load_balancing_study.simulation import SimulationEngine, WorkloadSource


_MISSING = object()


@dataclass(frozen=True, slots=True)
class AlgorithmRunResult:
    algorithm: str
    metrics: SimulationMetrics


def build_parser() -> argparse.ArgumentParser:
    benchmark_preset = get_benchmark_preset()
    available_algorithms = list_algorithms()
    parser = argparse.ArgumentParser(
        prog="load-balancing-study",
        description="Run load-balancing simulations with configurable workloads.",
    )
    parser.add_argument(
        "--algorithm",
        action="append",
        choices=["all", *available_algorithms],
        default=[],
        help=(
            "Algorithm to execute. Repeat to compare specific algorithms "
            "(example: --algorithm round-robin --algorithm least-connections). "
            "Use 'all' to compare every registered algorithm."
        ),
    )
    parser.add_argument(
        "--duration",
        type=float,
        default=benchmark_preset.duration_seconds,
        help="Simulation duration in seconds.",
    )
    parser.add_argument("--servers", type=int, default=benchmark_preset.server_count, help="Number of backend servers.")
    parser.add_argument(
        "--max-concurrent",
        type=int,
        default=benchmark_preset.max_concurrent,
        help="Max concurrent requests per server.",
    )
    parser.add_argument(
        "--queue-limit",
        type=int,
        default=benchmark_preset.queue_limit,
        help="Queue size per server. Use -1 for unlimited queue.",
    )
    parser.add_argument("--seed", type=int, default=None, help="Optional deterministic seed.")

    parser.add_argument(
        "--scenario",
        choices=("constant", "burst", "poisson", "pareto-long-tail"),
        default=benchmark_preset.scenario_kind,
        help="Base scenario used when --workload is not provided.",
    )
    parser.add_argument(
        "--rps",
        type=float,
        default=None,
        help="Requests per second for constant, poisson, and pareto-long-tail scenarios.",
    )
    parser.add_argument(
        "--service-time",
        type=float,
        default=None,
        help="Service time in seconds for constant, burst, and poisson scenarios.",
    )
    parser.add_argument(
        "--service-time-min",
        type=float,
        default=None,
        help="Minimum service time in seconds for pareto-long-tail scenario.",
    )
    parser.add_argument(
        "--service-time-alpha",
        type=float,
        default=None,
        help="Pareto alpha (> 1, lower means heavier tail) for pareto-long-tail scenario.",
    )
    parser.add_argument("--base-rps", type=float, default=None, help="Base requests per second for burst scenario.")
    parser.add_argument("--burst-rps", type=float, default=None, help="Burst requests per second.")
    parser.add_argument("--burst-start", type=float, default=None, help="Burst start time in seconds.")
    parser.add_argument("--burst-end", type=float, default=None, help="Burst end time in seconds.")
    parser.add_argument(
        "--time-resolution",
        type=float,
        default=0.1,
        help="Time resolution for burst scenario generation.",
    )
    parser.add_argument(
        "--workload",
        action="append",
        default=[],
        help=(
            "Repeatable workload spec to run simultaneous loads. "
            "Format: name:type:key=value,key=value. "
            "Types: constant, burst, poisson, pareto-long-tail."
        ),
    )
    parser.add_argument("--output", choices=("text", "json"), default="text")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        _validate_args(args)
        algorithms_to_run = _resolve_algorithms(args.algorithm)
        workloads = _build_workloads(args)
        servers = _build_servers(args)

        engine = SimulationEngine()
        simulation_input = engine.build_input(
            duration_seconds=args.duration,
            workloads=workloads,
            seed=args.seed,
        )
        results: list[AlgorithmRunResult] = []
        for algorithm_name in algorithms_to_run:
            output = engine.run(
                simulation_input=simulation_input,
                server_configs=servers,
                algorithm=create_algorithm(algorithm_name),
            )
            metrics = calculate_metrics(
                simulation_input=simulation_input,
                simulation_output=output,
                server_ids=[server.server_id for server in servers],
            )
            results.append(AlgorithmRunResult(algorithm=algorithm_name, metrics=metrics))
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    if args.output == "json":
        _print_json_report(args.duration, workloads, results)
    else:
        _print_text_report(args.duration, workloads, results)

    return 0


def _resolve_algorithms(raw_algorithms: list[str]) -> list[str]:
    selected = [algorithm.strip().lower() for algorithm in raw_algorithms if algorithm.strip()]
    if not selected:
        return list_algorithms()

    if "all" in selected:
        if len(selected) > 1:
            raise ValueError("--algorithm all cannot be combined with specific algorithm names")
        return list_algorithms()

    # Preserve order while removing duplicates.
    return list(dict.fromkeys(selected))


def _validate_args(args: argparse.Namespace) -> None:
    if args.duration <= 0:
        raise ValueError("duration must be > 0")
    if args.servers <= 0:
        raise ValueError("servers must be > 0")
    if args.max_concurrent <= 0:
        raise ValueError("max-concurrent must be > 0")
    if args.queue_limit == 0 or args.queue_limit < -1:
        raise ValueError("queue-limit must be -1 or >= 1")
    if args.scenario in {"constant", "burst", "poisson"}:
        service_time = _resolve_service_time_seconds(args.scenario, args.service_time)
        if service_time <= 0:
            raise ValueError("service-time must be > 0")
    if args.scenario in {"constant", "poisson", "pareto-long-tail"}:
        requests_per_second = _resolve_requests_per_second(args.scenario, args.rps)
        if requests_per_second <= 0:
            raise ValueError("rps must be > 0")
    if args.scenario == "pareto-long-tail":
        service_time_min = _resolve_service_time_min_seconds(args.scenario, args.service_time_min)
        if service_time_min is None or service_time_min <= 0:
            raise ValueError("service-time-min must be > 0")
        service_time_alpha = _resolve_service_time_alpha(args.scenario, args.service_time_alpha)
        if service_time_alpha is None or service_time_alpha <= 1:
            raise ValueError("service-time-alpha must be > 1")
def _build_servers(args: argparse.Namespace) -> list[ServerConfig]:
    queue_limit = None if args.queue_limit < 0 else args.queue_limit
    return [
        ServerConfig(
            server_id=f"s{index + 1}",
            max_concurrent=args.max_concurrent,
            queue_limit=queue_limit,
        )
        for index in range(args.servers)
    ]


def _build_workloads(args: argparse.Namespace) -> list[WorkloadSource]:
    if args.workload:
        return [_parse_workload_spec(spec) for spec in args.workload]

    if args.scenario == "constant":
        scenario = ConstantRateScenario(
            requests_per_second=_resolve_requests_per_second(args.scenario, args.rps),
            service_time_seconds=_resolve_service_time_seconds(args.scenario, args.service_time),
            name="constant",
        )
    elif args.scenario == "burst":
        scenario = BurstScenario(
            base_requests_per_second=_resolve_base_requests_per_second(args.scenario, args.base_rps),
            burst_requests_per_second=_resolve_burst_requests_per_second(args.scenario, args.burst_rps),
            burst_start_seconds=_resolve_burst_start_seconds(args.scenario, args.burst_start),
            burst_end_seconds=_resolve_burst_end_seconds(args.scenario, args.burst_end),
            service_time_seconds=_resolve_service_time_seconds(args.scenario, args.service_time),
            time_resolution_seconds=args.time_resolution,
            name="burst",
        )
    elif args.scenario == "poisson":
        scenario = PoissonArrivalScenario(
            requests_per_second=_resolve_requests_per_second(args.scenario, args.rps),
            service_time_seconds=_resolve_service_time_seconds(args.scenario, args.service_time),
            name="poisson",
        )
    elif args.scenario == "pareto-long-tail":
        scenario = ParetoLongTailScenario(
            requests_per_second=_resolve_requests_per_second(args.scenario, args.rps),
            service_time_min_seconds=_resolve_service_time_min_seconds(args.scenario, args.service_time_min),
            service_time_alpha=_resolve_service_time_alpha(args.scenario, args.service_time_alpha),
            name="pareto-long-tail",
        )

    return [
        WorkloadSource(
            name=f"default-{args.scenario}",
            scenario=scenario,
            start_time_seconds=0.0,
            duration_seconds=args.duration,
            seed=args.seed,
        )
    ]


def _resolve_service_time_seconds(scenario_name: str, service_time: float | None) -> float:
    if service_time is not None:
        return service_time

    return get_scenario_preset(scenario_name).service_time_seconds


def _resolve_requests_per_second(scenario_name: str, requests_per_second: float | None) -> float:
    if requests_per_second is not None:
        return requests_per_second

    resolved = get_scenario_preset(scenario_name).requests_per_second
    if resolved is None:
        raise ValueError(f"scenario '{scenario_name}' does not define a default requests-per-second")

    return resolved


def _resolve_service_time_min_seconds(scenario_name: str, service_time_min: float | None) -> float | None:
    if service_time_min is not None:
        return service_time_min

    return get_scenario_preset(scenario_name).service_time_min_seconds


def _resolve_service_time_alpha(scenario_name: str, service_time_alpha: float | None) -> float | None:
    if service_time_alpha is not None:
        return service_time_alpha

    return get_scenario_preset(scenario_name).service_time_alpha


def _resolve_base_requests_per_second(scenario_name: str, base_requests_per_second: float | None) -> float:
    if base_requests_per_second is not None:
        return base_requests_per_second

    resolved = get_scenario_preset(scenario_name).base_requests_per_second
    if resolved is None:
        raise ValueError(f"scenario '{scenario_name}' does not define a default base requests-per-second")

    return resolved


def _resolve_burst_requests_per_second(scenario_name: str, burst_requests_per_second: float | None) -> float:
    if burst_requests_per_second is not None:
        return burst_requests_per_second

    resolved = get_scenario_preset(scenario_name).burst_requests_per_second
    if resolved is None:
        raise ValueError(f"scenario '{scenario_name}' does not define a default burst requests-per-second")

    return resolved


def _resolve_burst_start_seconds(scenario_name: str, burst_start_seconds: float | None) -> float:
    if burst_start_seconds is not None:
        return burst_start_seconds

    resolved = get_scenario_preset(scenario_name).burst_start_seconds
    if resolved is None:
        raise ValueError(f"scenario '{scenario_name}' does not define a default burst start")

    return resolved


def _resolve_burst_end_seconds(scenario_name: str, burst_end_seconds: float | None) -> float:
    if burst_end_seconds is not None:
        return burst_end_seconds

    resolved = get_scenario_preset(scenario_name).burst_end_seconds
    if resolved is None:
        raise ValueError(f"scenario '{scenario_name}' does not define a default burst end")

    return resolved


def _parse_workload_spec(spec: str) -> WorkloadSource:
    parts = spec.split(":", 2)
    if len(parts) != 3:
        raise ValueError(
            "invalid workload format. Use name:type:key=value,key=value (example: "
            "steady:constant:rps=8,service=0.2,start=0,duration=20)"
        )

    name = parts[0].strip()
    scenario_type = parts[1].strip().lower()
    params = _parse_params(parts[2])

    if not name:
        raise ValueError("workload name must not be empty")

    start_time = _pop_float(params, "start", default=0.0)
    duration = _pop_float(params, "duration", default=None)
    seed = _pop_int(params, "seed", default=None)

    if scenario_type == "constant":
        scenario = ConstantRateScenario(
            requests_per_second=_pop_float(params, "rps"),
            service_time_seconds=_pop_float(params, "service", default=1.0),
            name=f"{name}-constant",
        )
    elif scenario_type == "burst":
        scenario = BurstScenario(
            base_requests_per_second=_pop_float(params, "base_rps"),
            burst_requests_per_second=_pop_float(params, "burst_rps"),
            burst_start_seconds=_pop_float(params, "burst_start"),
            burst_end_seconds=_pop_float(params, "burst_end"),
            service_time_seconds=_pop_float(params, "service", default=1.0),
            time_resolution_seconds=_pop_float(params, "resolution", default=0.1),
            name=f"{name}-burst",
        )
    elif scenario_type == "poisson":
        scenario = PoissonArrivalScenario(
            requests_per_second=_pop_float(params, "rps"),
            service_time_seconds=_pop_float(params, "service", default=1.0),
            name=f"{name}-poisson",
        )
    elif scenario_type == "pareto-long-tail":
        scenario = ParetoLongTailScenario(
            requests_per_second=_pop_float(params, "rps"),
            service_time_min_seconds=_pop_float(params, "service_min", default=0.05),
            service_time_alpha=_pop_float(params, "alpha", default=1.5),
            name=f"{name}-pareto-long-tail",
        )
    else:
        raise ValueError(f"unsupported workload type '{scenario_type}'")

    if params:
        unknown = ", ".join(sorted(params.keys()))
        raise ValueError(f"unknown workload parameters: {unknown}")

    return WorkloadSource(
        name=name,
        scenario=scenario,
        start_time_seconds=start_time,
        duration_seconds=duration,
        seed=seed,
    )


def _parse_params(raw_params: str) -> dict[str, str]:
    params: dict[str, str] = {}
    if not raw_params.strip():
        return params

    for item in raw_params.split(","):
        token = item.strip()
        if not token:
            continue
        if "=" not in token:
            raise ValueError(f"invalid workload parameter '{token}', expected key=value")
        key, value = token.split("=", 1)
        normalized_key = key.strip().lower()
        if not normalized_key:
            raise ValueError(f"invalid workload parameter key in '{token}'")
        if normalized_key in params:
            raise ValueError(f"duplicated workload parameter '{normalized_key}'")
        params[normalized_key] = value.strip()

    return params


def _pop_float(params: dict[str, str], key: str, default: Any = _MISSING) -> float | None:
    if key not in params:
        if default is _MISSING:
            raise ValueError(f"missing workload parameter '{key}'")
        return default

    raw_value = params.pop(key)
    try:
        return float(raw_value)
    except ValueError as exc:
        raise ValueError(f"workload parameter '{key}' must be a float") from exc


def _pop_int(params: dict[str, str], key: str, default: Any = _MISSING) -> int | None:
    if key not in params:
        if default is _MISSING:
            raise ValueError(f"missing workload parameter '{key}'")
        return default

    raw_value = params.pop(key)
    try:
        return int(raw_value)
    except ValueError as exc:
        raise ValueError(f"workload parameter '{key}' must be an integer") from exc


def _print_text_report(
    duration_seconds: float,
    workloads: list[WorkloadSource],
    results: list[AlgorithmRunResult],
) -> None:
    print("Simulation Report")
    print(f"duration_seconds: {duration_seconds:.3f}")
    print(f"workloads: {', '.join(workload.name for workload in workloads)}")
    print("comparison:")
    _print_comparison_table(results)


def _print_comparison_table(results: list[AlgorithmRunResult]) -> None:
    headers = [
        "algorithm",
        "total",
        "served",
        "dropped",
        "drop_rate",
        "throughput",
        "avg_latency",
        "p95_latency",
        "avg_wait",
    ]
    rows = [
        [
            result.algorithm,
            str(result.metrics.total_requests),
            str(result.metrics.served_requests),
            str(result.metrics.dropped_requests),
            f"{result.metrics.drop_rate:.4f}",
            f"{result.metrics.throughput_rps:.4f}",
            f"{result.metrics.avg_latency_seconds:.4f}",
            f"{result.metrics.p95_latency_seconds:.4f}",
            f"{result.metrics.avg_wait_seconds:.4f}",
        ]
        for result in results
    ]

    widths = [len(header) for header in headers]
    for row in rows:
        for index, value in enumerate(row):
            widths[index] = max(widths[index], len(value))

    def _format(row_values: list[str]) -> str:
        return " | ".join(value.ljust(widths[index]) for index, value in enumerate(row_values))

    print(_format(headers))
    print("-+-".join("-" * width for width in widths))
    for row in rows:
        print(_format(row))


def _print_json_report(
    duration_seconds: float,
    workloads: list[WorkloadSource],
    results: list[AlgorithmRunResult],
) -> None:
    payload = {
        "duration_seconds": duration_seconds,
        "workloads": [
            {
                "name": workload.name,
                "scenario": workload.scenario.name,
                "start_time_seconds": workload.start_time_seconds,
                "duration_seconds": workload.duration_seconds,
                "seed": workload.seed,
            }
            for workload in workloads
        ],
        "comparative_metrics": [
            {
                "algorithm": result.algorithm,
                "metrics": asdict(result.metrics),
            }
            for result in results
        ],
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
