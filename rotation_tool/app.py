import hashlib
import traceback
import threading
import time
import os
import streamlit as st

from rotation_tool.io_utils import load_csv, export_csv
from rotation_tool.visuals import render_team_panel, render_oncourt_chart
from rotation_tool.data_model import GameData


# ---- Auto-exit when no sessions are open ----
def _auto_exit_when_no_sessions(grace_seconds: int = 5, poll_interval: float = 0.5):
    """
    Exit the process automatically when Streamlit has zero active sessions
    for `grace_seconds`. Uses private runtime API; pin Streamlit version.
    """
    if "_auto_exit_started" in st.session_state:
        return
    st.session_state["_auto_exit_started"] = True

    def _watcher():
        try:
            from streamlit.runtime import get_instance

            rt = get_instance()
        except Exception:
            time.sleep(1.0)
            return _watcher()

        stable_zero_since = None
        while True:
            try:
                active = len(rt._session_mgr.list_active_sessions())
                now = time.time()
                if active == 0:
                    if stable_zero_since is None:
                        stable_zero_since = now
                    elif now - stable_zero_since >= grace_seconds:
                        os._exit(0)
                else:
                    stable_zero_since = None
            except Exception:
                stable_zero_since = None
            time.sleep(poll_interval)

    threading.Thread(target=_watcher, daemon=True).start()


def _hash_uploaded_file(file):
    """Return a short hex hash for the uploaded file bytes."""
    if file is None:
        return None
    try:
        raw = file.getvalue()
    except Exception:
        raw = file.read()
        try:
            file.seek(0)
        except Exception:
            pass
    return hashlib.md5(raw).hexdigest()


def main():
    st.set_page_config(page_title="NBA Rotation Tool", layout="wide")
    _auto_exit_when_no_sessions(grace_seconds=5)

    # Compact CSS
    st.markdown(
        """
        <style>
        :root{ --toolbar-top-margin:28px; --page-top-padding:1.2rem; }
        .block-container { padding-top: var(--page-top-padding); padding-bottom: .5rem; }
        div[data-testid="stVerticalBlock"] > div:has(> div[data-testid="column"]) { margin-bottom: .18rem; }
        div[data-baseweb="select"] > div { min-height: 30px; }
        input[type="number"], input[type="text"] { height: 30px; padding-top: 2px; padding-bottom: 2px; }
        .toolbar-spacer { height: var(--toolbar-top-margin); }
        hr { margin:4px 0; border:0; height:1px; background:#eee; }
        </style>
        """,
        unsafe_allow_html=True,
    )

    # ---- Session state init ----
    if "game" not in st.session_state:
        st.session_state.game = GameData()
    if "uploaded_hash" not in st.session_state:
        st.session_state.uploaded_hash = None
    if "render_nonce" not in st.session_state:
        st.session_state.render_nonce = 0
    if "export_filename" not in st.session_state:
        st.session_state.export_filename = "PlayerOverrides.csv"

    # Toolbar spacer
    st.markdown('<div class="toolbar-spacer"></div>', unsafe_allow_html=True)

    # --------------------------
    # Row 1: IMPORT / REFRESH / EXPORT
    # --------------------------
    col_upload, col_refresh, col_export = st.columns([5, 2, 3])

    with col_upload:
        uploaded = st.file_uploader(
            "Upload rotation CSV", type=["csv"], label_visibility="visible"
        )
        if uploaded is not None:
            try:
                name = uploaded.name
                base = name.rsplit(".", 1)[0] if "." in name else name
                st.session_state.export_filename = f"{base}.csv"

                new_hash = _hash_uploaded_file(uploaded)
                if new_hash and new_hash != st.session_state.get("uploaded_hash"):
                    try:
                        uploaded.seek(0)
                    except Exception:
                        pass
                    st.session_state.game = load_csv(uploaded)
                    st.session_state.uploaded_hash = new_hash
                    st.session_state.render_nonce = (
                        st.session_state.get("render_nonce", 0) + 1
                    )
            except Exception as ex:
                st.error("Failed to load CSV.")
                st.exception(ex)

    with col_refresh:
        st.markdown("<div style='height:30px'></div>", unsafe_allow_html=True)
        if st.button("🔄 Refresh view", width="stretch"):
            st.session_state.render_nonce += 1

    with col_export:
        st.markdown("<div style='height:30px'></div>", unsafe_allow_html=True)
        df_for_download = export_csv(st.session_state.game)
        st.download_button(
            "⬇️ Download CSV",
            data=df_for_download.to_csv(index=False).encode("utf-8"),
            file_name=st.session_state.get("export_filename", "PlayerOverrides.csv"),
            mime="text/csv",
            width="stretch",
        )

    # --------------------------
    # Row 2: TEAM SWITCH
    # --------------------------
    team_choice = st.radio("Team", ["HomeTeam", "AwayTeam"], horizontal=True)

    # --------------------------
    # Body: Selected team
    # --------------------------
    if team_choice == "HomeTeam":
        render_team_panel(st.session_state.game.home_team)
    else:
        render_team_panel(st.session_state.game.away_team)

    st.subheader("On-Court Players Over Time")
    if team_choice == "HomeTeam":
        render_oncourt_chart(st.session_state.game.home_team)
    else:
        render_oncourt_chart(st.session_state.game.away_team)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        st.error("An unexpected error occurred.")
        st.exception(e)
        print("\n--- Unhandled exception in Streamlit app ---")
        print("".join(traceback.format_exception(type(e), e, e.__traceback__)))
