# NBA Rotations Tool

A Streamlit-based tool for visualizing and editing NBA rotation data.

# Run locally:

1. Create and activate a virtual environment  
   python -m venv .venv
   .venv\Scripts\activate

2. Install dependencies
    pip install -r requirements.txt

3. Start the app
    streamlit run rotation_tool/app.py

4. Build an executable
    pyinstaller --clean --noconfirm --onefile --windowed --name "NBA Rotations Tool" --icon ".\assets\basketball.ico" --copy-metadata streamlit --collect-all streamlit --copy-metadata pandas --collect-all pandas --copy-metadata numpy --collect-all numpy --copy-metadata plotly --collect-all plotly --add-data "rotation_tool:rotation_tool" run_app.py