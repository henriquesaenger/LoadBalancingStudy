from load_balancing_study.load_profiles import assign_general_load_types
from load_balancing_study.simulation import Request


def test_assign_general_load_types_uses_general_mix_and_expected_labels() -> None:
    requests = [
        Request(request_id=index + 1, arrival_time=float(index), service_time=0.1)
        for index in range(100)
    ]

    assigned = assign_general_load_types(requests, seed=19)

    counts = {"read": 0, "write": 0, "report": 0, "auth": 0}
    for request in assigned:
        load_type = request.source.split("-", 1)[0]
        counts[load_type] += 1

    assert len(assigned) == 100
    assert counts["read"] > counts["write"] > counts["report"]
    assert 5 <= counts["auth"] <= 8
    assert all(request.source.endswith("expected") for request in assigned)


def test_assign_general_load_types_preserves_weight_suffixes() -> None:
    requests = [
        Request(request_id=1, arrival_time=0.0, service_time=0.1, load_weight="below-expected"),
        Request(request_id=2, arrival_time=1.0, service_time=0.1, load_weight="expected"),
        Request(request_id=3, arrival_time=2.0, service_time=0.1, load_weight="above-expected"),
    ]

    assigned = assign_general_load_types(requests, seed=7)

    assert assigned[0].source.endswith("below-expected")
    assert assigned[1].source.endswith("expected")
    assert assigned[2].source.endswith("above-expected")