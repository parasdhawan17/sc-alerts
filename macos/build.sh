#!/bin/bash
set -euo pipefail
PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_DIR"
export PYINSTALLER_CONFIG_DIR="${PYINSTALLER_CONFIG_DIR:-$PROJECT_DIR/build/pyinstaller-cache}"
BUILD_PYTHON="${SC_ALERTS_BUILD_PYTHON:-$PROJECT_DIR/.venv/bin/python}"
if [[ ! -x "$BUILD_PYTHON" ]]; then
  echo 'Create a build environment and install macos/requirements-build.txt first.' >&2
  exit 1
fi
"$BUILD_PYTHON" -m PyInstaller --noconfirm --clean --onedir --name sc-alerts-worker \
  --paths "$PROJECT_DIR" --paths "$PROJECT_DIR/scripts" \
  --collect-data googleapiclient --distpath build/backend-dist --workpath build/pyinstaller \
  --specpath build scripts/app_backend.py
APP_DIR="$PROJECT_DIR/dist/SC Alerts.app"
mkdir -p "$APP_DIR/Contents/MacOS" "$APP_DIR/Contents/Resources"
rm -rf "$APP_DIR/Contents/Resources/backend"
cp -R build/backend-dist/sc-alerts-worker "$APP_DIR/Contents/Resources/backend"
swiftc -swift-version 5 -parse-as-library -O -target "$(uname -m)-apple-macosx13.0" \
  -module-cache-path "$PROJECT_DIR/build/swift-module-cache" \
  macos/SCAlerts.swift -o "$APP_DIR/Contents/MacOS/SCAlerts" \
  -framework SwiftUI -framework AppKit
swiftc -swift-version 5 -module-cache-path "$PROJECT_DIR/build/swift-module-cache" \
  macos/MakeIcon.swift -o "$PROJECT_DIR/build/make-icon" -framework AppKit
"$PROJECT_DIR/build/make-icon" "$APP_DIR/Contents/Resources/SCAlerts.icns"
cp macos/Info.plist "$APP_DIR/Contents/Info.plist"
codesign --force --deep --sign - "$APP_DIR"
codesign --verify --deep --strict "$APP_DIR"
echo "Built $APP_DIR"
