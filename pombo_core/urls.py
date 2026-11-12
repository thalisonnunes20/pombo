from django.urls import path, include
from django.http import HttpResponse
from .views import set_language_view

def health_check(request):
    return HttpResponse("OK", content_type="text/plain")

urlpatterns = [
    # Health check para Docker
    path('health/', health_check, name='health_check'),

    # Troca de idioma em tempo real
    path('set-lang/<str:lang_code>/', set_language_view, name='set_language'),

    # Autenticação
    path('auth/', include('apps.authentication.urls')),

    # Dashboard & Telas Administrativas
    path('dashboard/', include('apps.dashboard.urls')),

    # Armazenamento e APIs de Upload/Scanner
    path('storage/', include('apps.storage.urls')),

    # Motor de Links e Rotas Públicas (/s/ e /d/)
    path('', include('apps.links.urls')),

    # Redirecionar raiz para o dashboard
    path('', include('apps.dashboard.urls')),
]

