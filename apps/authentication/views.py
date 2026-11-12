from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout, get_user_model
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_POST, require_http_methods
from apps.dashboard.models import log_event, AuditLog
from pombo_core.security import check_login_lockout, record_login_attempt, get_client_ip
from pombo_core.translations import get_translations

User = get_user_model()

@require_http_methods(["GET", "POST"])
def login_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard_overview')

    lang = request.session.get('django_language') or getattr(request, 'current_lang', 'en')
    t = get_translations(lang)

    error_message = None
    if request.method == "POST":
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')

        # 1. Proteção Anti-Força Bruta: Verificar bloqueio temporário
        is_locked, remaining = check_login_lockout(request, username)
        if is_locked:
            log_event(
                AuditLog.CATEGORY_AUTH,
                f"Tentativa de login bloqueada por taxa de limite (Brute-force) para IP {get_client_ip(request)} (Usuário: '{username}')",
                level=AuditLog.LEVEL_ERROR,
                request=request
            )
            error_message = t.get('login_rate_limited', 'Muitas tentativas. Aguarde {seconds}s.').replace('{seconds}', str(remaining))
            return render(request, 'auth/login.html', {'error': error_message}, status=429)

        user = authenticate(request, username=username, password=password)
        if user is not None:
            if user.is_active:
                record_login_attempt(request, username, success=True)
                login(request, user)

                # Suporte à opção "Salvar Login" (Persistência da sessão por 30 dias)
                remember_me = request.POST.get('remember_me') in ['true', '1', 'on']
                if remember_me:
                    request.session.set_expiry(60 * 60 * 24 * 30) # 30 dias
                else:
                    request.session.set_expiry(0) # Expira ao fechar navegador

                log_event(AuditLog.CATEGORY_AUTH, f"Usuário '{username}' realizou login (Salvar login: {remember_me})", request=request)
                next_url = request.GET.get('next', 'dashboard_overview')
                return redirect(next_url)
            else:
                log_event(AuditLog.CATEGORY_AUTH, f"Tentativa de login de usuário inativo: '{username}'", level=AuditLog.LEVEL_WARNING, request=request)
                error_message = t.get('login_inactive_user', "Usuário inativo.")
        else:
            is_locked_now, duration = record_login_attempt(request, username, success=False)
            if is_locked_now:
                log_event(
                    AuditLog.CATEGORY_AUTH,
                    f"IP {get_client_ip(request)} bloqueado por 5 minutos após 5 falhas consecutivas de login.",
                    level=AuditLog.LEVEL_ERROR,
                    request=request
                )
                error_message = t.get('login_rate_limited', 'Muitas tentativas. Aguarde {seconds}s.').replace('{seconds}', str(duration))
            else:
                log_event(AuditLog.CATEGORY_AUTH, f"Falha de autenticação para o usuário: '{username}'", level=AuditLog.LEVEL_WARNING, request=request)
                error_message = t.get('login_invalid_credentials', "Credenciais inválidas.")

    return render(request, 'auth/login.html', {'error': error_message})

@login_required
def logout_view(request):
    logout(request)
    return redirect('login')

@login_required
@require_POST
def create_user_api(request):
    if not request.user.can_manage_users and not request.user.is_superuser:
        return JsonResponse({'success': False, 'error': 'Permissão negada.'}, status=403)

    username = request.POST.get('username', '').strip()
    password = request.POST.get('password', '').strip()
    email = request.POST.get('email', '').strip()

    if not username or not password:
        return JsonResponse({'success': False, 'error': 'Usuário e senha são obrigatórios.'}, status=400)

    if len(password) < 8:
        return JsonResponse({'success': False, 'error': 'A senha deve conter pelo menos 8 caracteres.'}, status=400)

    if User.objects.filter(username=username).exists():
        return JsonResponse({'success': False, 'error': 'Nome de usuário já está em uso.'}, status=400)

    user = User.objects.create_user(
        username=username,
        email=email,
        password=password,
        can_upload=request.POST.get('can_upload') == 'true',
        can_create_links=request.POST.get('can_create_links') == 'true',
        can_access_external=request.POST.get('can_access_external') == 'true',
        can_delete_files=request.POST.get('can_delete_files') == 'true',
        can_manage_users=request.POST.get('can_manage_users') == 'true',
    )

    return JsonResponse({'success': True, 'user': {
        'id': user.id,
        'username': user.username,
        'email': user.email,
    }})

@login_required
@require_POST
def toggle_user_status_api(request, user_id):
    if not request.user.can_manage_users and not request.user.is_superuser:
        return JsonResponse({'success': False, 'error': 'Permissão negada.'}, status=403)

    target_user = get_object_or_404(User, id=user_id)
    if target_user.id == request.user.id:
        return JsonResponse({'success': False, 'error': 'Você não pode desativar seu próprio usuário.'}, status=400)

    target_user.is_active = not target_user.is_active
    target_user.save(update_fields=['is_active'])
    return JsonResponse({'success': True, 'is_active': target_user.is_active})

