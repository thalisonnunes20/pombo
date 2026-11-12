import secrets
from django.db import models
from django.utils import timezone
from django.conf import settings
from apps.storage.models import StoredFile

def generate_unique_token():
    # 12 bytes urlsafe = 16 caracteres alfanuméricos seguros
    return secrets.token_urlsafe(12)

class ShareLink(models.Model):
    token = models.CharField(max_length=64, unique=True, default=generate_unique_token, db_index=True)
    file = models.ForeignKey(StoredFile, on_delete=models.CASCADE, related_name='share_links')
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)

    # Regras de validade
    max_downloads = models.PositiveIntegerField(null=True, blank=True, help_text="Limite de cliques/downloads. Nulo = infinito.")
    download_count = models.PositiveIntegerField(default=0, help_text="Total de downloads realizados.")
    expires_at = models.DateTimeField(null=True, blank=True, help_text="Data de expiração. Nulo = sem limite de tempo.")

    # Opções de entrega
    is_direct = models.BooleanField(default=False, help_text="Se verdadeiro, baixa diretamente sem passar pela página web.")
    is_active = models.BooleanField(default=True, help_text="Permite revogar o link a qualquer momento.")

    created_at = models.DateTimeField(auto_now_add=True)
    last_downloaded_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Link de Compartilhamento"
        verbose_name_plural = "Links de Compartilhamento"
        ordering = ['-created_at']

    def __str__(self):
        return f"Link {self.token} -> {self.file.name}"

    @property
    def is_expired_by_time(self) -> bool:
        if self.expires_at is None:
            return False
        return timezone.now() > self.expires_at

    @property
    def is_expired_by_limit(self) -> bool:
        if self.max_downloads is None:
            return False
        return self.download_count >= self.max_downloads

    @property
    def is_valid(self) -> bool:
        if not self.is_active:
            return False
        if self.is_expired_by_time:
            return False
        if self.is_expired_by_limit:
            return False
        return True

    @property
    def remaining_downloads(self):
        if self.max_downloads is None:
            return None
        return max(0, self.max_downloads - self.download_count)

    @property
    def status_display(self) -> str:
        if not self.is_active:
            return "Revogado"
        if self.is_expired_by_time:
            return "Expirado por Tempo"
        if self.is_expired_by_limit:
            return "Limite Atingido"
        return "Ativo"

