from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth import get_user_model
from django.db.models import Sum, Count
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from apps.storage.models import StoredFile
from apps.links.models import ShareLink
from .models import AuditLog, log_event

User = get_user_model()

def format_bytes(num):
    if not num:
        return "0 B"
    num = float(num)
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if abs(num) < 1024.0:
            return f"{num:3.1f} {unit}"
        num /= 1024.0
    return f"{num:.1f} PB"

@login_required
def overview_view(request):
    total_files = StoredFile.objects.count()
    upload_files_count = StoredFile.objects.filter(source=StoredFile.SOURCE_UPLOAD).count()
    external_files_count = StoredFile.objects.filter(source=StoredFile.SOURCE_EXTERNAL).count()
    
    total_bytes = StoredFile.objects.aggregate(total=Sum('size'))['total'] or 0
    total_downloads = ShareLink.objects.aggregate(total=Sum('download_count'))['total'] or 0
    active_links = [l for l in ShareLink.objects.filter(is_active=True) if l.is_valid]

    recent_files = StoredFile.objects.order_by('-created_at')[:8]
    recent_links = ShareLink.objects.select_related('file').order_by('-created_at')[:8]

    context = {
        'total_files': total_files,
        'upload_files_count': upload_files_count,
        'external_files_count': external_files_count,
        'total_storage_formatted': format_bytes(total_bytes),
        'total_downloads': total_downloads,
        'active_links_count': len(active_links),
        'recent_files': recent_files,
        'recent_links': recent_links,
        'current_page': 'overview',
    }
    return render(request, 'dashboard/overview.html', context)

@login_required
def upload_view(request):
    if not request.user.can_upload and not request.user.is_superuser:
        return render(request, 'dashboard/error_permission.html', {
            'message': 'Você não tem permissão para fazer upload de arquivos.'
        }, status=403)

    return render(request, 'dashboard/upload.html', {'current_page': 'upload'})

@login_required
def explorer_view(request):
    source = request.GET.get('source', StoredFile.SOURCE_UPLOAD)
    if source == StoredFile.SOURCE_EXTERNAL and not request.user.can_access_external and not request.user.is_superuser:
        source = StoredFile.SOURCE_UPLOAD

    query = request.GET.get('q', '').strip()
    category = request.GET.get('category', '').strip()

    files = StoredFile.objects.filter(source=source)

    if query:
        files = files.filter(name__icontains=query)

    files = files.order_by('-created_at')

    # Filtro em memória para categorização rápida
    if category:
        files = [f for f in files if f.file_category == category]

    context = {
        'files': files,
        'current_source': source,
        'query': query,
        'current_category': category,
        'can_access_external': request.user.can_access_external or request.user.is_superuser,
        'current_page': 'explorer',
    }
    return render(request, 'dashboard/explorer.html', context)

@login_required
def links_view(request):
    links = ShareLink.objects.select_related('file', 'created_by').order_by('-created_at')
    context = {
        'links': links,
        'current_page': 'links',
    }
    return render(request, 'dashboard/links.html', context)

@login_required
def users_view(request):
    if not request.user.can_manage_users and not request.user.is_superuser:
        return render(request, 'dashboard/error_permission.html', {
            'message': 'Apenas administradores podem gerenciar usuários e permissões.'
        }, status=403)

    users = User.objects.all().order_by('-date_joined')
    context = {
        'users': users,
        'current_page': 'users',
    }
    return render(request, 'dashboard/users.html', context)

@login_required
def logs_view(request):
    if not request.user.can_manage_users and not request.user.is_superuser:
        return render(request, 'dashboard/error_permission.html', {
            'message': 'Apenas administradores podem visualizar os logs de auditoria do sistema.'
        }, status=403)

    category = request.GET.get('cat', '').strip()
    level = request.GET.get('level', '').strip()
    query = request.GET.get('q', '').strip()

    logs_qs = AuditLog.objects.select_related('user').all()

    if category:
        logs_qs = logs_qs.filter(category=category)
    if level:
        logs_qs = logs_qs.filter(level=level)
    if query:
        logs_qs = logs_qs.filter(message__icontains=query)

    logs = logs_qs[:200]

    context = {
        'logs': logs,
        'current_cat': category,
        'current_level': level,
        'query': query,
        'current_page': 'logs',
    }
    return render(request, 'dashboard/logs.html', context)

@login_required
@require_POST
def clear_logs_api(request):
    if not request.user.can_manage_users and not request.user.is_superuser:
        return JsonResponse({'success': False, 'error': 'Permissão negada.'}, status=403)

    count = AuditLog.objects.count()
    AuditLog.objects.all().delete()
    log_event(AuditLog.CATEGORY_DELETE, f"Todos os {count} logs de auditoria foram limpos", request=request)
    return JsonResponse({'success': True, 'cleared_count': count})

