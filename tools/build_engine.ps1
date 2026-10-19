$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path $PSScriptRoot -Parent
Set-Location -LiteralPath $projectRoot
$env:CARGO_HOME = Join-Path $projectRoot '.local\cargo'
$env:RUSTUP_HOME = Join-Path $projectRoot '.local\rustup'
$toolchainName = '1.97.0-x86_64-pc-windows-gnu'
$asciiToolchain = Join-Path $env:TEMP 'uma-rust-gnu-1.97.0'
if (-not (Test-Path -LiteralPath (Join-Path $asciiToolchain 'bin\rustc.exe'))) {
    $sourceToolchain = Join-Path $env:RUSTUP_HOME "toolchains\$toolchainName"
    if (-not (Test-Path -LiteralPath $sourceToolchain)) {
        & (Join-Path $env:CARGO_HOME 'bin\rustup.exe') toolchain install $toolchainName --profile minimal --target wasm32-unknown-unknown
        if ($LASTEXITCODE -ne 0) { throw 'Rust installation failed' }
    }
    Copy-Item -LiteralPath $sourceToolchain -Destination $asciiToolchain -Recurse
}
$env:RUSTC = Join-Path $asciiToolchain 'bin\rustc.exe'
$env:RUSTDOC = Join-Path $asciiToolchain 'bin\rustdoc.exe'
$releaseRemaps = @(
    "--remap-path-prefix=$projectRoot=/uma-race-lab",
    "--remap-path-prefix=$env:USERPROFILE=/build/user",
    "--remap-path-prefix=$($env:USERPROFILE.Replace('\','/'))=/build/user"
)
$env:CARGO_ENCODED_RUSTFLAGS = $releaseRemaps -join [char]31
& (Join-Path $env:CARGO_HOME 'bin\cargo.exe') "+$toolchainName" build --manifest-path 'vendor\honse-sim\source\Cargo.toml' -p honse-sim-wasm --release --target wasm32-unknown-unknown --locked --target-dir (Join-Path $env:TEMP 'uma-rust-target')
if ($LASTEXITCODE -ne 0) {throw 'Engine build failed'}
& (Join-Path $projectRoot '.local\wasm-bindgen\wasm-bindgen.exe') --target web --out-name uma_sim_wasm --out-dir 'vendor\honse-sim' (Join-Path $env:TEMP 'uma-rust-target\wasm32-unknown-unknown\release\uma_sim_wasm.wasm')
if ($LASTEXITCODE -ne 0) {throw 'WASM bindings generation failed'}
