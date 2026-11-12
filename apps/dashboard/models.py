from django.db import models
from django.conf import settings

class AuditLog(models.Model):
    CATEGORY_LINK = 'link'
    CATEGORY_DOWNLOAD = 'download'
    CATEGORY_UPLOAD = 'upload'
    CATEGORY_DELETE = 'delete'
    CATEGORY_AUTH = 'auth'
    CATEGORY_ERROR = 'error'

    CATEGORY_CHOICES = [
        (CATEGORY_LINK, 'Criação de Links'),
        (CATEGORY_DOWNLOAD, 'Downloads & Acessos'),
        (CATEGORY_UPLOAD, 'Envio de Arquivos'),
        (CATEGORY_DELETE, 'Exclusão'),
        (CATEGORY_AUTH, 'Autenticação'),
        (CATEGORY_ERROR, 'Erros do Sistema'),
    ]

    LEVEL_INFO = 'INFO'
    LEVEL_WARNING = 'WARN'
    LEVEL_ERROR = 'ERROR'

    LEVEL_CHOICES = [
        (LEVEL_INFO, 'INFO'),
        (LEVEL_WARNING, 'WARN'),
        (LEVEL_ERROR, 'ERROR'),
    ]

    created_at = models.DateTimeField(auto_now_add=True, db_index=True, verbose_name="Data/Hora")
    category = models.CharField(max_length=30, choices=CATEGORY_CHOICES, db_index=True, verbose_name="Categoria")
    level = models.CharField(max_length=10, choices=LEVEL_CHOICES, default=LEVEL_INFO, db_index=True, verbose_name="Nível")
    message = models.CharField(max_length=500, verbose_name="Mensagem")
    ip_address = models.CharField(max_length=50, null=True, blank=True, verbose_name="Endereço IP")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Usuário")
    details = models.TextField(blank=True, default='', verbose_name="Detalhes Adicionais")

    class Meta:
        verbose_name = "Log de Auditoria"
        verbose_name_plural = "Logs de Auditoria"
        ordering = ['-created_at']

    def __str__(self):
        return f"[{self.created_at.strftime('%Y-%m-%d %H:%M:%S')}] [{self.category.upper()}] {self.message}"

def get_client_ip(request):
    if not request:
        return None
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0].strip()
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip

def log_event(category: str, message: str, level: str = AuditLog.LEVEL_INFO, request=None, details: str = ''):
    """
    Grava um log estruturado no banco de dados.
    """
    try:
        user = None
        ip = None
        if request:
            if hasattr(request, 'user') and request.user.is_authenticated:
                user = request.user
            ip = get_client_ip(request)

        AuditLog.objects.create(
            category=category,
            level=level,
            message=message,
            ip_address=ip,
            user=user,
            details=details
        )
    except Exception:
        # Nunca quebra a aplicação caso ocorra falha de log
        pass

