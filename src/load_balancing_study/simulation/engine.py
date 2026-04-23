import heapq
from dataclasses import dataclass
from collections.abc import Sequence
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from load_balancing_study.algorithms.base import LoadBalancingAlgorithm
from load_balancing_study.load_profiles import assign_general_load_types
from load_balancing_study.scenarios import Scenario
from load_balancing_study.servers import ServerConfig, ServerState
from load_balancing_study.simulation.models import Assignment, Request, SimulationInput, SimulationOutput


@dataclass(frozen=True, slots=True)
class WorkloadSource:
    name: str
    scenario: Scenario
    start_time_seconds: float = 0.0
    duration_seconds: float | None = None
    seed: int | None = None


@dataclass(order=True, frozen=True, slots=True)
class _ScheduledEvent:
    time: float
    priority: int
    delta_active: int
    delta_queued: int


class _ServerRuntime:
    def __init__(self, config: ServerConfig) -> None:
        if config.max_concurrent <= 0:
            raise ValueError(f"server '{config.server_id}' max_concurrent must be > 0")
        if config.queue_limit is not None and config.queue_limit < 0:
            raise ValueError(f"server '{config.server_id}' queue_limit must be >= 0")

        self.config = config
        self._state = ServerState(server_id=config.server_id)
        self._applied_until = 0.0
        self._slots_available_at = [0.0] * config.max_concurrent
        self._scheduled_events: list[_ScheduledEvent] = []

    def snapshot(self, at_time: float) -> ServerState:
        self._advance_to(at_time)
        return ServerState(
            server_id=self.config.server_id,
            active_requests=self._state.active_requests,
            queued_requests=self._state.queued_requests,
            online=self._state.online,
        )

    def can_accept(self, at_time: float) -> bool:
        self._advance_to(at_time)
        if self.config.queue_limit is None:
            return True

        return self._state.queued_requests < self.config.queue_limit

    def schedule(self, request: Request) -> Assignment:
        self._advance_to(request.arrival_time)

        slot_index = min(
            range(len(self._slots_available_at)),
            key=lambda index: self._slots_available_at[index],
        )
        start_time = max(request.arrival_time, self._slots_available_at[slot_index])
        end_time = start_time + request.service_time
        self._slots_available_at[slot_index] = end_time

        if start_time > request.arrival_time:
            self._state.queued_requests += 1
            heapq.heappush(
                self._scheduled_events,
                _ScheduledEvent(
                    time=start_time,
                    priority=1,
                    delta_active=1,
                    delta_queued=-1,
                ),
            )
        else:
            self._state.active_requests += 1

        heapq.heappush(
            self._scheduled_events,
            _ScheduledEvent(
                time=end_time,
                priority=0,
                delta_active=-1,
                delta_queued=0,
            ),
        )

        return Assignment(
            request_id=request.request_id,
            server_id=self.config.server_id,
            start_time=start_time,
            end_time=end_time,
            source=request.source,
        )

    def _advance_to(self, at_time: float) -> None:
        if at_time < self._applied_until:
            raise ValueError("server runtime cannot move backwards in time")

        while self._scheduled_events and self._scheduled_events[0].time <= at_time:
            event = heapq.heappop(self._scheduled_events)
            self._state.active_requests += event.delta_active
            self._state.queued_requests += event.delta_queued

            if self._state.active_requests < 0 or self._state.queued_requests < 0:
                raise RuntimeError(
                    f"server '{self.config.server_id}' produced an invalid runtime state"
                )

        self._applied_until = at_time


