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
    install_build_deps
    build_binary
    check_python
    install_python_deps
    print_success
}

main "$@"
