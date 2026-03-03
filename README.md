# extract-xiso GUI 🎮

> **The easiest way to work with Xbox ISO files — no command line needed!**

This tool lets you **extract**, **create**, **list**, and **optimize** Xbox ISO files using a beautiful drag & drop web interface that runs on your computer.

---

## 🚀 Quick Start (The Easy Way)

### Step 1 — Download the project

Click the green **Code** button at the top of this page → **Download ZIP** → unzip it somewhere on your computer.

Or if you have Git:
```
git clone https://github.com/MrsHorrid/extract-xiso
cd extract-xiso
```

### Step 2 — Run the installer

**On Mac or Linux**, open Terminal, go to the folder, and run:
```
./install.sh
```

**On Windows (native)**, double‑click **install.bat** or run it from Command Prompt in the project folder. It creates a virtual environment (`.venv`) and installs dependencies. No admin rights needed.

**On Windows (WSL)**, you can instead use Linux: run `./install.sh` inside WSL.

> ☕ This takes 1–2 minutes. It installs everything needed and optionally builds the C tool if CMake is available.

### Step 3 — Open the app

**Mac / Linux / WSL:**
```
python3 gui/app.py
```

**Windows (after install.bat):**
```
run.bat
```
Or: `.venv\Scripts\python.exe gui\app.py`

Your browser will open automatically at **http://localhost:7860** 🎉

---

## 🖥️ What does it look like?

A dark Xbox-themed dashboard with 4 big buttons:

| Button | What it does |
|--------|-------------|
| 🗂 **Extract** | Unpack an Xbox ISO — drag your `.iso` file in, get a folder of files out |
| 📁 **Create** | Make an Xbox ISO from a folder — zip your game files, drag them in |
| 📋 **List** | See what's inside an ISO without extracting anything |
| 🔄 **Rewrite** | Fix/optimize an ISO's internal structure |

Just drag & drop your file onto the right card and hit the green button. That's it!

---

## ❓ What is an Xbox ISO?

An Xbox ISO (`.iso` file) is a copy of an original Xbox game disc. This tool helps you:
- **Back up** your original Xbox games to your computer
- **Prepare** ISOs for use with original Xbox emulators or modded consoles
- **Fix** ISOs that have compatibility issues

---

## 🛠️ Requirements

- **Python 3.8 or newer** — [Download here](https://www.python.org/downloads/) (on Windows, tick “Add Python to PATH”)
- **pip** — Provided by the installers (`install.sh` / `install.bat`) or your OS package manager
- **Windows:** `install.bat` creates a `.venv` in the project and does not require admin. Optional: **CMake** + **Visual Studio Build Tools** to build `extract-xiso.exe`; otherwise the GUI still runs and you can use a pre-built binary.
- **Mac/Linux:** `install.sh` uses system Python; **cmake** + **gcc**/Clang for building the C binary

---

## 🐛 Something not working?

**"Missing Python dependencies" / "No module named pip"**
→ Your Python has no pip or the GUI deps aren’t installed. Install them:

On **Ubuntu/Debian/WSL**:
```bash
sudo apt-get update && sudo apt-get install -y python3-pip
pip install -r gui/requirements.txt
# or from repo root:
pip install -r gui/requirements.txt
```
Then run `python3 gui/app.py` again.

**"install.sh: permission denied"**
```
chmod +x install.sh && ./install.sh
```

**"python3: command not found"**
→ [Download Python](https://www.python.org/downloads/) and install it first.

**"Binary not found" warning in the app**
→ The C binary wasn’t built. Run `./install.sh` again (Mac/Linux/WSL), or on Windows run `install.bat` with CMake and Visual Studio Build Tools installed, or download a release that includes `extract-xiso.exe`.

**Windows: "Python not found" when running install.bat**
→ Install Python from [python.org](https://www.python.org/downloads/) and check **“Add Python to PATH”**. Then run `install.bat` again.

**Windows: "Run install.bat first" when running run.bat**
→ Double‑click `install.bat` once to create the `.venv` and install dependencies; then use `run.bat` to start the app.

**Port 7860 already in use**
```
python3 gui/app.py --port 7861
```

---

## 💡 Tips

- Works with files up to **8GB** (big ISOs are fine!)
- Your files stay **100% local** — nothing is uploaded anywhere
- Press **E**, **C**, **L**, or **R** on your keyboard to quickly jump to each section
- Toggle **dark/light mode** with the moon button in the top right

---

## 📖 For advanced users (command line)

If you prefer the original CLI:
```bash
# Extract an ISO
./extract-xiso halo-2.iso

# Extract to specific folder
./extract-xiso halo-2.iso -d /path/to/output/

# Create an ISO from a folder
./extract-xiso -c ./halo-2

# List contents of an ISO
./extract-xiso -l halo-2.iso

# Rewrite/optimize an ISO
./extract-xiso -r halo-2.iso
```

---

## 🙏 Credits

- Original extract-xiso tool by [XboxDev](https://github.com/XboxDev/extract-xiso)
- Web GUI by [MrsHorrid](https://github.com/MrsHorrid)

---

*Found a bug or have a suggestion? [Open an issue](https://github.com/MrsHorrid/extract-xiso/issues) — we'd love to hear from you!*
