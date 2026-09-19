#!/usr/bin/env bash
# Builds the BT Keyboard appliance OS image using Buildroot.
#
# Usage:
#   ./build.sh [x86_64|raspberrypi4]
#
# First run downloads Buildroot (~20 MB tarball, extracts to a full
# source tree) into ./build/, then compiles a full cross toolchain,
# kernel, and root filesystem from scratch. Expect this to take
# 30-90+ minutes and a few GB of free disk on first run; re-runs are
# incremental. Needs internet access and the usual Buildroot host
# dependencies (see https://buildroot.org/downloads/manual/manual.html#requirement).
set -euo pipefail

TARGET="${1:-x86_64}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BUILDROOT_VERSION="2024.02"
BUILD_DIR="$SCRIPT_DIR/build"
BUILDROOT_SRC="$BUILD_DIR/buildroot-$BUILDROOT_VERSION"
OUTPUT_DIR="$BUILD_DIR/output-$TARGET"

case "$TARGET" in
    x86_64)       BASE_DEFCONFIG=qemu_x86_64_defconfig ;;
    raspberrypi4) BASE_DEFCONFIG=raspberrypi4_64_defconfig ;;
    *)
        echo "Unknown target '$TARGET'. Use 'x86_64' or 'raspberrypi4'." >&2
        exit 1
        ;;
esac

mkdir -p "$BUILD_DIR"

if [ ! -d "$BUILDROOT_SRC" ]; then
    echo "==> Fetching Buildroot $BUILDROOT_VERSION"
    curl -fL "https://buildroot.org/downloads/buildroot-$BUILDROOT_VERSION.tar.gz" \
        | tar -xz -C "$BUILD_DIR"
fi

cd "$BUILDROOT_SRC"

echo "==> Configuring ($BASE_DEFCONFIG + btkeyboard fragment)"
make O="$OUTPUT_DIR" BR2_EXTERNAL="$SCRIPT_DIR/buildroot" "$BASE_DEFCONFIG"
support/kconfig/merge_config.sh -O "$OUTPUT_DIR" "$OUTPUT_DIR/.config" \
    "$SCRIPT_DIR/buildroot/configs/btkeyboard.fragment"
make O="$OUTPUT_DIR" olddefconfig

echo "==> Building (this takes a while the first time)"
make O="$OUTPUT_DIR"

echo "==> Done. Image(s) in $OUTPUT_DIR/images/"
