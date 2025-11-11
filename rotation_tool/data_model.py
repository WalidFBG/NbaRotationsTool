from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class Stint:
    start_min: float
    end_min: float


@dataclass
class Player:
    player_id: str
    name: str
    team: str  # "Home" or "Away"

    archetype_id: Optional[str] = None
    expected_minutes: float = 0.0
    closer_weighting: float = 0.0  # editable [0,1]
    stddev_scaler: float = 1.0  # default 1 if missing

    # Raw percentages from CSV/editor, aligned to stint_pattern order.
    # These are fractions (0..1). We'll edit minutes in UI and convert back here.
    stints_raw: List[float] = field(default_factory=list)

    # Optional concrete [start,end] stints for timeline (to be added later)
    stints: List[Stint] = field(default_factory=list)


@dataclass
class Team:
    name: str
    players: List[Player] = field(default_factory=list)


@dataclass
class GameData:
    home_team: Team = field(default_factory=lambda: Team(name="Home"))
    away_team: Team = field(default_factory=lambda: Team(name="Away"))
