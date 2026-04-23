from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ServerConfig:
    server_id: str
    max_concurrent: int = 1
    queue_limit: int | None = None


@dataclass(slots=True)
class ServerState:
    server_id: str
    active_requests: int = 0
    queued_requests: int = 0
    online: bool = True
