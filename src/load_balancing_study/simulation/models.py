from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Request:
    request_id: int
    arrival_time: float
    service_time: float
    source: str = "default"
    load_type: str = "unassigned"
    load_weight: str = "expected"
    workload_origin: str = "default"


@dataclass(frozen=True, slots=True)
class SimulationInput:
    duration_seconds: float
    requests: list[Request]


@dataclass(frozen=True, slots=True)
class Assignment:
    request_id: int
    server_id: str
    start_time: float
    end_time: float
    source: str = "default"


@dataclass(frozen=True, slots=True)
class SimulationOutput:
    assignments: list[Assignment]
    dropped_requests: int = 0
