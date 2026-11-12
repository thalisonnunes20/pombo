import os
import json
from .translations import TRANSLATIONS

def get_current_language(request) -> str:
    lang = request.COOKIES.get('pombo_language')
    if lang in TRANSLATIONS:
        return lang

    default_env = os.getenv('DEFAULT_LANGUAGE', 'en').lower().strip()
    if default_env in ['pt', 'pt-br', 'pt_br']:
        return 'pt-br'
    return 'en'

def i18n_context(request):
    lang = get_current_language(request)
    t_dict = TRANSLATIONS.get(lang, TRANSLATIONS['en'])
    return {
        't': t_dict,
        'current_lang': lang,
        't_json': json.dumps(t_dict),
        'available_langs': [
            ('en', 'English'),
            ('pt-br', 'Português'),
        ],
    }

