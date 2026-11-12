from django.http import HttpResponseRedirect
from django.views.decorators.http import require_http_methods
from .translations import TRANSLATIONS

@require_http_methods(["GET", "POST"])
def set_language_view(request, lang_code):
    """
    Alterna o idioma do sistema (en ou pt-br) e redireciona de volta para a página anterior.
    """
    clean_lang = lang_code.lower()
    if clean_lang not in TRANSLATIONS:
        clean_lang = 'en'

    next_url = request.META.get('HTTP_REFERER') or '/'
    response = HttpResponseRedirect(next_url)
    # Define o cookie por 365 dias
    response.set_cookie(
        'pombo_language',
        clean_lang,
        max_age=365 * 24 * 60 * 60,
        samesite='Lax'
    )
    return response

