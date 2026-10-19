# Sources and attribution

Uma Race Lab is an unofficial, AI-assisted research project. No Cygames game binaries, extracted databases, game assets or decompiled game source are distributed here.

- **jalbarrang / torena-sim, honse-sim 0.13.0** — https://github.com/jalbarrang/torena-sim — GPL-3.0-only. Pinned commit `6ebb31f0466242395b316ee1d5933f057dfe8ec7`. The Rust simulation and WASM adapter source, original license and locally rebuilt WASM/JS are in `vendor/honse-sim/`. Local amendments are described in its PATCHES.md. The mechanics documentation is a community source, not proof of Global-version accuracy. Source is provided for the included compiled component.
- **alpha123 / uma-tools** — https://github.com/alpha123/uma-tools — GPL-3.0. Public resource-format interoperability and asset-reading logic consulted, pinned `c330bbb7acf34c36595254f5dcd1f18497bebf3a`. Earlier race-formula research also consulted https://github.com/alpha123/uma-skill-tools. Research sources remain in excluded `.local/references/`.
- **katboi01 / UmaViewer** — https://github.com/katboi01/UmaViewer — public Global/JP resource-format configuration and read-only SQLite compatibility consulted. Pinned `07f82e9fa08f23c1cda3a9be3045a09372eae8bb`. Only the factual Global file-format parameters are used in our reader; no UmaViewer C# source or configuration is bundled. These public format constants are not player/account credentials.
- **utelle / SQLite3MultipleCiphers** — https://github.com/utelle/SQLite3MultipleCiphers — MIT with component notices. Official 2.6.1 Windows binary is included in the Windows release for read-only resource-index access; LICENSE and SPDX notices are in licenses/. Not bundled in the source archive. Official archive URL and SHA256 are pinned in tools/prepare_release_deps.py.
- **K0lb3 / UnityPy** — https://github.com/K0lb3/UnityPy — MIT, 1.25.4. Parses the user's own course/parameter bundles. Included with its Python dependencies in the Windows release; package versions and license files are recorded in BUILD-INFO.json and licenses/python-packages/. No user's extracted game resources are included.
- **Perfare / Il2CppDumper** — https://github.com/Perfare/Il2CppDumper — MIT, local static research tool/layout reference, not bundled.
- **SamboyCoding / Cpp2IL** — https://github.com/SamboyCoding/Cpp2IL — local static research tool, not bundled.
- **Rust / wasm-bindgen** — official compiler and matching CLI used in an isolated `.local/` toolchain. Their libraries retain their own licenses. No system PATH change is needed.
- **Python / Tcl / Tk / Node.js** — application runtimes. The Windows release bundles Python 3.12/Tcl/Tk and official Node.js 24.18.1 win-x64. Python, Tcl, Tk and the full Node.js notices are included under licenses/. Node's official archive URL and SHA256 are pinned in tools/prepare_release_deps.py.
- **PyInstaller** — https://pyinstaller.org/ — 6.22.3, GPL with the bootloader exception. Used to create the standalone directory bundle; its distribution license and exception are included under licenses/python-packages/. Build dependencies are pinned in requirements-build.txt.
- **rehan-remade / universal-modder** — https://github.com/rehan-remade/universal-modder — workflow references through installed skills; no runtime dependency.

The project includes GPL-3.0 components; see LICENSE and vendor/honse-sim/LICENSE. No publication, upload or upstream contribution has been made.

Windows releases are paired with the complete application/Rust source archive and SHA256SUMS.txt. No credentials are required to build. The optional GitHub Actions workflow creates downloadable candidate artifacts only; the owner chooses when to publish a release.
