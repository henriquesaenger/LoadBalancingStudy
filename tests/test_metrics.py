from load_balancing_study.metrics import calculate_metrics
from load_balancing_study.simulation import Assignment, Request, SimulationInput, SimulationOutput


def test_calculate_metrics_returns_core_indicators() -> None:
    simulation_input = SimulationInput(
        duration_seconds=10.0,
        requests=[
            Request(request_id=1, arrival_time=0.0, service_time=1.0, source="steady"),
            Request(request_id=2, arrival_time=1.0, service_time=1.0, source="steady"),
            Request(request_id=3, arrival_time=2.0, service_time=1.0, source="burst"),
        ],
    )
    simulation_output = SimulationOutput(
        assignments=[
            Assignment(request_id=1, server_id="s1", start_time=0.0, end_time=1.0, source="steady"),
            Assignment(request_id=2, server_id="s2", start_time=2.0, end_time=3.0, source="steady"),
        ],
        dropped_requests=1,
    )

    metrics = calculate_metrics(
        simulation_input=simulation_input,
        simulation_output=simulation_output,
        server_ids=["s1", "s2", "s3"],
    )

    assert metrics.total_requests == 3
    assert metrics.served_requests == 2
    assert metrics.dropped_requests == 1
    assert metrics.drop_rate == 1 / 3
    assert metrics.throughput_rps == 0.2
    assert metrics.avg_latency_seconds == 1.5
    assert metrics.p95_latency_seconds == 2.0
    assert metrics.avg_wait_seconds == 0.5
    assert metrics.avg_service_seconds == 1.0

    assert [(item.server_id, item.served_requests) for item in metrics.server_distribution] == [
        ("s1", 1),
        ("s2", 1),
        ("s3", 0),
    ]
    assert [(item.source, item.total_requests, item.served_requests, item.dropped_requests) for item in metrics.source_distribution] == [
        ("burst", 1, 0, 1),
        ("steady", 2, 2, 0),
    ]
