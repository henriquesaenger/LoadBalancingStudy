from collections.abc import Sequence

from load_balancing_study.algorithms import RoundRobinAlgorithm
from load_balancing_study.algorithms.base import LoadBalancingAlgorithm
from load_balancing_study.scenarios import ConstantRateScenario
from load_balancing_study.servers import ServerConfig, ServerState
from load_balancing_study.simulation import Request, SimulationEngine, SimulationInput, WorkloadSource


class RecordingAlgorithm(LoadBalancingAlgorithm):
    name = "recording"

    def __init__(self) -> None:
        self.observed_states: list[tuple[int, int, int]] = []

    def select_server(self, request: Request, server_states: Sequence[ServerState]) -> str | None:
        state = server_states[0]
        self.observed_states.append((request.request_id, state.active_requests, state.queued_requests))
        return state.server_id


def test_build_input_merges_overlapping_workloads() -> None:
    engine = SimulationEngine()
    workloads = [
        WorkloadSource(
            name="steady",
            scenario=ConstantRateScenario(requests_per_second=2.0, service_time_seconds=0.5),
            start_time_seconds=0.0,
            duration_seconds=3.0,
        ),
        WorkloadSource(
            name="burst",
            scenario=ConstantRateScenario(requests_per_second=4.0, service_time_seconds=0.25),
            start_time_seconds=1.0,
            duration_seconds=2.0,
        ),
    ]

    simulation_input = engine.build_input(duration_seconds=4.0, workloads=workloads)

    assert len(simulation_input.requests) == 14
    assert simulation_input.requests == sorted(
        simulation_input.requests,
        key=lambda request: (request.arrival_time, request.request_id),
    )
    origins = {request.workload_origin for request in simulation_input.requests}
    assert origins == {"steady", "burst"}
    assert all(
        request.source.startswith(("read-", "write-", "report-", "auth-"))
        for request in simulation_input.requests
    )


def test_build_input_applies_total_requests_cap_after_sorting() -> None:
    engine = SimulationEngine()
    workloads = [
        WorkloadSource(
            name="steady",
            scenario=ConstantRateScenario(requests_per_second=2.0, service_time_seconds=0.5),
            start_time_seconds=0.0,
            duration_seconds=3.0,
        ),
        WorkloadSource(
            name="burst",
            scenario=ConstantRateScenario(requests_per_second=4.0, service_time_seconds=0.25),
            start_time_seconds=1.0,
            duration_seconds=2.0,
        ),
    ]

    simulation_input = engine.build_input(
        duration_seconds=4.0,
        workloads=workloads,
        total_requests=5,
    )

    assert len(simulation_input.requests) == 5
    assert simulation_input.requests == sorted(
        simulation_input.requests,
        key=lambda request: (request.arrival_time, request.request_id),
    )


def test_build_input_from_single_scenario_generates_exact_total_requests() -> None:
    engine = SimulationEngine()

    simulation_input = engine.build_input_from_scenario(
        scenario=ConstantRateScenario(requests_per_second=2.0, service_time_seconds=0.5),
        duration_seconds=3.0,
        total_requests=9,
        seed=7,
    )

    assert len(simulation_input.requests) == 9
    assert simulation_input.requests == sorted(
        simulation_input.requests,
        key=lambda request: (request.arrival_time, request.request_id),
    )
    assert simulation_input.requests[-1].arrival_time < 3.0
    gaps = [
        round(current.arrival_time - previous.arrival_time, 6)
        for previous, current in zip(simulation_input.requests, simulation_input.requests[1:])
    ]
    assert len(set(gaps)) > 1


def test_run_respects_queue_limit_and_drops_excess_requests() -> None:
    engine = SimulationEngine()
    simulation_input = SimulationInput(
        duration_seconds=5.0,
        requests=[
            Request(request_id=1, arrival_time=0.0, service_time=1.0),
            Request(request_id=2, arrival_time=0.0, service_time=1.0),
            Request(request_id=3, arrival_time=0.0, service_time=1.0),
            Request(request_id=4, arrival_time=0.0, service_time=1.0),
        ],
    )
    server_configs = [ServerConfig(server_id="s1", max_concurrent=1, queue_limit=1)]

    output = engine.run(
        simulation_input=simulation_input,
        server_configs=server_configs,
        algorithm=RoundRobinAlgorithm(),
    )

    assert len(output.assignments) == 2
    assert output.dropped_requests == 2
    assert output.assignments[0].request_id == 1
    assert output.assignments[0].start_time == 0.0
    assert output.assignments[1].request_id == 2
    assert output.assignments[1].start_time == 1.0


def test_run_updates_server_state_over_time() -> None:
    engine = SimulationEngine()
    simulation_input = SimulationInput(
        duration_seconds=5.0,
        requests=[
            Request(request_id=1, arrival_time=0.0, service_time=1.0),
            Request(request_id=2, arrival_time=0.0, service_time=1.0),
            Request(request_id=3, arrival_time=0.5, service_time=1.0),
            Request(request_id=4, arrival_time=1.0, service_time=1.0),
        ],
    )
    server_configs = [ServerConfig(server_id="s1", max_concurrent=1, queue_limit=2)]
    algorithm = RecordingAlgorithm()

    engine.run(
        simulation_input=simulation_input,
        server_configs=server_configs,
        algorithm=algorithm,
    )

    assert algorithm.observed_states == [
        (1, 0, 0),
        (2, 1, 0),
        (3, 1, 1),
        (4, 1, 1),
    ]
