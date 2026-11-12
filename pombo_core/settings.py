import os
from pathlib import Path

try:
    import dj_database_url
except ImportError:
    dj_database_url = None

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.getenv('SECRET_KEY', 'pombo-insecure-development-secret-key-change-in-prod')

DEBUG = os.getenv('DEBUG', '1') == '1'

ALLOWED_HOSTS = [h.strip() for h in os.getenv('ALLOWED_HOSTS', '*').split(',') if h.strip()]
for internal_host in ['localhost', '127.0.0.1', '[::1]', 'testserver']:
    if internal_host not in ALLOWED_HOSTS:
        ALLOWED_HOSTS.append(internal_host)

raw_csrf = os.getenv('CSRF_TRUSTED_ORIGINS', '')
parsed_csrf = []
for origin in raw_csrf.split(','):
    item = origin.strip()
    if not item:
        continue
    if item.startswith('http://') or item.startswith('https://'):
        parsed_csrf.append(item)
    else:
        # Se o domínio foi informado sem protocolo (ex: pombo.tsnunes.com.br), adiciona https e http
        parsed_csrf.append(f'https://{item}')
        parsed_csrf.append(f'http://{item}')

if parsed_csrf:
    CSRF_TRUSTED_ORIGINS = list(dict.fromkeys(parsed_csrf))
else:
    CSRF_TRUSTED_ORIGINS = ['http://localhost:8080', 'http://127.0.0.1:8080', 'http://localhost']

INSTALLED_APPS = [
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    # Pombo Apps
    'apps.authentication',
    'apps.storage',
    'apps.links',
    'apps.dashboard',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
]
try:
    import whitenoise
    MIDDLEWARE.append('whitenoise.middleware.WhiteNoiseMiddleware')
except ImportError:
    whitenoise = None

MIDDLEWARE.extend([
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
])

ROOT_URLCONF = 'pombo_core.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'pombo_core.context_processors.i18n_context',
            ],
        },
    },
]

WSGI_APPLICATION = 'pombo_core.wsgi.application'

# Configuração de Banco de Dados: Flexível (SQLite padrão, PostgreSQL/MySQL via DATABASE_URL)
DATABASE_URL = os.getenv('DATABASE_URL')
if DATABASE_URL:
    DATABASES = {
        'default': dj_database_url.config(default=DATABASE_URL, conn_max_age=600)
    }
else:
    data_dir = BASE_DIR / 'data'
    data_dir.mkdir(parents=True, exist_ok=True)
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': data_dir / 'pombo.sqlite3',
            'OPTIONS': {
                'timeout': 20, # Reduz lock em concorrência
            }
        }
    }

AUTH_USER_MODEL = 'authentication.User'

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator', 'OPTIONS': {'min_length': 8}},
]

DEFAULT_LANGUAGE = os.getenv('DEFAULT_LANGUAGE', 'en')
LANGUAGE_CODE = 'pt-br' if DEFAULT_LANGUAGE.lower() in ['pt', 'pt-br'] else 'en-us'
TIME_ZONE = 'America/Sao_Paulo'
USE_I18N = True
USE_TZ = True

STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [
    BASE_DIR / 'static',
]
if whitenoise:
    STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

LOGIN_URL = 'login'
LOGIN_REDIRECT_URL = 'dashboard_overview'
LOGOUT_REDIRECT_URL = 'login'

# Diretórios de Armazenamento mapeados via Docker Volume
STORAGE_DIR = BASE_DIR / 'storage'
UPLOAD_STORAGE_DIR = Path(os.getenv('UPLOAD_STORAGE_DIR', STORAGE_DIR / 'uploads'))
EXTERNAL_STORAGE_DIR = Path(os.getenv('EXTERNAL_STORAGE_DIR', STORAGE_DIR / 'external'))

UPLOAD_STORAGE_DIR.mkdir(parents=True, exist_ok=True)
EXTERNAL_STORAGE_DIR.mkdir(parents=True, exist_ok=True)

# Ativar X-Accel-Redirect do Nginx (padrão 1 em produção, 0 para teste local sem Nginx)
USE_X_ACCEL = os.getenv('USE_X_ACCEL', '1') == '1'

# Segurança HTTP e Cookies
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'SAMEORIGIN'
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'Lax'
CSRF_COOKIE_SAMESITE = 'Lax'

# Cache em memória para Rate Limiting e Proteção Anti-Força Bruta
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'pombo-security-cache',
    }
}

# Tamanho máximo de upload permitido no Django (100GB ou ilimitado)
DATA_UPLOAD_MAX_MEMORY_SIZE = 100 * 1024 * 1024 # 100MB em memória, depois usa spool em disco
FILE_UPLOAD_MAX_MEMORY_SIZE = 100 * 1024 * 1024
