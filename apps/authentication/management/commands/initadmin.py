import os
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model

class Command(BaseCommand):
    help = 'Inicializa o superusuário a partir das variáveis de ambiente se configuradas.'

    def handle(self, *args, **options):
        User = get_user_model()
        username = os.getenv('ADMIN_USERNAME')
        password = os.getenv('ADMIN_PASSWORD')
        email = os.getenv('ADMIN_EMAIL', 'admin@pombo.local')

        if not username or not password:
            self.stdout.write(self.style.WARNING('ADMIN_USERNAME ou ADMIN_PASSWORD não foram fornecidos.'))
            return

        user, created = User.objects.get_or_create(username=username, defaults={'email': email})
        user.set_password(password)
        user.is_staff = True
        user.is_superuser = True
        user.can_upload = True
        user.can_create_links = True
        user.can_access_external = True
        user.can_delete_files = True
        user.can_manage_users = True
        user.save()

        if created:
            self.stdout.write(self.style.SUCCESS(f'Superusuário "{username}" criado com sucesso.'))
        else:
            self.stdout.write(self.style.SUCCESS(f'Superusuário "{username}" atualizado com sucesso.'))

