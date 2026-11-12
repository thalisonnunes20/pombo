from django.http import JsonResponse, HttpResponse, HttpResponseForbidden, FileResponse
from django.views.decorators.http import require_POST, require_GET
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404
from django.conf import settings
from apps.dashboard.models import log_event, AuditLog
from .models import StoredFile
from .services import scan_storage_directory, save_uploaded_file, delete_stored_file, build_accel_redirect_path, build_content_disposition

@login_required
@require_POST
def upload_file_api(request):
    """Endpoint AJAX para upload de arquivos."""
    if not request.user.can_upload and not request.user.is_superuser:
        return JsonResponse({'success': False, 'error': 'Você não tem permissão para enviar arquivos.'}, status=403)

    files = request.FILES.getlist('files')
    if not files:
        # Tenta pegar arquivo único do campo 'file'
        single_file = request.FILES.get('file')
        if single_file:
            files = [single_file]

    if not files:
        return JsonResponse({'success': False, 'error': 'Nenhum arquivo enviado.'}, status=400)

    uploaded_records = []
    for file_obj in files:
        try:
            stored_file = save_uploaded_file(file_obj)
            log_event(AuditLog.CATEGORY_UPLOAD, f"Arquivo '{stored_file.name}' ({stored_file.formatted_size}) enviado com sucesso", request=request)
            uploaded_records.append({
                'id': stored_file.id,
                'name': stored_file.name,
                'size': stored_file.formatted_size,
                'category': stored_file.file_category,
            })
        except Exception as e:
            log_event(AuditLog.CATEGORY_ERROR, f"Erro no upload de '{file_obj.name}': {str(e)}", level=AuditLog.LEVEL_ERROR, request=request)
            return JsonResponse({'success': False, 'error': f'Erro ao salvar {file_obj.name}: {str(e)}'}, status=500)

    return JsonResponse({'success': True, 'files': uploaded_records})

@login_required
@require_POST
def scan_storage_api(request):
    """Sincroniza os arquivos do sistema de arquivos com o banco de dados."""
    source = request.POST.get('source', StoredFile.SOURCE_UPLOAD)
    if source not in [StoredFile.SOURCE_UPLOAD, StoredFile.SOURCE_EXTERNAL]:
        return JsonResponse({'success': False, 'error': 'Origem inválida.'}, status=400)

    if source == StoredFile.SOURCE_EXTERNAL and not request.user.can_access_external and not request.user.is_superuser:
        return JsonResponse({'success': False, 'error': 'Sem permissão para acessar pasta mapeada.'}, status=403)

    try:
        result = scan_storage_directory(source)
        log_event(AuditLog.CATEGORY_UPLOAD, f"Sincronização ({source}): {result['scanned']} escaneados, {result['created']} novos", request=request)
        return JsonResponse({'success': True, 'result': result})
    except Exception as e:
        log_event(AuditLog.CATEGORY_ERROR, f"Erro ao sincronizar pasta ({source}): {str(e)}", level=AuditLog.LEVEL_ERROR, request=request)
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

@login_required
@require_POST
def delete_file_api(request, file_id):
    """Exclui um arquivo da pasta de uploads."""
    if not request.user.can_delete_files and not request.user.is_superuser:
        return JsonResponse({'success': False, 'error': 'Você não tem permissão para excluir arquivos.'}, status=403)

    stored_file = get_object_or_404(StoredFile, id=file_id)
    if stored_file.source != StoredFile.SOURCE_UPLOAD:
        return JsonResponse({'success': False, 'error': 'Apenas arquivos da pasta de uploads podem ser excluídos.'}, status=400)

    filename = stored_file.name
    success = delete_stored_file(stored_file.id)
    if success:
        log_event(AuditLog.CATEGORY_DELETE, f"Arquivo '{filename}' excluído permanentemente do disco", request=request)
        return JsonResponse({'success': True})
    return JsonResponse({'success': False, 'error': 'Falha ao excluir o arquivo.'}, status=500)

@login_required
@require_GET
def admin_download_file(request, file_id):
    """Permite ao usuário autenticado baixar o arquivo diretamente pelo painel."""
    stored_file = get_object_or_404(StoredFile, id=file_id)

    if stored_file.source == StoredFile.SOURCE_EXTERNAL and not request.user.can_access_external and not request.user.is_superuser:
        return HttpResponseForbidden("Sem permissão para acessar arquivos da pasta mapeada.")

    # Se estiver rodando atrás do Nginx com X-Accel
    use_x_accel = settings.USE_X_ACCEL and (
        request.META.get('HTTP_X_ACCEL_SUPPORTED') == '1' or
        request.META.get('HTTP_X_REAL_IP') is not None
    )

    if use_x_accel:
        response = HttpResponse()
        response['X-Accel-Redirect'] = build_accel_redirect_path(stored_file)
        response['Content-Type'] = stored_file.mime_type
        response['Content-Disposition'] = build_content_disposition(stored_file.name)
        return response

    # Fallback para desenvolvimento local sem Nginx
    return FileResponse(open(stored_file.absolute_path, 'rb'), as_attachment=True, filename=stored_file.name)

