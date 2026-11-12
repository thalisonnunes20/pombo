#!/bin/sh
set -e

# Criar pastas essenciais se não existirem
mkdir -p /app/data
mkdir -p /app/storage/uploads
mkdir -p /app/storage/external
mkdir -p /app/staticfiles
mkdir -p /var/log/supervisor /var/log/nginx

# Garantir permissões para nginx e gunicorn
chown -R www-data:www-data /app/storage/uploads /app/data /app/staticfiles || true
chmod -R 775 /app/storage/uploads /app/data /app/staticfiles || true

echo "==> Executando migrações do banco de dados..."
python manage.py migrate --noinput

echo "==> Coletando arquivos estáticos..."
python manage.py collectstatic --noinput

# Otimização de performance se estiver usando SQLite: Ativar modo WAL (Write-Ahead Logging)
if [ -f "/app/data/pombo.sqlite3" ]; then
    python -c "
import sqlite3
con = sqlite3.connect('/app/data/pombo.sqlite3')
con.execute('PRAGMA journal_mode=WAL;')
con.close()
" 2>/dev/null || true
fi

# Criar usuário admin inicial caso configurado via variáveis de ambiente
if [ -n "$ADMIN_USERNAME" ] && [ -n "$ADMIN_PASSWORD" ]; then
    echo "==> Verificando/Criando usuário administrador inicial..."
    python manage.py initadmin
fi

echo "==> Iniciando Nginx e Gunicorn através do Supervisor..."
exec /usr/bin/supervisord -c /etc/supervisor/conf.d/supervisord.conf

