from dataclasses import dataclass
from typing import Dict, List, Tuple
from rotation_tool.data_model import Team, Player
from math import isclose
from rotation_tool.archetypes import ARCHETYPES


@dataclass
class Archetype:
    id: str
    name: str
    starter: bool
    stint_pattern: List[str]  # e.g., ["on","off","on"]


class Config:
    def __init__(self, archetypes: Dict[str, Archetype]):
        self.archetypes = archetypes


def get_config() -> Config:
    """Load archetypes directly from the embedded dictionary."""
    data = ARCHETYPES
    arch_map = {}
    for item in data["archetypes"]:
        arch = Archetype(
            id=item["id"],
            name=item.get("name", item["id"]),
            starter=bool(item.get("starter", False)),
            stint_pattern=list(item.get("stint_pattern", [])),
        )
        arch_map[arch.id] = arch
    return Config(arch_map)


# ----- Validation helpers -----
def closer_sum(team: Team) -> float:
    # Clamp each player to [0,1] to avoid weird inputs, then sum
    return round(sum(max(0.0, min(1.0, p.closer_weighting)) for p in team.players), 6)


def closer_status(total: float, tol: float = 0.01) -> str:
    # green if within tol of 5.0, red otherwise
    return "ok" if abs(total - 5.0) <= tol else "bad"


# ----- Expected minutes (team total should be 240 = 5 * 48) -----
def expected_minutes_sum(team: Team) -> float:
    """Return the sum of players' expected minutes, clamped to [0,48] each."""
    return round(
        sum(max(0.0, min(48.0, float(p.expected_minutes or 0.0))) for p in team.players),
        6,
    )


def expected_minutes_status(total: float, target: float = 240.0, tol: float = 0.01) -> str:
    """Return 'ok' if team total is within tolerance of target (240), else 'bad'."""
    return "ok" if abs(total - target) <= tol else "bad"


def split_on_off_indices(archetype_id: str) -> Tuple[List[int], List[int]]:
    cfg = get_config()
    arch = cfg.archetypes.get(archetype_id)
    if not arch:
        return [], []
    on_idx, off_idx = [], []
    for i, tag in enumerate(arch.stint_pattern):
        (on_idx if tag == "on" else off_idx).append(i)
    return on_idx, off_idx


def split_on_off_sums(player: Player) -> Tuple[float, float] | None:
    if not player.archetype_id:
        return None
    on_idx, off_idx = split_on_off_indices(player.archetype_id)
    on_sum = sum(player.stints_raw[i] for i in on_idx if i < len(player.stints_raw))
    off_sum = sum(player.stints_raw[i] for i in off_idx if i < len(player.stints_raw))
    return (on_sum, off_sum)


# ----- NEW: Make concrete [start,end] segments for the timeline -----
def _ensure_default_percentages(player: Player) -> List[float]:
    """
    Ensure stints_raw matches the archetype length and has sensible defaults.
    - If sums for 'on' or 'off' are zero, distribute equally within that group.
    - Keep any existing numbers as-is (no auto-normalize to 1.0 — validation will flag).
    """
    if not player.archetype_id:
        return player.stints_raw

    cfg = get_config()
    arch = cfg.archetypes.get(player.archetype_id)
    if not arch:
        return player.stints_raw

    L = len(arch.stint_pattern)
    raw = list(player.stints_raw) + [0.0] * max(0, L - len(player.stints_raw))
    on_idx, off_idx = split_on_off_indices(player.archetype_id)

    # If all zeros in a group, fill equal shares
    on_sum = sum(raw[i] for i in on_idx)
    off_sum = sum(raw[i] for i in off_idx)

    if on_idx and on_sum == 0:
        eq = 1.0 / len(on_idx)
        for i in on_idx:
            raw[i] = eq

    if off_idx and off_sum == 0:
        eq = 1.0 / len(off_idx)
        for i in off_idx:
            raw[i] = eq

    return raw[:L]


def compute_segments(player: Player) -> List[Tuple[float, float, str]]:
    """
    Return a list of segments (start_min, end_min, tag) covering 0..48 in the archetype order.
    tag is "on" or "off".
    Uses expected_minutes + stints_raw percentages.
    IMPORTANT: No proportional rescaling — honors the implicit 48 total from apply_boundaries.
    """
    if not player.archetype_id:
        return []

    cfg = get_config()
    arch = cfg.archetypes.get(player.archetype_id)
    if not arch:
        return []

    raw = _ensure_default_percentages(player)
    on_idx, off_idx = split_on_off_indices(player.archetype_id)

    on_total = max(0.0, min(48.0, float(player.expected_minutes or 0.0)))
    off_total = max(0.0, 48.0 - on_total)

    # Durations in archetype order
    durations: List[float] = []
    for i, tag in enumerate(arch.stint_pattern):
        pct = raw[i] if i < len(raw) else 0.0
        if tag == "on":
            durations.append((pct * on_total) if on_total > 0 else 0.0)
        else:
            durations.append((pct * off_total) if off_total > 0 else 0.0)

    # Accumulate to [start,end], without any global scaling
    segs: List[Tuple[float, float, str]] = []
    t = 0.0
    for i, tag in enumerate(arch.stint_pattern):
        d = max(0.0, durations[i])
        start = t
        end = min(48.0, start + d)
        segs.append((start, end, tag))
        t = end

    # Ensure we always end at 48.0 (tiny drift guard)
    if segs:
        s, _, tag = segs[-1]
        segs[-1] = (s, 48.0, tag)

    return segs


