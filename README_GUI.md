# extract-xiso GUI

A gorgeous Xbox-themed web UI for [extract-xiso](https://github.com/XboxDev/extract-xiso) — the Xbox ISO creation and extraction utility — now with advanced format conversion, file injection, custom ISO building, and XBE patching.

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

### Core Tools (extract-xiso)
- 🗂 **Extract** — Unpack Xbox ISOs with drag & drop
- 📁 **Create** — Build ISOs from zipped game folders
- 📋 **List** — Inspect ISO contents with a file tree
- 🔄 **Rewrite** — Optimize ISO filesystem structure

### Advanced Tools
- 🔄 **Format Converter** — Convert between XISO, CCI, CSO, GoD, ZAR (via XGDTool)
- 💉 **File Injector** — Inject/replace files inside an ISO without full repack
- 🔨 **Build Custom ISO** — Create Xbox ISOs from scratch (via xdvdfs)
- 🩹 **XBE Media Patcher** — Patch .xbe executables to run from backup/HDD

### UI & UX
- 🎮 **Xbox-themed dark UI** — Looks like the Xbox dashboard
- 🔧 **Tool status bar** — Live indicator of which tools are installed
- ⚡ **Auto-install** — `./install.sh` builds and downloads everything
- 📊 **Real-time progress** — Live SSE log streaming, animated bars
- 🌙 **Dark/light mode** — Toggle in top right
- ⌨️ **Keyboard shortcuts** — `E` Extract, `C` Create, `L` List, `R` Rewrite, `F` Format, `I` Inject, `B` Build, `P` Patch XBE
- 📱 **Mobile responsive**
- 🔒 **Local only** — runs on your machine, no data sent anywhere

---

## Tools

| Tool | Purpose | Installed by |
|------|---------|-------------|
| **extract-xiso** | Extract, create, list, rewrite Xbox ISOs | Built from source via `cmake` |
| **xdvdfs** | Pack/unpack Xbox DVD filesystem, build custom ISOs | `cargo install xdvdfs-cli` or prebuilt binary |
| **XGDTool** | Convert between XISO, CCI, CSO, GoD, ZAR formats | Prebuilt binary from GitHub releases |

---

## Format Converter

Convert Xbox disc images between formats using XGDTool.

**Supported formats:**

| Format | Description | Best for |
|--------|-------------|---------|
| XISO | Standard Xbox ISO | Universal compatibility |
| CCI | Compressed ISO | OG Xbox with XBMC, smallest compatible |
| CSO | Compressed ISO (CSO) | Project Stellar, smallest size |
| GoD | Games on Demand | Xbox 360 HDD installs |
| ZAR | Archive format | Archival/backup |
| Extract | Raw files | Modding, inspection |

**Options:**
- Target machine: OG Xbox, xemu, Xenia, Xbox 360
- Scrub: No scrub / Partial (remove padding) / Full reauthor (smallest possible)

---

## File Injector

Replace or add files inside an existing Xbox ISO without fully repacking it.

**Use cases:**
- Swap `default.xbe` with a patched version
- Replace game assets (textures, audio, scripts)
- Add save files or config files to a disc image

**How it works:**
1. Extracts the ISO to a temp directory
2. Replaces the target file with your replacement
3. Repacks everything back into a new ISO
4. Returns the modified ISO for download

---

## Build Custom ISO

Create an Xbox ISO entirely from scratch using xdvdfs.

**Use cases:**
- Homebrew game packaging
- Custom compilations
- Testing disc layouts

**How it works:**
1. Upload multiple files via drag & drop
2. Set the path for each file inside the ISO
3. Optionally apply XBE media patch to all `.xbe` files
4. xdvdfs packs everything into a proper Xbox XDVDFS image

---

## XBE Media Patcher

Patch a `.xbe` executable so your modded Xbox will load it from any media type (HDD, backup disc, USB, etc.).

**What it does:**

The XBE file format stores a "media type flags" field at offset `0x118` in the certificate block. The patch sets bit 3 (`0x08`) of this field, which enables "any media" mode:

```
Before: media_flags = 0x00000004  (DVD only)
After:  media_flags = 0x0000000C  (DVD + any media)
```

**When you need it:**
- Your game doesn't load from a backup disc
- Your BIOS doesn't auto-patch XBE media flags
- You're running a homebrew on a stock(ish) BIOS

---

## Manual setup

**Requirements:** Python 3.8+, cmake, gcc/clang, curl

```bash
# 1. Build the C binary
mkdir build && cd build && cmake .. && make && cd ..

# 2. Install Python deps
pip install flask flask-cors

# 3. (Optional) Install xdvdfs
cargo install xdvdfs-cli

# 4. (Optional) Install XGDTool
# Download from https://github.com/wiredopposite/XGDTool/releases
# Place binary in ./bin/XGDTool

# 5. Run
python3 gui/app.py
```

---

## Screenshots

> *Coming soon*

---

## Credits

- Original tool: [XboxDev/extract-xiso](https://github.com/XboxDev/extract-xiso) by in@fishtank.com
- GUI wrapper: [MrsHorrid/extract-xiso](https://github.com/MrsHorrid/extract-xiso)
- Format conversion: [XGDTool](https://github.com/wiredopposite/XGDTool) by wiredopposite
- Xbox DVD filesystem: [xdvdfs](https://github.com/antangelo/xdvdfs) by antangelo
