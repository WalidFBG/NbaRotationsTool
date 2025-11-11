import streamlit as st
import plotly.graph_objects as go
from rotation_tool.data_model import Team, Player
from rotation_tool.state_manager import (
    closer_sum,
    closer_status,
    expected_minutes_sum,
    expected_minutes_status,
    get_config,
    compute_segments,
    compute_default_boundaries,
    apply_boundaries,
    team_oncourt_steps,
)

MAIN_COL_SPECS = [0.9, 4.0, 5.0]

CTRL_COL_SPECS = [
    3.0,
    1.0,
    1.0,
    1.0,
    1.0,
]

# Timeline config
TICK_VALS = [0, 12, 24, 36, 48]
TICK_TEXT = ["0", "12", "24", "36", "48"]
TIMELINE_HEIGHT = 28  # thicker bars (was 10)

COLOR_ON_STARTER = "#D37000"
COLOR_ON_BENCH = "#3B82F6"
COLOR_OFF = "#20252C"
BOUNDARY_COLOR = "#6b7280"


def _is_starter_like(player: Player) -> bool:
    """Starter = archetype.is_starter OR archetype == 'Star'."""
    if not player.archetype_id:
        return False
    cfg = get_config()
    arch = cfg.archetypes.get(player.archetype_id)
    if not arch:
        return False
    return bool(getattr(arch, "starter", False) or player.archetype_id == "Star")


def _prev_keys(pid: str):
    return (f"prev_arch_{pid}", f"prev_exp_{pid}", f"ends_{pid}")


def _sync_ends_from_current(player):
    """
    Recompute end-times from the player's current (archetype, expected_minutes, stints_raw)
    and store them in session state so the editor matches the plot.
    """
    ends_key = f"ends_{player.player_id}"
    st.session_state[ends_key] = compute_default_boundaries(player)


def _team_header(team: Team):
    closer_total = closer_sum(team)
    closer_state = closer_status(closer_total)
    closer_color = "#16a34a" if closer_state == "ok" else "#dc2626"

    exp_total = expected_minutes_sum(team)
    exp_state = expected_minutes_status(exp_total)
    exp_color = "#16a34a" if exp_state == "ok" else "#dc2626"

    st.markdown(
        (
            f"**{team.name}**  ·  Closer total: "
            f"<span style='background:{closer_color};color:white;padding:1px 8px;border-radius:12px;'>{closer_total:.2f} / 5.00</span>"
            f"  ·  Expected minutes: "
            f"<span style='background:{exp_color};color:white;padding:1px 8px;border-radius:12px;'>{exp_total:.2f} / 240.00</span>"
        ),
        unsafe_allow_html=True,
    )
    # captions for problems (show both if both invalid)
    if closer_state != "ok":
        st.caption("Closer weighting must total 5.00 (±0.01).")
    if exp_state != "ok":
        st.caption("Expected minutes across players should total 240.00 (±0.01).")


def _timeline_key(player: Player) -> str:
    """Key depends on archetype, expected minutes, and the *values* of stints_raw."""
    nonce = st.session_state.get("render_nonce", 0)
    raw_sig = "_".join(
        f"{x:.4f}" for x in player.stints_raw
    )  # captures value changes even if same length
    arch = player.archetype_id or "NotSet"
    return f"tl_{player.team}_{player.player_id}_{arch}_{float(player.expected_minutes):.2f}_{raw_sig}_{nonce}"


def _timeline(player: Player):
    segs = compute_segments(player)  # [(start, end, tag)]
    fig = go.Figure()

    # boundaries at 0 and 48
    fig.add_vline(x=0, line_width=1, line_dash="solid", line_color=BOUNDARY_COLOR)
    fig.add_vline(x=48, line_width=1, line_dash="solid", line_color=BOUNDARY_COLOR)

    # draw segments as rectangles
    for start, end, tag in segs:
        if end <= start:
            continue
        fig.add_shape(
            type="rect",
            x0=start,
            x1=end,
            y0=0.0,
            y1=1.0,
            xref="x",
            yref="y",
            line=dict(width=0),
            fillcolor=(COLOR_ON_STARTER if _is_starter_like(player) else COLOR_ON_BENCH)
            if tag == "on"
            else COLOR_OFF,
            layer="below",
        )

    fig.update_xaxes(
        range=[0, 48],
        tickmode="array",
        tickvals=TICK_VALS,
        ticktext=TICK_TEXT,
        tickfont=dict(size=9),
        showgrid=True,
        zeroline=False,
        showline=True,
        mirror=True,
        ticks="outside",
        fixedrange=True,
    )
    fig.update_yaxes(visible=False, fixedrange=True, range=[0, 1])

    fig.update_layout(
        height=TIMELINE_HEIGHT,
        margin=dict(l=0, r=0, t=0, b=0),
        showlegend=False,
        dragmode=False,
    )

    st.plotly_chart(
        fig,
        width="stretch",
        key=_timeline_key(player),  # <- dynamic key tied to live values
    )


