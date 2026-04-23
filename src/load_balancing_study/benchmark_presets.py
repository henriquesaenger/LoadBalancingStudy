from dataclasses import dataclass
import math


@dataclass(frozen=True, slots=True)
class BenchmarkPreset:
    duration_seconds: float
    server_count: int
    max_concurrent: int
    queue_limit: int | None
    scenario_kind: str


@dataclass(frozen=True, slots=True)
class ScenarioPreset:
    kind: str
    service_time_seconds: float | None = None
    requests_per_second: float | None = None
    service_time_min_seconds: float | None = None
    service_time_alpha: float | None = None
    base_requests_per_second: float | None = None
    burst_requests_per_second: float | None = None
    burst_start_seconds: float | None = None
    burst_end_seconds: float | None = None
    time_resolution_seconds: float | None = None


DEFAULT_BENCHMARK_PRESET = BenchmarkPreset(
    duration_seconds=300.0,
    server_count=4,
    max_concurrent=8,
    queue_limit=15,
    scenario_kind="poisson",
)

_SCENARIO_PRESETS = {
    "constant": ScenarioPreset(
        kind="constant",
        service_time_seconds=0.08,
        requests_per_second=220.0,
        time_resolution_seconds=0.1,
    ),
    "burst": ScenarioPreset(
        kind="burst",
        service_time_seconds=0.10,
        base_requests_per_second=140.0,
        burst_requests_per_second=380.0,
        burst_start_seconds=60.0,
        burst_end_seconds=120.0,
        time_resolution_seconds=0.1,
    ),
    "poisson": ScenarioPreset(
        kind="poisson",
        service_time_seconds=0.08,
        requests_per_second=220.0,
        time_resolution_seconds=0.1,
    ),
    "pareto-long-tail": ScenarioPreset(
        kind="pareto-long-tail",
        requests_per_second=180.0,
        service_time_min_seconds=0.05,
        service_time_alpha=1.4,
        time_resolution_seconds=0.1,
    ),
}


def get_benchmark_preset() -> BenchmarkPreset:
    return DEFAULT_BENCHMARK_PRESET


def get_scenario_preset(kind: str) -> ScenarioPreset:
    normalized_kind = kind.strip().lower()
    preset = _SCENARIO_PRESETS.get(normalized_kind)
    if preset is None:
        raise ValueError(f"unsupported scenario kind '{kind}'")

    return preset


def resolve_scenario_value(kind: str, field_name: str, value: object) -> object:
    if value is not None:
        return value

    return getattr(get_scenario_preset(kind), field_name)


def estimate_default_total_requests(kind: str, duration_seconds: float) -> int:
    if duration_seconds <= 0:
        return 0

    preset = get_scenario_preset(kind)

    if kind in {"constant", "pareto-long-tail"}:
        requests_per_second = preset.requests_per_second
        if requests_per_second is None:
            raise ValueError(f"scenario '{kind}' does not define requests_per_second")
        return max(1, math.ceil(duration_seconds * requests_per_second))

    if kind == "poisson":
        requests_per_second = preset.requests_per_second
        if requests_per_second is None:
            raise ValueError(f"scenario '{kind}' does not define requests_per_second")
        return max(1, round(duration_seconds * requests_per_second))

    if kind == "burst":
        base_requests_per_second = preset.base_requests_per_second
        burst_requests_per_second = preset.burst_requests_per_second
        burst_start_seconds = preset.burst_start_seconds
        burst_end_seconds = preset.burst_end_seconds
        time_resolution_seconds = preset.time_resolution_seconds

        if (
            base_requests_per_second is None
            or burst_requests_per_second is None
            or burst_start_seconds is None
            or burst_end_seconds is None
            or time_resolution_seconds is None
        ):
            raise ValueError(f"scenario '{kind}' does not define a complete burst preset")

        total_requests = 0
        current_time = 0.0
        while current_time < duration_seconds:
            in_burst = burst_start_seconds <= current_time < burst_end_seconds
            requests_per_second = burst_requests_per_second if in_burst else base_requests_per_second
            total_requests += int(requests_per_second * time_resolution_seconds)
            current_time += time_resolution_seconds

        return total_requests

    raise ValueError(f"unsupported scenario kind '{kind}'")