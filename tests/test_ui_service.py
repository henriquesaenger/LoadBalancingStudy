import pytest

from load_balancing_study.ui.service import BenchmarkConfig, ScenarioConfig, run_benchmark_comparison


def _load_type_totals_by_prefix(sources: list[str]) -> dict[str, int]:
    totals: dict[str, int] = {"read": 0, "write": 0, "report": 0, "auth": 0}
    for source in sources:
        load_type = source.split("-", 1)[0]
        totals[load_type] += 1
    return totals


def test_run_benchmark_comparison_returns_selected_algorithms() -> None:
    comparison = run_benchmark_comparison(
        BenchmarkConfig(
            algorithm_names=("round-robin", "least-connections"),
            duration_seconds=4.0,
            server_count=2,
            max_concurrent=1,
            queue_limit=5,
            seed=7,
            scenario=ScenarioConfig(
                kind="constant",
                requests_per_second=6.0,
                service_time_seconds=0.25,
            ),
        )
    )

    assert comparison.scenario_name == "ui-constant"
    assert comparison.server_ids == ("s1", "s2")
    assert [result.algorithm_name for result in comparison.results] == [
        "round-robin",
        "least-connections",
    ]
    assert len(comparison.simulation_input.requests) == comparison.results[0].metrics.total_requests
    assert all(result.metrics.total_requests == len(comparison.simulation_input.requests) for result in comparison.results)


def test_run_benchmark_comparison_supports_burst_scenario() -> None:
    comparison = run_benchmark_comparison(
        BenchmarkConfig(
            algorithm_names=("random",),
            duration_seconds=5.0,
            server_count=3,
            max_concurrent=2,
            queue_limit=None,
            scenario=ScenarioConfig(
                kind="burst",
                service_time_seconds=0.2,
                base_requests_per_second=2.0,
                burst_requests_per_second=8.0,
                burst_start_seconds=1.0,
                burst_end_seconds=3.0,
                time_resolution_seconds=0.5,
            ),
        )
    )

    assert comparison.scenario_name == "ui-burst"
    assert comparison.results[0].metrics.total_requests == len(comparison.simulation_input.requests)
    assert comparison.results[0].metrics.served_requests <= comparison.results[0].metrics.total_requests


def test_run_benchmark_comparison_generates_exact_total_requests() -> None:
    comparison = run_benchmark_comparison(
        BenchmarkConfig(
            algorithm_names=("round-robin",),
            duration_seconds=2.0,
            total_requests=11,
            server_count=2,
            max_concurrent=1,
            queue_limit=5,
            seed=3,
            scenario=ScenarioConfig(
                kind="constant",
                requests_per_second=3.0,
                service_time_seconds=0.2,
            ),
        )
    )

    assert len(comparison.simulation_input.requests) == 11
    assert comparison.results[0].metrics.total_requests == 11


def test_run_benchmark_comparison_exposes_variable_traffic_sources() -> None:
    comparison = run_benchmark_comparison(
        BenchmarkConfig(
            algorithm_names=("round-robin",),
            duration_seconds=20.0,
            total_requests=600,
            server_count=2,
            max_concurrent=2,
            queue_limit=10,
            seed=17,
            scenario=ScenarioConfig(
                kind="constant",
                requests_per_second=30.0,
                service_time_seconds=0.05,
            ),
        )
    )

    source_distribution = comparison.results[0].metrics.source_distribution
    sources = [item.source for item in source_distribution]
    totals = _load_type_totals_by_prefix(
        [
            source_item.source
            for source_item in source_distribution
            for _ in range(source_item.total_requests)
        ]
    )

    assert len(sources) >= 2
    assert all(
        source.startswith(("read-", "write-", "report-", "auth-"))
        for source in sources
    )
    assert any(source.endswith("below-expected") for source in sources)
    assert any(source.endswith("expected") for source in sources)
    assert any(source.endswith("above-expected") for source in sources)
    assert totals["read"] > totals["write"] > totals["report"]
    assert 30 <= totals["auth"] <= 48


def test_benchmark_config_defaults_use_realistic_poisson_baseline() -> None:
    config = BenchmarkConfig(algorithm_names=("round-robin",))

    assert config.duration_seconds == 300.0
    assert config.server_count == 4
    assert config.max_concurrent == 8
    assert config.queue_limit == 15
    assert config.scenario.kind == "poisson"
    assert config.scenario.requests_per_second == 220.0
    assert config.scenario.service_time_seconds == 0.08


@pytest.mark.parametrize(
    ("scenario_kind", "expected_values"),
    [
        (
            "constant",
            {
                "service_time_seconds": 0.08,
                "requests_per_second": 220.0,
            },
        ),
        (
            "burst",
            {
                "service_time_seconds": 0.10,
                "base_requests_per_second": 140.0,
                "burst_requests_per_second": 380.0,
                "burst_start_seconds": 60.0,
                "burst_end_seconds": 120.0,
            },
        ),
        (
            "poisson",
            {
                "service_time_seconds": 0.08,
                "requests_per_second": 220.0,
            },
        ),
        (
            "pareto-long-tail",
            {
                "requests_per_second": 180.0,
                "service_time_min_seconds": 0.05,
                "service_time_alpha": 1.4,
            },
        ),
    ],
)
def test_scenario_config_uses_default_preset_for_each_kind(
    scenario_kind: str,
    expected_values: dict[str, object],
) -> None:
    config = ScenarioConfig(kind=scenario_kind)

    for field_name, expected_value in expected_values.items():
        assert getattr(config, field_name) == expected_value


def test_run_benchmark_comparison_requires_at_least_one_algorithm() -> None:
    with pytest.raises(ValueError, match="select at least one algorithm"):
        run_benchmark_comparison(BenchmarkConfig(algorithm_names=()))


def test_run_benchmark_comparison_rejects_non_positive_total_requests() -> None:
    with pytest.raises(ValueError, match="total_requests must be > 0 when provided"):
        run_benchmark_comparison(
            BenchmarkConfig(
                algorithm_names=("round-robin",),
                total_requests=0,
            )
        )


def test_run_benchmark_comparison_supports_poisson_scenario() -> None:
    comparison = run_benchmark_comparison(
        BenchmarkConfig(
            algorithm_names=("least-connections",),
            duration_seconds=5.0,
            server_count=2,
            max_concurrent=2,
            queue_limit=5,
            seed=13,
            scenario=ScenarioConfig(
                kind="poisson",
                requests_per_second=7.0,
                service_time_seconds=0.15,
            ),
        )
    )

    assert comparison.scenario_name == "ui-poisson"
    assert comparison.results[0].metrics.total_requests == len(comparison.simulation_input.requests)
    assert comparison.results[0].metrics.total_requests > 0


def test_run_benchmark_comparison_supports_pareto_long_tail_scenario() -> None:
    comparison = run_benchmark_comparison(
        BenchmarkConfig(
            algorithm_names=("least-connections",),
            duration_seconds=5.0,
            server_count=2,
            max_concurrent=2,
            queue_limit=5,
            seed=19,
            scenario=ScenarioConfig(
                kind="pareto-long-tail",
                requests_per_second=7.0,
                service_time_min_seconds=0.05,
                service_time_alpha=1.5,
            ),
        )
    )

    assert comparison.scenario_name == "ui-pareto-long-tail"
    assert comparison.results[0].metrics.total_requests == len(comparison.simulation_input.requests)
    assert comparison.results[0].metrics.avg_service_seconds >= 0.05