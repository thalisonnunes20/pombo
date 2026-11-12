import mimetypes
from pathlib import Path
from django.db import models
from django.conf import settings

class StoredFile(models.Model):
    SOURCE_UPLOAD = 'upload'
    SOURCE_EXTERNAL = 'external'
    SOURCE_CHOICES = [
        (SOURCE_UPLOAD, 'Upload Local'),
        (SOURCE_EXTERNAL, 'Pasta Externa Mapeada'),
    ]

    name = models.CharField(max_length=255, verbose_name="Nome do Arquivo")
    relative_path = models.CharField(max_length=1000, verbose_name="Caminho Relativo")
    source = models.CharField(max_length=20, choices=SOURCE_CHOICES, default=SOURCE_UPLOAD, verbose_name="Origem")
    size = models.BigIntegerField(default=0, verbose_name="Tamanho (bytes)")
    mime_type = models.CharField(max_length=150, default='application/octet-stream', verbose_name="MIME Type")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Data de Registro")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Última Atualização")

    class Meta:
        verbose_name = "Arquivo Armazenado"
        verbose_name_plural = "Arquivos Armazenados"
        unique_together = ('source', 'relative_path')
        ordering = ['-updated_at']

    def __str__(self):
        return f"[{self.get_source_display()}] {self.name}"

    @property
    def formatted_size(self):
        """Retorna o tamanho em formato legível para humanos."""
        num = float(self.size)
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if abs(num) < 1024.0:
                return f"{num:3.1f} {unit}"
            num /= 1024.0
        return f"{num:.1f} PB"

    @property
    def extension(self):
        return Path(self.name).suffix.lower()

    @property
    def file_category(self):
        """Classifica o arquivo para preview ou ícones específicos."""
        mime = self.mime_type.lower()
        ext = self.extension
        if mime.startswith('image/') or ext in ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.svg', '.bmp']:
            return 'image'
        if mime.startswith('video/') or ext in ['.mp4', '.mkv', '.webm', '.mov', '.avi']:
            return 'video'
        if mime.startswith('audio/') or ext in ['.mp3', '.wav', '.ogg', '.flac', '.m4a']:
            return 'audio'
        if ext in ['.zip', '.tar', '.gz', '.bz2', '.7z', '.rar']:
            return 'archive'
        if ext in ['.pdf', '.txt', '.md', '.json', '.csv', '.doc', '.docx']:
            return 'document'
        return 'other'

    @property
    def absolute_path(self) -> Path:
        """Retorna o caminho absoluto verificado."""
        base = settings.UPLOAD_STORAGE_DIR if self.source == self.SOURCE_UPLOAD else settings.EXTERNAL_STORAGE_DIR
        target = (base / self.relative_path).resolve()
        # Verificação rigorosa contra Path Traversal
        if not str(target).startswith(str(base.resolve())):
            raise PermissionError("Tentativa de acesso fora do diretório de armazenamento permitido.")
        return target

