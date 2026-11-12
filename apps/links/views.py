from datetime import timedelta
from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse, HttpResponse, HttpResponseNotFound, FileResponse
from django.views.decorators.http import require_POST, require_GET
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.db.models import F
from django.conf import settings

from apps.storage.models import StoredFile
from apps.storage.services import build_accel_redirect_path, build_content_disposition
from apps.dashboard.models import log_event, AuditLog
from pombo_core.security import get_client_ip, check_rate_limit
from .models import ShareLink

SAFE_INLINE_MIMES = {
    'image/jpeg', 'image/png', 'image/gif', 'image/webp',
    'video/mp4', 'video/webm', 'video/ogg',
    'audio/mpeg', 'audio/ogg', 'audio/wav',
    'application/pdf',
}

@login_required
@require_POST
def create_link_api(request):
    """Cria um novo link compartilhável para um arquivo."""
    if not request.user.can_create_links and not request.user.is_superuser:
        return JsonResponse({'success': False, 'error': 'Você não tem permissão para gerar links.'}, status=403)

    file_id = request.POST.get('file_id')
    stored_file = get_object_or_404(StoredFile, id=file_id)

    if stored_file.source == StoredFile.SOURCE_EXTERNAL and not request.user.can_access_external and not request.user.is_superuser:
        return JsonResponse({'success': False, 'error': 'Sem permissão para gerar links de pastas mapeadas.'}, status=403)

    # 1. Limite de downloads (cliques)
    max_downloads = request.POST.get('max_downloads', '').strip()
    max_downloads_val = None
    if max_downloads and max_downloads.isdigit():
        max_downloads_val = int(max_downloads)
        if max_downloads_val <= 0:
            max_downloads_val = None

    # 2. Tempo de validade
    expires_at_val = None
    expiry_preset = request.POST.get('expiry_preset', 'none')
    now = timezone.now()

    if expiry_preset == '1h':
        expires_at_val = now + timedelta(hours=1)
    elif expiry_preset == '24h':
        expires_at_val = now + timedelta(days=1)
    elif expiry_preset == '7d':
        expires_at_val = now + timedelta(days=7)
    elif expiry_preset == '30d':
        expires_at_val = now + timedelta(days=30)
    elif expiry_preset == 'custom':
        custom_date_str = request.POST.get('custom_expires_at')
        if custom_date_str:
            parsed = parse_datetime(custom_date_str)
            if parsed and parsed > now:
                expires_at_val = parsed

    # 3. Tipo de entrega: direto vs página
    is_direct = request.POST.get('is_direct', 'false').lower() in ['true', '1', 'on']

    # Criar link
    link = ShareLink.objects.create(
        file=stored_file,
        created_by=request.user,
        max_downloads=max_downloads_val,
        expires_at=expires_at_val,
        is_direct=is_direct,
    )

    log_event(AuditLog.CATEGORY_LINK, f"Link gerado para '{stored_file.name}' (Token: {link.token})", request=request)

    base_url = request.build_absolute_uri('/')[:-1]
    direct_url = f"{base_url}/d/{link.token}/"
    landing_url = f"{base_url}/s/{link.token}/"
    primary_url = direct_url if is_direct else landing_url

    return JsonResponse({
        'success': True,
        'link': {
            'id': link.id,
            'token': link.token,
            'primary_url': primary_url,
            'direct_url': direct_url,
            'landing_url': landing_url,
            'is_direct': link.is_direct,
            'max_downloads': link.max_downloads,
            'expires_at': link.expires_at.strftime('%d/%m/%Y %H:%M') if link.expires_at else 'Infinito',
            'status': link.status_display,
        }
    })

@login_required
@require_POST
def toggle_link_status_api(request, link_id):
    """Ativa ou desativa (revoga) um link."""
    link = get_object_or_404(ShareLink, id=link_id)
    if not request.user.can_create_links and not request.user.is_superuser:
        return JsonResponse({'success': False, 'error': 'Permissão negada.'}, status=403)

    link.is_active = not link.is_active
    link.save(update_fields=['is_active'])
    log_event(AuditLog.CATEGORY_LINK, f"Status do link {link.token} alterado para {link.status_display}", request=request)
    return JsonResponse({'success': True, 'is_active': link.is_active, 'status': link.status_display})

@login_required
@require_POST
def delete_link_api(request, link_id):
    """Exclui permanentemente um link."""
    link = get_object_or_404(ShareLink, id=link_id)
    if not request.user.can_create_links and not request.user.is_superuser:
        return JsonResponse({'success': False, 'error': 'Permissão negada.'}, status=403)

    token = link.token
    link.delete()
    log_event(AuditLog.CATEGORY_DELETE, f"Link de compartilhamento {token} excluído", request=request)
    return JsonResponse({'success': True})

