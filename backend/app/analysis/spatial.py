"""Conservative, versioned Summoner's Rift position heuristic, not path tracking."""
from math import hypot, isfinite


LANE_WIDTH = 1100
LANES = {
    "top": ((1800, 2500), (1800, 12000), (2800, 13000), (12000, 13000)),
    "bottom": ((2500, 1800), (12000, 1800), (13000, 2800), (13000, 12000)),
    "middle": ((2500, 2500), (12500, 12500)),
}


def segment_distance(x, y, start, end):
    dx, dy = end[0] - start[0], end[1] - start[1]
    fraction = max(0, min(1, ((x - start[0]) * dx + (y - start[1]) * dy) / (dx * dx + dy * dy)))
    return hypot(x - start[0] - fraction * dx, y - start[1] - fraction * dy)


def classify_position(position: dict | None) -> str | None:
    if not isinstance(position, dict):
        return None
    x, y = position.get("x"), position.get("y")
    if any(type(value) not in (int, float) or not isfinite(value) or not 0 <= value <= 15000 for value in (x, y)):
        return None
    # The origin is also used for unavailable positions.
    if x == 0 and y == 0:
        return None
    if min(hypot(x - 1200, y - 1200), hypot(x - 13800, y - 13800)) < 2500:
        return "base"
    distances = sorted((
        min(segment_distance(x, y, a, b) for a, b in zip(points, points[1:])), lane
    ) for lane, points in LANES.items())
    if distances[0][0] > LANE_WIDTH:
        return "jungle_or_river"
    if distances[1][0] - distances[0][0] < 300:
        return None
    return distances[0][1]
