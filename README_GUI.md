# extract-xiso GUI

A gorgeous Xbox-themed web UI for [extract-xiso](https://github.com/XboxDev/extract-xiso) — the Xbox ISO creation and extraction utility.

## One-line install

```bash
git clone https://github.com/MrsHorrid/extract-xiso && cd extract-xiso && ./install.sh
```

Or via curl:
```bash
curl -sSL https://raw.githubusercontent.com/MrsHorrid/extract-xiso/master/install.sh | bash
```

Then launch:
```bash
python3 gui/app.py
```
Browser opens automatically at **http://localhost:7860**

---

## Features

- 🗂 **Extract** — Unpack Xbox ISOs with drag & drop
- 📁 **Create** — Build ISOs from zipped game folders  
- 📋 **List** — Inspect ISO contents with a file tree
- 🔄 **Rewrite** — Optimize ISO filesystem structure
- 🎮 **Xbox-themed dark UI** — Looks like the Xbox dashboard
- ⚡ **Auto-install** — `./install.sh` builds everything from source
- 📊 **Real-time progress** — Live log output, animated bars
- 🌙 **Dark/light mode** — Toggle in top right
- ⌨️ **Keyboard shortcuts** — `E` Extract, `C` Create, `L` List, `R` Rewrite
- 📱 **Mobile responsive**
- 🔒 **Local only** — runs on your machine, no data sent anywhere

---

## Manual setup

**Requirements:** Python 3.8+, cmake, gcc/clang

```bash
# 1. Build the C binary
mkdir build && cd build && cmake .. && make && cd ..

# 2. Install Python deps  
pip install flask flask-cors

# 3. Run
python3 gui/app.py
```

---

## Screenshots

> *Coming soon*

---

## Credits

- Original tool: [XboxDev/extract-xiso](https://github.com/XboxDev/extract-xiso) by in@fishtank.com
- GUI wrapper: [MrsHorrid/extract-xiso](https://github.com/MrsHorrid/extract-xiso)
