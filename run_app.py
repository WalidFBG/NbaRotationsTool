# run_app.py
import os
import sys
import threading
import time
import urllib.request
import webbrowser
from pathlib import Path


def resource_path(*parts):
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    return str(base.joinpath(*parts))


def open_when_ready(url, timeout=10):
    def worker():
        start = time.time()
        health = url.rstrip("/") + "/_stcore/health"
        while time.time() - start < timeout:
            try:
                with urllib.request.urlopen(health, timeout=1) as r:
                    if r.status == 200:
                        webbrowser.open(url, new=1, autoraise=True)
                        return
            except Exception:
                time.sleep(0.25)

    threading.Thread(target=worker, daemon=True).start()


def main():
    # --- IMPORTANT: set env BEFORE importing Streamlit ---
    os.environ["STREAMLIT_GLOBAL_DEVELOPMENTMODE"] = "false"  # force prod mode
    os.environ["STREAMLIT_SERVER_HEADLESS"] = "true"
    os.environ["STREAMLIT_SERVER_FILEWATCHERTYPE"] = "none"
    os.environ["STREAMLIT_BROWSER_GATHER_USAGE_STATS"] = "false"
    # If you previously tweaked CORS/XSRF in config, clear them to defaults:
    os.environ.pop("STREAMLIT_SERVER_ENABLECORS", None)
    os.environ.pop("STREAMLIT_SERVER_ENABLEXSRFPROTECTION", None)

    app_path = resource_path("rotation_tool", "app.py")
    url = "http://127.0.0.1:8501"
    open_when_ready(url)

    # Import CLI only after env is set
    from streamlit.web.cli import main as stcli

    sys.argv = [
        "streamlit",
        "run",
        app_path,
        "--global.developmentMode=false",  # belt & braces
        "--server.headless",
        "true",
        "--server.fileWatcherType",
        "none",
        "--server.port",
        "8501",
    ]
    stcli()


if __name__ == "__main__":
    main()
