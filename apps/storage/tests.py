import tempfile
from pathlib import Path
from django.test import TestCase, override_settings
from django.contrib.auth import get_user_model
from apps.storage.models import StoredFile
from apps.storage.services import list_directory_contents, scan_storage_directory

User = get_user_model()

class StorageHierarchyTests(TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.base_path = Path(self.temp_dir.name)

        # Cria árvore de pastas simulando Jellyfin
        # Jellyfin/
        #   Filmes/
        #     matrix.mp4
        #   Series/
        #     breaking_bad/
        #       s01e01.mkv
        #   Animes/
        (self.base_path / 'Filmes').mkdir(parents=True)
        (self.base_path / 'Filmes' / 'matrix.mp4').write_bytes(b'fake movie data')

        (self.base_path / 'Series' / 'breaking_bad').mkdir(parents=True)
        (self.base_path / 'Series' / 'breaking_bad' / 's01e01.mkv').write_bytes(b'fake episode data')

        (self.base_path / 'Animes').mkdir(parents=True)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_list_directory_contents_root(self):
        with override_settings(EXTERNAL_STORAGE_DIR=self.base_path):
            result = list_directory_contents('external', '')
            folder_names = [f['name'] for f in result['folders']]
            self.assertIn('Filmes', folder_names)
            self.assertIn('Series', folder_names)
            self.assertIn('Animes', folder_names)
            self.assertEqual(len(result['files']), 0)
            self.assertIsNone(result['parent_folder'])

    def test_list_directory_contents_subfolder(self):
        with override_settings(EXTERNAL_STORAGE_DIR=self.base_path):
            result = list_directory_contents('external', 'Filmes')
            self.assertEqual(len(result['files']), 1)
            self.assertEqual(result['files'][0].name, 'matrix.mp4')
            self.assertEqual(result['files'][0].relative_path, 'Filmes/matrix.mp4')
            self.assertEqual(result['parent_folder'], '')

    def test_scan_storage_directory_recursive(self):
        with override_settings(EXTERNAL_STORAGE_DIR=self.base_path):
            res = scan_storage_directory('external')
            self.assertEqual(res['scanned'], 2)
            self.assertEqual(StoredFile.objects.filter(source='external').count(), 2)

    def test_explorer_view_renders_folder_tree(self):
        (self.base_path / "Grey's Anatomy & Co").mkdir()
        (self.base_path / "Grey's Anatomy & Co" / 'ep01.mp4').write_bytes(b'x')
        admin = User.objects.create_superuser('root', 'r@x.com', 'pass12345')
        self.client.force_login(admin)
        with override_settings(EXTERNAL_STORAGE_DIR=self.base_path):
            r = self.client.get('/explorer/', {'source': 'external'})
            self.assertEqual(r.status_code, 200)
            self.assertContains(r, 'Filmes')
            self.assertContains(r, 'folder=Grey%27s%20Anatomy%20%26%20Co')
            r = self.client.get('/explorer/', {'source': 'external', 'folder': "Grey's Anatomy & Co"})
            self.assertEqual(r.status_code, 200)
            self.assertContains(r, 'ep01.mp4')
            # Path traversal deve cair na raiz, nunca sair do diretorio mapeado
            r = self.client.get('/explorer/', {'source': 'external', 'folder': '../../etc'})
            self.assertEqual(r.status_code, 200)
            self.assertNotContains(r, 'passwd')

    def test_accel_path_and_disposition_encode_special_chars(self):
        from apps.storage.services import build_accel_redirect_path, build_content_disposition
        f = StoredFile(source='external', name='Quem Somos? #1.mkv', relative_path='Filmes/Quem Somos? #1.mkv')
        self.assertEqual(build_accel_redirect_path(f), '/_protected/external/Filmes/Quem%20Somos%3F%20%231.mkv')
        disp = build_content_disposition('進撃の巨人 01.mkv')
        disp.encode('latin-1')  # header precisa ser ASCII/latin-1 valido
        self.assertIn("filename*=utf-8''", disp)