class SimulationEngine:
    def build_input(
        self,
        duration_seconds: float,
        workloads: Sequence[WorkloadSource],
        total_requests: int | None = None,
        seed: int | None = None,
    ) -> SimulationInput:
        if duration_seconds <= 0:
            raise ValueError("duration_seconds must be > 0")
        if total_requests is not None and total_requests <= 0:
            raise ValueError("total_requests must be > 0 when provided")
        if not workloads:
            return SimulationInput(duration_seconds=duration_seconds, requests=[])

        requests: list[Request] = []
        next_request_id = 1
        apply_total_requests_during_generation = total_requests is not None and len(workloads) == 1

        for index, workload in enumerate(workloads):
            self._validate_workload(workload)
            if workload.start_time_seconds >= duration_seconds:
                continue

            available_duration = duration_seconds - workload.start_time_seconds
            scenario_duration = workload.duration_seconds
            if scenario_duration is None:
                scenario_duration = available_duration
            else:
                scenario_duration = min(scenario_duration, available_duration)

            if scenario_duration <= 0:
                continue

            scenario_seed = workload.seed
            if scenario_seed is None and seed is not None:
                scenario_seed = seed + index

            generated = workload.scenario.generate_requests(
                duration_seconds=scenario_duration,
                seed=scenario_seed,
                total_requests=total_requests if apply_total_requests_during_generation else None,
            )
            for generated_request in generated:
                if generated_request.service_time <= 0:
                    raise ValueError("request service_time must be > 0")

                arrival_time = generated_request.arrival_time + workload.start_time_seconds
                if arrival_time < 0 or arrival_time >= duration_seconds:
                    continue

                requests.append(
                    Request(
                        request_id=next_request_id,
                        arrival_time=arrival_time,
                        service_time=generated_request.service_time,
                        source=generated_request.source,
                        load_type=generated_request.load_type,
                        load_weight=generated_request.load_weight,
                        workload_origin=workload.name,
                    )
                )
                next_request_id += 1

        requests.sort(key=lambda request: (request.arrival_time, request.request_id))
        if total_requests is not None:
            requests = requests[:total_requests]
        requests = assign_general_load_types(requests, seed=seed)

        return SimulationInput(duration_seconds=duration_seconds, requests=requests)

    def build_input_from_scenario(
        self,
        scenario: Scenario,
        duration_seconds: float,
        total_requests: int | None = None,
        seed: int | None = None,
    ) -> SimulationInput:
        return self.build_input(
            duration_seconds=duration_seconds,
            workloads=[
                WorkloadSource(
                    name=scenario.name,
                    scenario=scenario,
                    start_time_seconds=0.0,
                    duration_seconds=duration_seconds,
                    seed=seed,
                )
            ],
            total_requests=total_requests,
        )

    def run(
        self,
        simulation_input: SimulationInput,
        server_configs: Sequence[ServerConfig],
        algorithm: "LoadBalancingAlgorithm",
    ) -> SimulationOutput:
        if simulation_input.duration_seconds <= 0:
            raise ValueError("simulation_input.duration_seconds must be > 0")
        if not server_configs:
            raise ValueError("server_configs must not be empty")

        runtime_by_server = self._build_runtime(server_configs)
        runtimes_in_order = [runtime_by_server[config.server_id] for config in server_configs]

        algorithm.reset(server_configs)

        assignments: list[Assignment] = []
        dropped_requests = 0

        ordered_requests = sorted(
            simulation_input.requests,
            key=lambda request: (request.arrival_time, request.request_id),
        )

        for request in ordered_requests:
            if request.arrival_time < 0:
                continue
            if request.arrival_time >= simulation_input.duration_seconds:
                continue
            if request.service_time <= 0:
                raise ValueError("request service_time must be > 0")

            server_states = [runtime.snapshot(request.arrival_time) for runtime in runtimes_in_order]
            selected_server_id = algorithm.select_server(request, server_states)

            if selected_server_id is None:
                dropped_requests += 1
                continue

            runtime = runtime_by_server.get(selected_server_id)
            if runtime is None:
                raise ValueError(f"algorithm selected unknown server '{selected_server_id}'")

            if not runtime.can_accept(request.arrival_time):
                dropped_requests += 1
                continue

            assignments.append(runtime.schedule(request))

        assignments.sort(key=lambda assignment: (assignment.start_time, assignment.request_id))
        return SimulationOutput(assignments=assignments, dropped_requests=dropped_requests)

    def run_workloads(
        self,
        duration_seconds: float,
        workloads: Sequence[WorkloadSource],
        server_configs: Sequence[ServerConfig],
        algorithm: "LoadBalancingAlgorithm",
        seed: int | None = None,
    ) -> SimulationOutput:
        simulation_input = self.build_input(
            duration_seconds=duration_seconds,
            workloads=workloads,
            seed=seed,
        )
        return self.run(
            simulation_input=simulation_input,
            server_configs=server_configs,
            algorithm=algorithm,
        )

    def _build_runtime(self, server_configs: Sequence[ServerConfig]) -> dict[str, _ServerRuntime]:
        runtime_by_server: dict[str, _ServerRuntime] = {}
        for config in server_configs:
            if config.server_id in runtime_by_server:
                raise ValueError(f"duplicate server_id '{config.server_id}'")
            runtime_by_server[config.server_id] = _ServerRuntime(config)

        return runtime_by_server

    def _validate_workload(self, workload: WorkloadSource) -> None:
        if not workload.name.strip():
            raise ValueError("workload name must be a non-empty string")
        if workload.start_time_seconds < 0:
            raise ValueError("workload start_time_seconds must be >= 0")
        if workload.duration_seconds is not None and workload.duration_seconds < 0:
            raise ValueError("workload duration_seconds must be >= 0")
