# rotation_tool/io_utils.py
from typing import List, Dict
import io
import re
import pandas as pd
from rotation_tool.data_model import GameData, Team, Player

# Exact headers expected (output order too)
HEADERS = [
    "Team",
    "Player id",
    "Player name",
    "Expected typical minutes",
    "Rotation archetype id",
    "Closer weighting",
    "Stint 0 minutes",
    "Stint 1 minutes",
    "Stint 2 minutes",
    "Stint 3 minutes",
    "Stint 4 minutes",
    "Stint 5 minutes",
    "Stint 6 minutes",
    "Stint 7 minutes",
    "Stint 8 minutes",
    "StandardDeviationScaler",
]
STINT_COLS = [f"Stint {i} minutes" for i in range(9)]

# Minimal set that must be present to build rows
REQUIRED_HEADERS = {
    "Team",
    "Player id",
    "Player name",
    "Expected typical minutes",
    "Rotation archetype id",
    "Closer weighting",
    "StandardDeviationScaler",
}

# -----------------------
# Helpers
# -----------------------


def _coerce_float(val, default=None):
    """Coerce to float, tolerating blanks, NaN, and '1,234.5' values."""
    if pd.isna(val) or val == "":
        return default
    try:
        if isinstance(val, str):
            val = val.strip().replace(",", "")
            if val == "":
                return default
        return float(val)
    except Exception:
        return default


def _read_dataframe_from_uploaded(file_like) -> pd.DataFrame:
    """
    Robustly read CSV from Streamlit's UploadedFile or any file-like.
    - Reads raw bytes once, then tries UTF-8-SIG -> UTF-8 -> Latin-1.
    - Uses delimiter inference (sep=None, engine='python').
    - Returns a DataFrame or raises ValueError with a friendly message.
    """
    # Get raw bytes (don't consume the file-like permanently)
    try:
        raw: bytes = file_like.getvalue()
    except AttributeError:
        raw = file_like.read()
        try:
            file_like.seek(0)
        except Exception:
            pass

    if not raw:
        raise ValueError("The uploaded file is empty.")

    last_err = None
    for encoding in ("utf-8-sig", "utf-8", "latin1"):
        try:
            text = raw.decode(encoding, errors="strict")
            sio = io.StringIO(text)
            # sep=None => sniff delimiter; engine='python' is flexible
            df = pd.read_csv(sio, sep=None, engine="python")
            if df is None or df.shape[1] == 0:
                continue
            return df
        except Exception as ex:
            last_err = ex
            continue

    raise ValueError(
        "Could not parse the uploaded CSV. "
        "Ensure it's a plain CSV (not .xlsx) and try re-saving as UTF-8."
    ) from last_err


def _normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """
    Strip BOM/whitespace, collapse inner spaces. Keeps original casing otherwise.
    """

    def norm(c: str) -> str:
        if not isinstance(c, str):
            c = str(c)
        c = c.replace("\ufeff", "")  # drop BOM if present
        c = c.strip()
        c = re.sub(r"\s+", " ", c)
        return c

    df = df.copy()
    df.columns = [norm(c) for c in df.columns]
    return df


def _map_columns_to_expected(df: pd.DataFrame) -> pd.DataFrame:
    """
    Map normalized incoming columns to our exact HEADERS where possible.
    This is tolerant to minor spacing/case quirks but will not invent columns.
    """
    norm_df = _normalize_columns(df)

    # Build a case-insensitive lookup for expected headers
    expected_map: Dict[str, str] = {h.lower(): h for h in HEADERS}

    new_cols = []
    for c in norm_df.columns:
        key = c.lower()
        mapped = expected_map.get(key)
        if mapped:
            new_cols.append(mapped)
        else:
            # keep unknowns as-is; we won't rely on them
            new_cols.append(c)

    norm_df.columns = new_cols
    return norm_df


# -----------------------
# Public API
# -----------------------


def load_csv(file_like) -> GameData:
    """
    Read, normalize, validate, and convert to GameData.
    Raises ValueError with a friendly message on structural problems.
    """
    df_raw = _read_dataframe_from_uploaded(file_like)
    df = _map_columns_to_expected(df_raw)

    # Validate required headers
    missing = [h for h in REQUIRED_HEADERS if h not in df.columns]
    if missing:
        raise ValueError("CSV is missing required columns: " + ", ".join(missing))

    game = GameData()
    home_players: List[Player] = []
    away_players: List[Player] = []

    # Iterate rows
    for _, row in df.iterrows():
        team_val = str(row.get("Team", "")).strip()
        if team_val not in ("HomeTeam", "AwayTeam"):
            # ignore rows for other teams / garbage
            continue

        player = Player(
            player_id=str(row.get("Player id", "")).strip(),
            name=str(row.get("Player name", "")).strip(),
            team=team_val,
            archetype_id=(str(row.get("Rotation archetype id", "")).strip() or None),
            expected_minutes=_coerce_float(row.get("Expected typical minutes"), 0.0)
            or 0.0,
            closer_weighting=_coerce_float(row.get("Closer weighting"), 0.0) or 0.0,
            stddev_scaler=_coerce_float(row.get("StandardDeviationScaler"), 1.0) or 1.0,
        )

        # Collect stint minutes (ignore blanks)
        raw: List[float] = []
        for col in STINT_COLS:
            if col in df.columns:
                v = _coerce_float(row.get(col), None)
                if v is not None:
                    raw.append(v)
        player.stints_raw = raw

        if team_val == "HomeTeam":
            home_players.append(player)
        else:
            away_players.append(player)

    game.home_team.players = home_players
    game.away_team.players = away_players
    return game


def export_csv(game: GameData) -> pd.DataFrame:
    """
    Transform GameData back to the exact CSV column layout.
    Always returns a DataFrame with HEADERS even if there are no players.
    """
    rows = []

    def _rows_for_team(team: Team):
        for p in team.players:
            row = {
                "Team": p.team,
                "Player id": p.player_id,
                "Player name": p.name,
                "Expected typical minutes": p.expected_minutes,
                "Rotation archetype id": p.archetype_id or "",
                "Closer weighting": p.closer_weighting,
                "StandardDeviationScaler": p.stddev_scaler,
            }
            for i, col in enumerate(STINT_COLS):
                row[col] = p.stints_raw[i] if i < len(p.stints_raw) else ""
            rows.append(row)

    _rows_for_team(game.home_team)
    _rows_for_team(game.away_team)

    return pd.DataFrame(rows, columns=HEADERS)
