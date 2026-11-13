import os
from datetime import timedelta
from django.test import TestCase
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.conf import settings

from apps.storage.models import StoredFile
from apps.storage.services import save_uploaded_file, scan_storage_directory, resolve_safe_path
from apps.links.models import ShareLink

User = get_user_model()

class PomboCoreTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='operador',
            password='testpassword123',
            can_upload=True,
            can_create_links=True,
            can_access_external=True
        )

    def test_custom_user_permissions(self):
        self.assertTrue(self.user.can_upload)
        self.assertTrue(self.user.can_create_links)
        self.assertTrue(self.user.can_access_external)
        self.assertFalse(self.user.can_delete_files)
        self.assertFalse(self.user.is_admin_or_manager)

    def test_upload_and_category_detection(self):
        video_content = b"fake video mp4 stream"
        uploaded = SimpleUploadedFile("trailer.mp4", video_content, content_type="video/mp4")
        stored = save_uploaded_file(uploaded)

        self.assertEqual(stored.name, "trailer.mp4")
        self.assertEqual(stored.source, StoredFile.SOURCE_UPLOAD)
        self.assertEqual(stored.file_category, "video")
        self.assertTrue(stored.absolute_path.exists())

        # Limpeza do arquivo de teste
        if stored.absolute_path.exists():
            stored.absolute_path.unlink()

    def test_path_traversal_prevention(self):
        # Tentativa de sair da pasta base com ../
        with self.assertRaises(PermissionError):
            resolve_safe_path(StoredFile.SOURCE_UPLOAD, "../../etc/passwd")

        with self.assertRaises(PermissionError):
            resolve_safe_path(StoredFile.SOURCE_EXTERNAL, "../secret_file.txt")

    def test_link_infinite(self):
        fake_file = StoredFile.objects.create(
            name="arquivo.zip",
            relative_path="arquivo.zip",
            source=StoredFile.SOURCE_UPLOAD,
            size=1024,
            mime_type="application/zip"
        )
        link = ShareLink.objects.create(file=fake_file, created_by=self.user)

        self.assertTrue(link.is_valid)
        self.assertFalse(link.is_expired_by_limit)
        self.assertFalse(link.is_expired_by_time)
        self.assertEqual(link.status_display, "Ativo")

    def test_link_click_limit(self):
        fake_file = StoredFile.objects.create(
            name="documento.pdf",
            relative_path="documento.pdf",
            source=StoredFile.SOURCE_UPLOAD,
            size=2048,
            mime_type="application/pdf"
        )
        link = ShareLink.objects.create(file=fake_file, max_downloads=2)

        self.assertTrue(link.is_valid)
        self.assertEqual(link.remaining_downloads, 2)

        # Simula 1 download
        link.download_count = 1
        link.save()
        self.assertTrue(link.is_valid)
        self.assertEqual(link.remaining_downloads, 1)

        # Simula 2 downloads (esgotado)
        link.download_count = 2
        link.save()
        self.assertFalse(link.is_valid)
        self.assertTrue(link.is_expired_by_limit)
        self.assertEqual(link.status_display, "Limite Atingido")

    def test_link_time_expiration(self):
        fake_file = StoredFile.objects.create(
            name="foto.png",
            relative_path="foto.png",
            source=StoredFile.SOURCE_UPLOAD,
            size=512,
            mime_type="image/png"
        )
        past_time = timezone.now() - timedelta(minutes=5)
        link = ShareLink.objects.create(file=fake_file, expires_at=past_time)

        self.assertFalse(link.is_valid)
        self.assertTrue(link.is_expired_by_time)
        self.assertEqual(link.status_display, "Expirado por Tempo")

    def test_link_combined_clicks_and_time(self):
        fake_file = StoredFile.objects.create(
            name="release.tar.gz",
            relative_path="release.tar.gz",
            source=StoredFile.SOURCE_UPLOAD,
            size=4096,
            mime_type="application/gzip"
        )
        future_time = timezone.now() + timedelta(hours=2)
        link = ShareLink.objects.create(file=fake_file, max_downloads=3, expires_at=future_time)

        # Inicialmente válido
        self.assertTrue(link.is_valid)

        # Atingiu cliques antes do tempo
        link.download_count = 3
        link.save()
        self.assertFalse(link.is_valid)
        self.assertEqual(link.status_display, "Limite Atingido")

    def test_i18n_language_switching(self):
        # 1. Rota de alternar idioma para português
        response = self.client.get('/set-lang/pt-br/')
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.cookies['pombo_language'].value, 'pt-br')

        # 2. Rota de alternar idioma para inglês
        response = self.client.get('/set-lang/en/')
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.cookies['pombo_language'].value, 'en')

    def test_folder_share_link_creation_navigation_and_zip(self):
        import io
        import tempfile
        import zipfile
        from pathlib import Path
        from django.test import override_settings

        with tempfile.TemporaryDirectory() as tmp_ext:
            ext_root = Path(tmp_ext)
            show_dir = ext_root / "Series" / "Breaking Bad"
            season_dir = show_dir / "Season 1"
            season_dir.mkdir(parents=True)
            (season_dir / "S01E01.mp4").write_bytes(b"episode 1 binary payload")
            (show_dir / "poster.jpg").write_bytes(b"jpeg image bytes")
            (ext_root / "secret_outside.txt").write_bytes(b"should not be accessible")

            with override_settings(EXTERNAL_STORAGE_DIR=ext_root):
                self.client.force_login(self.user)
                resp = self.client.post('/api/create/', {
                    'folder_source': StoredFile.SOURCE_EXTERNAL,
                    'folder_path': 'Series/Breaking Bad',
                    'is_direct': 'false',
                })
                self.assertEqual(resp.status_code, 200)
                data = resp.json()
                self.assertTrue(data['success'])
                token = data['link']['token']

                link = ShareLink.objects.get(token=token)
                self.assertTrue(link.file.is_directory)
                self.assertEqual(link.file.name, "Breaking Bad")

                # 1. Página pública da pasta lista subpastas e arquivos
                pub_resp = self.client.get(f'/s/{token}/')
                self.assertEqual(pub_resp.status_code, 200)
                self.assertContains(pub_resp, "Season 1")
                self.assertContains(pub_resp, "poster.jpg")

                # 2. Navegação em subpasta dentro do link compartilhado
                sub_resp = self.client.get(f'/s/{token}/?sub=Season%201')
                self.assertEqual(sub_resp.status_code, 200)
                self.assertContains(sub_resp, "S01E01.mp4")

                # 3. Download individual de arquivo dentro da pasta via X-Accel-Redirect
                dl_file_resp = self.client.get(
                    f'/d/{token}/?file=Season%201/S01E01.mp4',
                    HTTP_X_ACCEL_SUPPORTED='1',
                )
                self.assertEqual(dl_file_resp.status_code, 200)
                self.assertEqual(
                    dl_file_resp['X-Accel-Redirect'],
                    '/_protected/external/Series/Breaking%20Bad/Season%201/S01E01.mp4'
                )

                # 4. Bloqueio de Path Traversal tentando sair da pasta compartilhada
                traversal_resp = self.client.get(f'/d/{token}/?file=../../secret_outside.txt')
                self.assertEqual(traversal_resp.status_code, 404)

                # 5. Download da pasta completa em streaming .zip
                zip_resp = self.client.get(f'/d/{token}/')
                self.assertEqual(zip_resp.status_code, 200)
                self.assertEqual(zip_resp['Content-Type'], 'application/zip')
                zip_bytes = b''.join(zip_resp.streaming_content)
                with zipfile.ZipFile(io.BytesIO(zip_bytes), 'r') as zf:
                    self.assertIsNone(zf.testzip())
                    names = sorted(zf.namelist())
                    self.assertEqual(names, ['Season 1/S01E01.mp4', 'poster.jpg'])
                    self.assertEqual(zf.read('Season 1/S01E01.mp4'), b"episode 1 binary payload")


