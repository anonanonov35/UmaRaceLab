"""Separate immutable application resources from user-owned files."""
import os
from pathlib import Path
import shutil
import sys


def resource_root():
    return Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parents[1]))


def user_data_dir():
    override = os.environ.get('UMA_LAB_DATA_DIR')
    if override:
        return Path(override).expanduser().resolve()
    if getattr(sys, 'frozen', False):
        base=Path(os.environ['LOCALAPPDATA']) if os.environ.get('LOCALAPPDATA') else Path.home()/'AppData/Local'
        return base / 'UmaRaceLab'
    return resource_root() / 'local'


def node_executable():
    override = os.environ.get('UMA_LAB_NODE')
    candidates = [override, resource_root() / 'runtime/node.exe', shutil.which('node')]
    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            return str(Path(candidate).resolve())
    candidate=Path.home()/'.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node.exe'
    if candidate.is_file():return str(candidate.resolve())
    raise ValueError('Для расчёта требуется Node.js; на этом ПК используется установленный runtime.')


def index_library():
    candidates = [resource_root() / 'runtime/sqlite3mc_x64.dll',
                  resource_root() / '.local/sqlite3mc/dll/sqlite3mc_x64.dll']
    for path in candidates:
        if path.is_file():
            return path
    raise ValueError('Отсутствует библиотека чтения трасс. Переустановите сборку или выполните python tools/prepare_release_deps.py.')