def _controls_header_row():
    """Header row aligned with player rows."""
    name_col, tl_col, ctrl_col = st.columns(MAIN_COL_SPECS, gap="small")
    with name_col:
        st.caption("Player Name")
    with tl_col:
        st.caption("Rotation Pattern")
    with ctrl_col:
        c_arch, c_exp, c_cw, c_sd, c_btn = st.columns(CTRL_COL_SPECS, gap="small")
        with c_arch:
            st.caption("Archetype")
        with c_exp:
            st.caption("Exp. Minutes")
        with c_cw:
            st.caption("Closer Weighting")
        with c_sd:
            st.caption("Std Scaler")
        with c_btn:
            st.caption("Stints")


def _player_row(player: Player):
    # Create the three aligned columns
    name_col, tl_col, ctrl_col = st.columns(MAIN_COL_SPECS, gap="small")

    # 1) Player name (left)
    with name_col:
        st.text(player.name)

    # ===== New: Stints editor (end-times) =====
    if st.session_state.get(f"editing_{player.player_id}"):
        # small spacing
        st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)

        cfg = get_config()
        if not player.archetype_id or player.archetype_id not in cfg.archetypes:
            st.warning("Select an archetype first.")
            st.session_state[f"editing_{player.player_id}"] = False
            st.rerun()

        arch = cfg.archetypes[player.archetype_id]
        L = len(arch.stint_pattern)
        if L <= 1:
            st.info("This archetype has a single stint; no sub times to edit.")
            st.session_state[f"editing_{player.player_id}"] = False
            st.rerun()

        ends_key = f"ends_{player.player_id}"
        if ends_key not in st.session_state:
            st.session_state[ends_key] = compute_default_boundaries(player)
        if len(st.session_state[ends_key]) != L - 1:
            st.session_state[ends_key] = compute_default_boundaries(player)

        current_ends = list(st.session_state[ends_key])

        # Horizontal inputs: exactly L-1 columns (t1..t{L-1})
        cols = st.columns([1] * (L - 1), gap="small")
        new_ends = []
        prev = 0.0
        min_gap = 0.001
        for i in range(L - 1):
            remaining = (L - 1) - (i + 1)
            max_allowed = 48.0 - remaining * min_gap
            val = current_ends[i] if i < len(current_ends) else prev + min_gap
            with cols[i]:
                st.caption(f"t{i + 1}")
                nv = st.number_input(
                    f"End Time {i + 1}",
                    min_value=float(prev + min_gap),
                    max_value=float(max_allowed),
                    step=0.5,
                    value=float(val),
                    key=f"end_{player.player_id}_{i}",
                    label_visibility="collapsed",
                )
            nv = max(prev + min_gap, min(max_allowed, float(nv)))
            new_ends.append(nv)
            prev = nv

        # Apply as user edits (instant update)
        # Apply as user edits (instant update)
        apply_boundaries(player, new_ends, min_gap=min_gap)
        st.session_state[ends_key] = new_ends

        # NEW: keep the Expected Minutes widget in sync with the new computed value
        exp_key = f"exp_{player.player_id}"
        st.session_state[exp_key] = float(
            player.expected_minutes
        )  # <— ensures control shows the updated value

        st.session_state["render_nonce"] = st.session_state.get("render_nonce", 0) + 1

        # Buttons — handle first, and return immediately to avoid double-click feel
        c1, _ = st.columns([1, 8])
        with c1:
            if st.button("Close", key=f"close_{player.player_id}"):
                _sync_ends_from_current(player)  # keep ends cached to match the plot
                st.session_state[f"editing_{player.player_id}"] = False
                # sync Expected Minutes widget so it doesn't snap back
                exp_key = f"exp_{player.player_id}"
                st.session_state[exp_key] = float(player.expected_minutes)
                st.session_state["render_nonce"] = (
                    st.session_state.get("render_nonce", 0) + 1
                )
                st.rerun()

                st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)

    # 2) Controls (RIGHT) — render first so widget updates apply *before* we draw the timeline
    with ctrl_col:
        cfg = get_config()
        arch_ids = ["NotSet"] + list(cfg.archetypes.keys())
        current = player.archetype_id or "NotSet"

        c_arch, c_exp, c_cw, c_sd, c_btn = st.columns(CTRL_COL_SPECS, gap="small")

        k_arch_prev, k_exp_prev, k_ends = _prev_keys(player.player_id)
        # ensure defaults exist before we read them
        st.session_state.setdefault(k_arch_prev, current)
        st.session_state.setdefault(k_exp_prev, float(player.expected_minutes))
        prev_arch = st.session_state[k_arch_prev]
        prev_exp = st.session_state[k_exp_prev]

        with c_arch:
            new_arch = st.selectbox(
                "Archetype",
                arch_ids,
                index=arch_ids.index(current) if current in arch_ids else 0,
                key=f"arch_{player.player_id}",
                label_visibility="collapsed",
            )
            player.archetype_id = None if new_arch == "NotSet" else new_arch

        with c_exp:
            exp_key = f"exp_{player.player_id}"
            if exp_key not in st.session_state:
                st.session_state[exp_key] = float(player.expected_minutes)
            new_exp = st.number_input(
                "Expected Minutes",
                min_value=0.0,
                max_value=48.0,
                step=0.5,
                key=exp_key,
                label_visibility="collapsed",
            )
            player.expected_minutes = float(new_exp)

        with c_cw:
            player.closer_weighting = st.number_input(
                "Closer Weighting",
                min_value=0.0,
                max_value=1.0,
                step=0.01,
                value=float(player.closer_weighting),
                key=f"cw_{player.player_id}",
                label_visibility="collapsed",
            )

        with c_sd:
            player.stddev_scaler = st.number_input(
                "Std Dev Scaler",
                min_value=0.0,
                step=0.1,
                value=float(player.stddev_scaler),
                key=f"sd_{player.player_id}",
                label_visibility="collapsed",
            )

        with c_btn:
            if st.button("Edit", key=f"edit_{player.player_id}", width="stretch"):
                st.session_state[f"editing_{player.player_id}"] = True
                # ensure ends are in sync when opening editor
                _sync_ends_from_current(player)
                st.session_state["render_nonce"] = (
                    st.session_state.get("render_nonce", 0) + 1
                )
                st.rerun()

    # if arch/exp changed, recompute ends so plot/editor stay aligned
    changed_arch = (player.archetype_id or "NotSet") != (prev_arch or "NotSet")
    changed_exp = float(player.expected_minutes) != float(prev_exp)

    if changed_arch:
        # Wipe any prior stint info so new archetype uses its default shape
        player.stints_raw = []  # empty triggers equal shares per on/off group via _ensure_default_percentages
        # Reset editor cache to match the new archetype
        _sync_ends_from_current(player)
        ends_key = f"ends_{player.player_id}"
        st.session_state[ends_key] = compute_default_boundaries(player)
        # Bump render key and store "prev" for next pass
        st.session_state["render_nonce"] = st.session_state.get("render_nonce", 0) + 1
        st.session_state[k_arch_prev] = player.archetype_id or "NotSet"
        st.session_state[k_exp_prev] = float(player.expected_minutes)

    elif changed_exp:
        # Same archetype, minutes changed → recompute ends to match new total
        _sync_ends_from_current(player)
        st.session_state["render_nonce"] = st.session_state.get("render_nonce", 0) + 1
        st.session_state[k_arch_prev] = player.archetype_id or "NotSet"
        st.session_state[k_exp_prev] = float(player.expected_minutes)

    # 3) Timeline (MIDDLE) — render AFTER controls so it reflects latest values in the same rerun
    with tl_col:
        _timeline(player)


