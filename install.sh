#!/usr/bin/env bash
set -e

# ─────────────────────────────────────────────────────────────────────────────
#  extract-xiso WebUI — One-command installer
#  Usage: ./install.sh
# ─────────────────────────────────────────────────────────────────────────────

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

banner() {
    echo ""
    echo -e "${CYAN}${BOLD}"
    echo "  ╔═══════════════════════════════════════════╗"
    echo "  ║        extract-xiso WebUI Installer       ║"
    echo "  ║          Xbox ISO utility + gorgeous UI   ║"
    echo "  ╚═══════════════════════════════════════════╝"
    echo -e "${NC}"
}

info()    { echo -e "${CYAN}[INFO]${NC}  $1"; }
success() { echo -e "${GREEN}[OK]${NC}    $1"; }
warn()    { echo -e "${YELLOW}[WARN]${NC}  $1"; }
error()   { echo -e "${RED}[ERROR]${NC} $1"; exit 1; }
step()    { echo -e "\n${BOLD}${CYAN}▶ $1${NC}"; }

# ─── Detect OS ────────────────────────────────────────────────────────────────
detect_os() {
    case "$(uname -s)" in
        Linux*)
            if grep -qi microsoft /proc/version 2>/dev/null; then
                OS="wsl"
            else
                OS="linux"
            fi
            ;;
        Darwin*) OS="macos" ;;
        CYGWIN*|MINGW*|MSYS*) OS="windows" ;;
        *) OS="unknown" ;;
    esac
    info "Detected OS: ${OS}"
}

# ─── Install system deps ───────────────────────────────────────────────────────
install_build_deps() {
    step "Checking build dependencies (cmake, gcc, make)"

    if command -v cmake &>/dev/null && command -v gcc &>/dev/null && command -v make &>/dev/null; then
        success "cmake, gcc, make already installed"
        return
    fi

    case "$OS" in
        linux|wsl)
            info "Installing via apt..."
            sudo apt-get update -qq
            sudo apt-get install -y cmake gcc make
            ;;
        macos)
            if ! command -v brew &>/dev/null; then
                error "Homebrew not found. Install it from https://brew.sh then re-run this script."
            fi
            info "Installing via brew..."
            brew install cmake gcc make 2>/dev/null || true
            ;;
        windows)
            if command -v choco &>/dev/null; then
                info "Installing via chocolatey..."
                choco install cmake mingw make -y
            else
                warn "Chocolatey not found. Please install cmake, gcc, and make manually."
                warn "See: https://cmake.org/download/ and https://www.mingw-w64.org/"
            fi
            ;;
        *)
            warn "Unknown OS. Please install cmake, gcc, and make manually."
            ;;
    esac

    success "Build dependencies installed"
}

# ─── Build extract-xiso binary ────────────────────────────────────────────────
build_binary() {
    step "Building extract-xiso binary"

    cd "$REPO_ROOT"

    if [ -f "build/extract-xiso" ] || [ -f "build/extract-xiso.exe" ]; then
        success "Binary already built (delete build/ to rebuild)"
        return
    fi

    mkdir -p build
    cd build

    cmake .. -DCMAKE_BUILD_TYPE=Release
    make -j"$(nproc 2>/dev/null || sysctl -n hw.ncpu 2>/dev/null || echo 4)"

    cd "$REPO_ROOT"

    if [ -f "build/extract-xiso" ] || [ -f "build/extract-xiso.exe" ]; then
        success "Binary built: $(ls build/extract-xiso* 2>/dev/null)"
    else
        error "Build failed — no binary found in build/"
    fi
}

# ─── Check Python ─────────────────────────────────────────────────────────────
check_python() {
    step "Checking Python 3.8+"

    PYTHON=""
    for cmd in python3 python; do
        if command -v "$cmd" &>/dev/null; then
            VER=$("$cmd" -c "import sys; print('%d.%d' % sys.version_info[:2])" 2>/dev/null)
            MAJOR=$(echo "$VER" | cut -d. -f1)
            MINOR=$(echo "$VER" | cut -d. -f2)
            if [ "$MAJOR" -ge 3 ] && [ "$MINOR" -ge 8 ]; then
                PYTHON="$cmd"
                success "Found Python $VER ($cmd)"
                break
            fi
        fi
    done

    if [ -z "$PYTHON" ]; then
        case "$OS" in
            linux|wsl)
                info "Installing Python 3 via apt..."
                sudo apt-get install -y python3 python3-pip
                PYTHON="python3"
                ;;
            macos)
                info "Installing Python 3 via brew..."
                brew install python3
                PYTHON="python3"
                ;;
            *)
                error "Python 3.8+ not found. Install from https://python.org"
                ;;
        esac
        success "Python installed"
    fi
}

# ─── Install Python deps ───────────────────────────────────────────────────────
install_python_deps() {
    step "Installing Python dependencies"

    cd "$REPO_ROOT"

    if ! command -v pip3 &>/dev/null && ! "$PYTHON" -m pip --version &>/dev/null 2>&1; then
        case "$OS" in
            linux|wsl) sudo apt-get install -y python3-pip ;;
            macos)     curl https://bootstrap.pypa.io/get-pip.py | "$PYTHON" ;;
        esac
    fi

    "$PYTHON" -m pip install --upgrade pip -q
    "$PYTHON" -m pip install -r gui/requirements.txt -q

    success "Python dependencies installed"
}

