from django.contrib.auth.models import AbstractUser
from django.db import models

class User(AbstractUser):
    """
    Modelo de usuário customizado do Pombo com permissões granulares.
    """
    can_upload = models.BooleanField(
        default=True,
        verbose_name="Pode enviar arquivos",
        help_text="Permite fazer upload de fotos, vídeos e outros arquivos."
    )
    can_create_links = models.BooleanField(
        default=True,
        verbose_name="Pode gerar links",
        help_text="Permite gerar links compartilháveis temporários ou infinitos."
    )
    can_access_external = models.BooleanField(
        default=False,
        verbose_name="Pode acessar pastas mapeadas",
        help_text="Permite visualizar e criar links a partir da pasta externa do host."
    )
    can_delete_files = models.BooleanField(
        default=False,
        verbose_name="Pode excluir arquivos",
        help_text="Permite excluir arquivos enviados."
    )
    can_manage_users = models.BooleanField(
        default=False,
        verbose_name="Pode gerenciar usuários",
        help_text="Permite criar novos usuários e gerenciar permissões."
    )

    class Meta:
        verbose_name = "Usuário"
        verbose_name_plural = "Usuários"
        ordering = ['username']

    @property
    def is_admin_or_manager(self):
        return self.is_superuser or self.can_manage_users

