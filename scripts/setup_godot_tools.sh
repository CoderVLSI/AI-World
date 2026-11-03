#!/usr/bin/env bash
# Installs Godot (checksum-verified) and the Godot MCP server into ./tools (git-ignored).
# Usage: scripts/setup_godot_tools.sh [godot-version]   (Linux x86_64; on other systems download Godot manually)
set -euo pipefail
VERSION="${1:-4.4.1-stable}"
DEST="$(cd "$(dirname "$0")/.." && pwd)/tools"
mkdir -p "$DEST/godot_dl" "$DEST/godot" "$DEST/mcp"
cd "$DEST/godot_dl"
BASE="https://github.com/godotengine/godot/releases/download/$VERSION"
ZIP="Godot_v${VERSION}_linux.x86_64.zip"
curl -fsSL -o "$ZIP" "$BASE/$ZIP"
curl -fsSL -o SHA512-SUMS.txt "$BASE/SHA512-SUMS.txt"
expected="$(grep " $ZIP\$" SHA512-SUMS.txt | awk '{print $1}')"
actual="$(sha512sum "$ZIP" | awk '{print $1}')"
[ -n "$expected" ] && [ "$expected" = "$actual" ] || { echo "CHECKSUM MISMATCH - refusing to install" >&2; exit 1; }
unzip -oq "$ZIP" -d "$DEST/godot"
chmod +x "$DEST/godot/Godot_v${VERSION}_linux.x86_64"
echo "Godot installed and verified: $DEST/godot/Godot_v${VERSION}_linux.x86_64"
# MCP server: install without running package scripts, then print how to register it.
cd "$DEST/mcp"
[ -f package.json ] || npm init -y >/dev/null 2>&1
npm install --ignore-scripts --no-audit --no-fund @coding-solo/godot-mcp >/dev/null
echo "Godot MCP server installed: $DEST/mcp/node_modules/@coding-solo/godot-mcp/build/index.js"
echo 'Register it in an MCP client with: command "node", args ["<that path>"], env {"GODOT_PATH": "<godot path>"}'