# ─── Create bin directory ─────────────────────────────────────────────────────
create_bin_dir() {
    step "Creating ./bin/ directory for tool binaries"
    mkdir -p "$REPO_ROOT/bin"
    success "bin/ directory ready"
}

# ─── Install xdvdfs ───────────────────────────────────────────────────────────
install_xdvdfs() {
    step "Installing xdvdfs (Xbox DVD filesystem tool)"

    if [ -f "$REPO_ROOT/bin/xdvdfs" ] || [ -f "$REPO_ROOT/bin/xdvdfs.exe" ]; then
        success "xdvdfs already in bin/"
        return
    fi

    if command -v xdvdfs &>/dev/null; then
        success "xdvdfs already installed: $(xdvdfs --version 2>/dev/null || echo 'found')"
        return
    fi

    # Try via cargo
    CARGO_INSTALLED=false
    if command -v cargo &>/dev/null; then
        CARGO_INSTALLED=true
    else
        info "Rust/cargo not found. Installing via rustup..."
        curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
        # shellcheck disable=SC1090
        source "$HOME/.cargo/env" 2>/dev/null || export PATH="$HOME/.cargo/bin:$PATH"
        if command -v cargo &>/dev/null; then
            CARGO_INSTALLED=true
        fi
    fi

    if [ "$CARGO_INSTALLED" = true ]; then
        info "Installing xdvdfs via cargo..."
        if cargo install xdvdfs-cli; then
            success "xdvdfs installed via cargo"
            return
        else
            warn "cargo install failed, trying prebuilt binary..."
        fi
    fi

    # Fallback: download prebuilt binary from GitHub releases
    info "Downloading xdvdfs prebuilt binary from GitHub..."
    local bin_name="xdvdfs"
    local asset_pattern=""
    case "$OS" in
        linux|wsl) asset_pattern="x86_64-unknown-linux" ;;
        macos)     asset_pattern="x86_64-apple-darwin" ;;
        windows)   bin_name="xdvdfs.exe"; asset_pattern="x86_64-pc-windows" ;;
        *)         warn "Unknown OS — skipping xdvdfs binary download"; return ;;
    esac

    local download_url
    download_url=$(curl -s https://api.github.com/repos/antangelo/xdvdfs/releases/latest \
        | grep "browser_download_url" | grep "$asset_pattern" | head -1 | cut -d'"' -f4)

    if [ -n "$download_url" ]; then
        info "Downloading: $download_url"
        curl -L -o "$REPO_ROOT/bin/$bin_name" "$download_url"
        chmod +x "$REPO_ROOT/bin/$bin_name"
        success "xdvdfs downloaded to bin/$bin_name"
    else
        warn "Could not find xdvdfs release for your OS."
        warn "Install manually from: https://github.com/antangelo/xdvdfs/releases"
    fi
}

# ─── Install XGDTool ──────────────────────────────────────────────────────────
install_xgdtool() {
    step "Installing XGDTool (Xbox game disc converter)"

    local bin_name="XGDTool"
    [ "$OS" = "windows" ] && bin_name="XGDTool.exe"

    if [ -f "$REPO_ROOT/bin/$bin_name" ]; then
        success "XGDTool already in bin/"
        return
    fi

    if command -v XGDTool &>/dev/null; then
        success "XGDTool already installed"
        return
    fi

    info "Downloading XGDTool binary from GitHub..."
    local asset_pattern=""
    case "$OS" in
        linux|wsl) asset_pattern="linux" ;;
        macos)     asset_pattern="macos" ;;
        windows)   asset_pattern="windows" ;;
        *)         warn "Unknown OS — skipping XGDTool download"; return ;;
    esac

    local download_url
    download_url=$(curl -s https://api.github.com/repos/wiredopposite/XGDTool/releases/latest \
        | grep "browser_download_url" | grep -i "$asset_pattern" | head -1 | cut -d'"' -f4)

    if [ -n "$download_url" ]; then
        info "Downloading: $download_url"
        curl -L -o "$REPO_ROOT/bin/$bin_name" "$download_url"
        chmod +x "$REPO_ROOT/bin/$bin_name"
        success "XGDTool downloaded to bin/$bin_name"
    else
        warn "Could not find XGDTool release for your OS."
        warn "Install manually from: https://github.com/wiredopposite/XGDTool/releases"
    fi
}

# ─── Done ─────────────────────────────────────────────────────────────────────
print_success() {
    echo ""
    echo -e "${GREEN}${BOLD}"
    echo "  ╔══════════════════════════════════════════════════════════╗"
    echo "  ║                  ✓ Installation complete!                ║"
    echo "  ╠══════════════════════════════════════════════════════════╣"
    echo "  ║                                                          ║"
    echo "  ║   Start the WebUI:                                       ║"
    echo "  ║     python3 gui/app.py                                   ║"
    echo "  ║                                                          ║"
    echo "  ║   Then open:  http://localhost:7860                      ║"
    echo "  ║   (browser opens automatically)                          ║"
    echo "  ║                                                          ║"
    echo "  ╚══════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
}

# ─── Main ─────────────────────────────────────────────────────────────────────
main() {
    banner
    detect_os
    create_bin_dir
    install_build_deps
    build_binary
    check_python
    install_python_deps
    install_xdvdfs
    install_xgdtool
    print_success
}

main "$@"