def compute_default_boundaries(player: Player) -> List[float]:
    """
    Return the default boundary list (end time of each stint) excluding the final 48.
    Uses compute_segments(player) to get current [start,end] per stint.
    """
    segs = compute_segments(player)
    if not segs:
        return []
    # end times of all but the last segment (which ends at 48 by definition)
    ends = [end for (_, end, _) in segs[:-1]]
    # Clamp to [0,48] and strictly increasing (best-effort)
    out = []
    last = 0.0
    for e in ends:
        val = max(last + 0.001, min(48.0, float(e)))
        out.append(val)
        last = val
    return out


def apply_boundaries(player: Player, ends: List[float], min_gap: float = 0.001) -> None:
    """
    Apply a list of monotonically increasing boundaries (end-times) to the player.
    - ends has length L-1 where L is the archetype stint count.
    - Recomputes per-stint durations, updates:
        * player.expected_minutes  = total of 'on' durations
        * player.stints_raw[i]     = duration_i / (on_total or off_total)
    """
    if not player.archetype_id:
        return
    cfg = get_config()
    arch = cfg.archetypes.get(player.archetype_id)
    if not arch:
        return

    L = len(arch.stint_pattern)
    if L <= 0:
        return

    # Sanitize incoming ends → strictly increasing in (0,48), length L-1
    ends = list(ends[: L - 1])
    out_ends: List[float] = []
    last = 0.0
    for k in range(L - 1):
        raw = float(ends[k] if k < len(ends) else last + min_gap)
        val = max(last + min_gap, min(48.0 - (L - 1 - (k + 1)) * min_gap, raw))
        out_ends.append(val)
        last = val

    # Build [start,end] segments from boundaries
    seg_starts: List[float] = []
    seg_ends: List[float] = []
    t = 0.0
    for e in out_ends:
        seg_starts.append(t)
        seg_ends.append(e)
        t = e
    # final segment to 48
    seg_starts.append(t)
    seg_ends.append(48.0)

    # Durations and totals
    durations = [max(0.0, seg_ends[i] - seg_starts[i]) for i in range(L)]
    on_idx, off_idx = split_on_off_indices(player.archetype_id)
    on_total = sum(durations[i] for i in on_idx)
    off_total = sum(durations[i] for i in off_idx)

    # Update expected minutes to reflect 'on' total
    player.expected_minutes = max(0.0, min(48.0, on_total))

    # Update stints_raw percentages from durations (robust to zero totals)
    raw: List[float] = [0.0] * L
    for i in on_idx:
        raw[i] = durations[i] / on_total if on_total > 0 else 0.0
    for i in off_idx:
        raw[i] = durations[i] / off_total if off_total > 0 else 0.0
    player.stints_raw = raw


def team_oncourt_steps(team) -> Tuple[List[float], List[int]]:
    """
    Return piecewise-constant step series (xs, ys) over [0,48] for how many players are on court.
    Uses compute_segments(player) and counts "on" segments across all players.
    """
    events: List[Tuple[float, int]] = []  # (time, delta)
    for p in team.players:
        segs = compute_segments(p)
        for s, e, tag in segs:
            if tag == "on" and e > s:
                s = max(0.0, min(48.0, float(s)))
                e = max(0.0, min(48.0, float(e)))
                events.append((s, +1))
                events.append((e, -1))

    # Ensure we always have the domain
    events.append((0.0, 0))
    events.append((48.0, 0))

    # Sort, and for ties apply all -1 before +1 so a sub-out at t and sub-in at t keeps count consistent
    events.sort(key=lambda x: (x[0], x[1]))

    xs: List[float] = []
    ys: List[int] = []
    curr = 0
    last_t = 0.0

    # Build right-constant steps (Plotly shape='hv' handles the visual)
    for t, d in events:
        t = float(t)
        if not xs:
            xs.append(last_t)
            ys.append(curr)
        if t != last_t:
            xs.append(t)
            ys.append(curr)  # horizontal run to t
            last_t = t
        curr += d
        xs.append(t)
        ys.append(curr)  # vertical jump at t

    # Clamp domain and tidy duplicates
    # (Plotly tolerates duplicates; this keeps arrays small)
    out_x, out_y = [xs[0]], [ys[0]]
    for i in range(1, len(xs)):
        if not (isclose(xs[i], out_x[-1]) and ys[i] == out_y[-1]):
            out_x.append(xs[i])
            out_y.append(ys[i])

    # Ensure final point at 48
    if out_x[-1] != 48.0:
        out_x.append(48.0)
        out_y.append(out_y[-1])

    return out_x, out_y
