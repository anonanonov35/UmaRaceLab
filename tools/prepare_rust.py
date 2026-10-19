"""Install an isolated Rust toolchain for building the open-source WASM engine."""
import os
from pathlib import Path
import subprocess
import urllib.request

root = Path(__file__).resolve().parents[1]
local = root / ".local"
installer = local / "rustup-init.exe"
with urllib.request.urlopen("https://static.rust-lang.org/rustup/dist/x86_64-pc-windows-msvc/rustup-init.exe", timeout=60) as response:
    installer.write_bytes(response.read())
env = dict(os.environ, CARGO_HOME=str(local / "cargo"), RUSTUP_HOME=str(local / "rustup"), RUSTUP_INIT_SKIP_PATH_CHECK="yes")
subprocess.run([str(installer), "-y", "--no-modify-path", "--profile", "minimal", "--default-toolchain", "1.97.0", "--target", "wasm32-unknown-unknown"], env=env, check=True)
