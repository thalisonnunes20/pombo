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

