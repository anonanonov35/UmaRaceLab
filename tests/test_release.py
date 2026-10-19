from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from uma_lab import paths
from uma_lab.courses import cache_path
from tools.check_release import validate_source


class ReleaseTests(unittest.TestCase):
    def test_archive_rejects_private_data_and_game_files(self):
        for name in ('local/autosave-builds.json','.local/reference.json','runtime/node.exe','../outside.py',
                     '.env','keys/private.pem','master.mdb','meta.dat','dump/GameAssembly.dll'):
            with self.subTest(name=name),self.assertRaises(ValueError):validate_source(name,b'')
        validate_source('uma_lab/models.py',b'public application code')
        validate_source('vendor/honse-sim/uma_sim_wasm_bg.wasm',b'own compiled open-source engine')

    def test_archive_rejects_credential_material_and_personal_paths(self):
        for blob in (b'gh'+b'p_'+b'a'*36,b'-----BEGIN '+b'PRIVATE KEY-----',b'C:/'+b'Users/test-person/private'):
            with self.subTest(blob=blob[:8]),self.assertRaises(ValueError):validate_source('example.txt',blob)

    def test_frozen_data_is_separate_from_bundle(self):
        with patch.object(paths.sys,'frozen',True,create=True),patch.dict(paths.os.environ,{'LOCALAPPDATA':'user-data'},clear=True):
            self.assertEqual(paths.user_data_dir(),Path('user-data/UmaRaceLab'))

    def test_explicit_user_folder_overrides_default(self):
        with tempfile.TemporaryDirectory() as directory,patch.dict(paths.os.environ,{'UMA_LAB_DATA_DIR':directory}):
            self.assertEqual(paths.user_data_dir(),Path(directory).resolve())

    def test_bundled_node_works_without_system_path(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);(root/'runtime').mkdir();(root/'runtime/node.exe').write_bytes(b'fixture')
            with patch.object(paths,'resource_root',return_value=root),patch.dict(paths.os.environ,{},clear=True),patch.object(paths.shutil,'which',return_value=None):
                self.assertEqual(paths.node_executable(),str((root/'runtime/node.exe').resolve()))

    def test_separate_cache_can_force_a_cold_start(self):
        with tempfile.TemporaryDirectory() as directory,patch.dict(paths.os.environ,{'UMA_LAB_CACHE_DIR':directory}):
            path=cache_path(Path('example/master.mdb'))
            self.assertTrue(path.is_relative_to(Path(directory)))
            self.assertFalse(path.exists())


if __name__=='__main__':unittest.main()