def render_team_panel(team: Team):
    # Render header AFTER rows (so closer total reflects latest edits)
    header_ph = st.container()

    # Split players while keeping original relative order (stable)
    starters = [p for p in team.players if _is_starter_like(p)]
    bench = [p for p in team.players if not _is_starter_like(p)]

    _controls_header_row()

    if starters:
        st.caption("Starters")
        for p in starters:
            _player_row(p)

    if bench:
        st.caption("Bench")
        for p in bench:
            _player_row(p)

    # Now show the header with the fresh closer total (appears at top via placeholder)
    with header_ph:
        _team_header(team)


def render_oncourt_chart(team: Team):
    xs, ys = team_oncourt_steps(team)

    # Dynamic key that changes whenever players' rotations change
    nonce = st.session_state.get("render_nonce", 0)
    # simple signature: team name + number of points + last value
    sig = f"{team.name}_{len(xs)}_{ys[-1] if ys else 0}_{nonce}"

    fig = go.Figure()

    # main step line (right-constant)
    fig.add_trace(
        go.Scatter(
            x=xs,
            y=ys,
            mode="lines",
            line=dict(width=2),
            name="# on court",
            hovertemplate="t=%{x:.1f}m<br>#=%{y}<extra></extra>",
        )
    )

    # horizontal target at y=5
    fig.add_hline(y=5, line_dash="dot", line_color="#9ca3af", opacity=0.9)

    fig.update_layout(
        height=140,
        margin=dict(l=4, r=4, t=6, b=6),
        showlegend=False,
    )
    fig.update_xaxes(
        range=[0, 48],
        tickmode="array",
        tickvals=[0, 12, 24, 36, 48],
        ticktext=["0", "12", "24", "36", "48"],
        showgrid=True,
        fixedrange=True,
    )
    fig.update_yaxes(
        range=[0, max(6, max(ys) + 1 if ys else 6)],
        dtick=1,
        showgrid=True,
        fixedrange=True,
    )

    st.plotly_chart(fig, width="stretch", key=f"oncourt_{sig}")
