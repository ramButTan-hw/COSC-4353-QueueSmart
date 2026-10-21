"""Shared rule-based estimate extracted from the wait-time prototype."""

def estimate_wait_minutes(position: int, expected_duration_minutes: int) -> int:
    """
    Rule: wait time = position x expected duration per person.
    Position is 1-based (1 = next in line). Returns 0 for position <= 0.
    """
    if position <= 0:
        return 0
    return position * expected_duration_minutes

