from load_balancing_study.scenarios import (
    BurstScenario,
    ConstantRateScenario,
    ParetoLongTailScenario,
    PoissonArrivalScenario,
)


def test_constant_rate_scenario_respects_total_requests() -> None:
    scenario = ConstantRateScenario(
        requests_per_second=2.0,
        service_time_seconds=0.2,
    )

    requests = scenario.generate_requests(duration_seconds=5.0, seed=11, total_requests=13)
    repeated = scenario.generate_requests(duration_seconds=5.0, seed=11, total_requests=13)

    assert len(requests) == 13
    assert requests == repeated
    assert 0.0 <= requests[0].arrival_time < 5.0
    assert requests[-1].arrival_time < 5.0
    gaps = [
        round(current.arrival_time - previous.arrival_time, 6)
        for previous, current in zip(requests, requests[1:])
    ]
    assert len(set(gaps)) > 1


def test_poisson_arrival_scenario_is_reproducible_with_seed() -> None:
    scenario = PoissonArrivalScenario(
        requests_per_second=6.0,
        service_time_seconds=0.2,
    )

    first_run = scenario.generate_requests(duration_seconds=5.0, seed=7, total_requests=17)
    second_run = scenario.generate_requests(duration_seconds=5.0, seed=7, total_requests=17)

    assert first_run == second_run
    assert len(first_run) == 17
    assert len({round(request.arrival_time, 6) for request in first_run}) == len(first_run)


def test_pareto_long_tail_scenario_generates_service_times_above_minimum() -> None:
    scenario = ParetoLongTailScenario(
        requests_per_second=5.0,
        service_time_min_seconds=0.05,
        service_time_alpha=1.5,
    )

    requests = scenario.generate_requests(duration_seconds=3.0, seed=5, total_requests=11)
    repeated = scenario.generate_requests(duration_seconds=3.0, seed=5, total_requests=11)

    assert len(requests) == 11
    assert requests == repeated
    assert all(request.service_time >= 0.05 for request in requests)
    assert any(request.service_time > 0.05 for request in requests)


def test_burst_scenario_respects_total_requests() -> None:
    scenario = BurstScenario(
        base_requests_per_second=2.0,
        burst_requests_per_second=8.0,
        burst_start_seconds=1.0,
        burst_end_seconds=3.0,
        service_time_seconds=0.2,
        time_resolution_seconds=0.5,
    )

    requests = scenario.generate_requests(duration_seconds=4.0, seed=23, total_requests=19)
    repeated = scenario.generate_requests(duration_seconds=4.0, seed=23, total_requests=19)

    assert len(requests) == 19
    assert requests == repeated
    assert all(0.0 <= request.arrival_time < 4.0 for request in requests)
    burst_requests = sum(1 for request in requests if 1.0 <= request.arrival_time < 3.0)
    assert burst_requests > len(requests) - burst_requests