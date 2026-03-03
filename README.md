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

**On Windows**, use [WSL](https://docs.microsoft.com/en-us/windows/wsl/install) (Windows Subsystem for Linux), then run:
```
./install.sh
```

> ☕ This takes 1-2 minutes. It automatically installs everything needed and builds the tool.

### Step 3 — Open the app

```
python3 gui/app.py
```

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

- **Python 3.8 or newer** — [Download here](https://www.python.org/downloads/)
- **A terminal** — Terminal on Mac/Linux, or WSL on Windows
- **cmake + gcc** — The installer handles this automatically

---

## 🐛 Something not working?

**"install.sh: permission denied"**
```
chmod +x install.sh && ./install.sh
```

**"python3: command not found"**
→ [Download Python](https://www.python.org/downloads/) and install it first.

**"Binary not found" warning in the app**
→ The installer didn't finish building. Run `./install.sh` again.

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
