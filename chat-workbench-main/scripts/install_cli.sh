#!/bin/bash

# Copyright © Amazon.com and Affiliates: This deliverable is considered Developed Content as defined in the AWS Service
# Terms and the SOW between the parties dated 2025.

# ========================================================================
# Chat Workbench CLI Installation Script
# ========================================================================
#
# DESCRIPTION:
#   Builds the Rust-based CWB (Chat Workbench) CLI and installs it on the
#   local system for the current user.
#
# USAGE:
#   ./scripts/install_cli.sh
#
# BEHAVIOR:
#   The script first attempts to install the CLI using `cargo install`.
#   If cargo is available, this is the preferred method. If cargo is not
#   found, it falls back to copying the compiled binary to /usr/local/bin,
#   which may require sudo privileges.
#
# PREREQUISITES:
#   - Rust and Cargo must be installed for the primary installation method.
#     Installation instructions: https://www.rust-lang.org/tools/install
#
# ========================================================================

set -e

echo "🔧 Installing CWB (Chat Workbench CLI)..."

# Check if Rust is installed
if ! command -v cargo &> /dev/null; then
    echo "❌ Rust/Cargo not found. Please install Rust first:"
    echo "   curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh"
    exit 1
fi

# Navigate to CLI directory
if [ ! -d "cli" ]; then
    echo "❌ CLI directory not found. Make sure you're in the project root."
    exit 1
fi

cd cli

echo "🏗️  Building CWB CLI (this may take a few minutes)..."
cargo build --release

# Check if build was successful
if [ ! -f "target/release/cwb" ]; then
    echo "❌ Build failed. Please check the output above."
    exit 1
fi

# Determine installation method
if command -v cargo &> /dev/null; then
    echo "📦 Installing via cargo..."
    cargo install --path . --force

    # Check if cargo bin is in PATH
    if [[ ":$PATH:" != *":$HOME/.cargo/bin:"* ]]; then
        echo "⚠️  Warning: $HOME/.cargo/bin is not in your PATH"
        echo "   Add this line to your shell profile (~/.bashrc, ~/.zshrc, etc.):"
        echo "   export PATH=\"\$HOME/.cargo/bin:\$PATH\""
    fi
else
    # Fallback: copy to /usr/local/bin
    echo "📁 Installing to /usr/local/bin..."
    sudo cp target/release/cwb /usr/local/bin/
    sudo chmod +x /usr/local/bin/cwb
fi

# Verify installation
if command -v cwb &> /dev/null; then
    echo "✅ CWB CLI installed successfully!"
    echo ""
    echo "🚀 Get started with:"
    echo "   cwb --help"
    echo "   cwb init"
    echo "   cwb doctor"
    echo ""
    cwb --version
else
    echo "❌ Installation failed. CWB command not found in PATH."
    echo "   You can run it directly from: $(pwd)/target/release/cwb"
    exit 1
fi