def public_landing_view(request, token):
    """Página de apresentação/download do link compartilhado."""
    try:
        link = ShareLink.objects.select_related('file').get(token=token)
    except ShareLink.DoesNotExist:
        ip = get_client_ip(request)
        is_scan_blocked, _ = check_rate_limit(f"scan:{ip}", max_requests=15, window_seconds=60)
        if is_scan_blocked:
            log_event(
                AuditLog.CATEGORY_ERROR,
                f"Alerta de Segurança: IP {ip} bloqueado temporariamente por varredura de links inexistentes.",
                level=AuditLog.LEVEL_ERROR,
                request=request
            )
            return render(request, 'public/link_expired.html', {'reason': 'Too many requests. Please wait a moment.'}, status=429)
        return render(request, 'public/link_expired.html', {'reason': 'Link não encontrado.'}, status=404)

    # Se o link for configurado como download direto estrito, redireciona para a rota /d/
    if link.is_direct:
        return redirect('direct_download', token=token)

    if not link.is_valid:
        return render(request, 'public/link_expired.html', {
            'reason': link.status_display,
            'link': link
        }, status=410)

    context = {
        'link': link,
        'file': link.file,
        'preview_url': f"/d/{link.token}/?preview=1",
        'download_url': f"/d/{link.token}/",
    }
    return render(request, 'public/download_page.html', context)

def direct_download_view(request, token):
    """
    Entrega o arquivo binário direto com X-Accel-Redirect.
    Incrementa o contador de cliques de forma atômica.
    """
    ip = get_client_ip(request)

    # 1. Rate limiting contra DDoS em downloads
    is_blocked, _ = check_rate_limit(f"dl:{ip}", max_requests=40, window_seconds=1)
    if is_blocked:
        return HttpResponse("Too Many Requests. Rate limit exceeded.", status=429)

    try:
        link = ShareLink.objects.select_related('file').get(token=token)
    except ShareLink.DoesNotExist:
        is_scan_blocked, _ = check_rate_limit(f"scan:{ip}", max_requests=15, window_seconds=60)
        if is_scan_blocked:
            log_event(
                AuditLog.CATEGORY_ERROR,
                f"Alerta de Segurança: IP {ip} bloqueado temporariamente por varredura de tokens inexistentes.",
                level=AuditLog.LEVEL_ERROR,
                request=request
            )
            return HttpResponse("Too Many Requests. Token scan rate limit exceeded.", status=429)
        return HttpResponseNotFound("Link não encontrado.")

    if not link.is_valid:
        log_event(AuditLog.CATEGORY_ERROR, f"Download rejeitado para token {token}: {link.status_display}", level=AuditLog.LEVEL_WARNING, request=request)
        return render(request, 'public/link_expired.html', {
            'reason': link.status_display,
            'link': link
        }, status=410)

    # Incremento atômico para evitar race condition
    is_preview = request.GET.get('preview') == '1'
    # Só desconta o clique se não for apenas a tag de preview no carregamento da página
    if not is_preview:
        ShareLink.objects.filter(id=link.id).update(
            download_count=F('download_count') + 1,
            last_downloaded_at=timezone.now()
        )
        log_event(AuditLog.CATEGORY_DOWNLOAD, f"Download do arquivo '{link.file.name}' via token {link.token}", request=request)

    stored_file = link.file
    filename = stored_file.name

    # Prevenção contra Stored XSS: apenas mimetypes seguros podem ser exibidos inline
    if is_preview and stored_file.mime_type in SAFE_INLINE_MIMES:
        disposition = "inline"
    else:
        disposition = build_content_disposition(filename)

    use_x_accel = settings.USE_X_ACCEL and (
        request.META.get('HTTP_X_ACCEL_SUPPORTED') == '1' or
        request.META.get('HTTP_X_REAL_IP') is not None
    )

    if use_x_accel:
        response = HttpResponse()
        response['X-Accel-Redirect'] = build_accel_redirect_path(stored_file)
        response['Content-Type'] = stored_file.mime_type
        response['Content-Disposition'] = disposition
        response['X-Content-Type-Options'] = 'nosniff'
        return response

    # Fallback transparente para localhost / desenvolvimento local sem Nginx
    try:
        file_handle = open(stored_file.absolute_path, 'rb')
        response = FileResponse(file_handle, content_type=stored_file.mime_type)
        response['Content-Disposition'] = disposition
        response['X-Content-Type-Options'] = 'nosniff'
        return response
    except Exception as e:
        return HttpResponseNotFound(f"Arquivo não encontrado no disco: {str(e)}")

