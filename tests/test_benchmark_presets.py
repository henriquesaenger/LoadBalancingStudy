from load_balancing_study.benchmark_presets import estimate_default_total_requests, get_scenario_preset
from load_balancing_study.scenarios import BurstScenario


def test_estimate_default_total_requests_for_constant() -> None:
    assert estimate_default_total_requests("constant", 300.0) == 66000


def test_estimate_default_total_requests_for_burst() -> None:
    preset = get_scenario_preset("burst")
    scenario = BurstScenario(
        base_requests_per_second=preset.base_requests_per_second,
        burst_requests_per_second=preset.burst_requests_per_second,
        burst_start_seconds=preset.burst_start_seconds,
        burst_end_seconds=preset.burst_end_seconds,
        service_time_seconds=preset.service_time_seconds,
        time_resolution_seconds=preset.time_resolution_seconds,
    )

    assert estimate_default_total_requests("burst", 300.0) == len(
        scenario.generate_requests(duration_seconds=300.0)
    )


def test_estimate_default_total_requests_for_poisson() -> None:
    assert estimate_default_total_requests("poisson", 300.0) == 66000


def test_estimate_default_total_requests_for_pareto_long_tail() -> None:
    assert estimate_default_total_requests("pareto-long-tail", 300.0) == 54000