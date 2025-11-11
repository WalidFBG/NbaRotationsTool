# NBA Rotations Tool

A **Streamlit-based desktop app** for editing and visualizing NBA rotation data.

---

## 🚀 Run Locally

1. **Create and activate a virtual environment**

```
   python -m venv .venv  
   .venv\Scripts\activate
```

2. **Install dependencies**

```
   pip install -r requirements.txt
```

3. **Start the app**

```
   $env:PYTHONPATH = "$PWD"; python -m streamlit run rotation_tool/app.py
```

---

## 🧰 Build a Standalone EXE (Windows)

To build a distributable `.exe`:

```
   pyinstaller --clean --noconfirm --onefile --windowed --name "NBA Rotations Tool" --icon ".\assets\basketball.ico" --copy-metadata streamlit --collect-all streamlit --copy-metadata pandas --collect-all pandas --copy-metadata numpy --collect-all numpy --copy-metadata plotly --collect-all plotly --add-data "rotation_tool:rotation_tool" run_app.py
```

This produces:

```
   dist/NBA Rotations Tool.exe
```

---

## ⚙️ Notes

- Closing all browser tabs automatically stops the app (EXE exits after ~5 seconds).  
- To debug locally, run with a console by adding `--console` in your PyInstaller command.  
- Tested on Windows with Python 3.11+.

---

**Author:** Walid Mustafa  
**Company:** Fanatics Enterprise  
**License:** Internal Use Only