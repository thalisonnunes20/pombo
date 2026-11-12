import os
import mimetypes
from pathlib import Path
from urllib.parse import quote
from django.conf import settings
from django.utils.http import content_disposition_header
from .models import StoredFile

def build_accel_redirect_path(stored_file) -> str:
    """
    Monta o caminho interno do X-Accel-Redirect com percent-encoding.
    Sem isso, nomes contendo '?', '#', '%', espacos ou caracteres nao-ASCII
    (comuns em bibliotecas Jellyfin/Plex) quebram a resolucao no Nginx.
    """
    return f"/_protected/{stored_file.source}/{quote(stored_file.relative_path, safe='/')}"

def build_content_disposition(filename: str, as_attachment: bool = True) -> str:
    """Gera Content-Disposition compativel com RFC 6266 (suporta UTF-8 via filename*)."""
    return content_disposition_header(as_attachment, filename)

def get_base_dir(source: str) -> Path:
    if source == StoredFile.SOURCE_UPLOAD:
        return settings.UPLOAD_STORAGE_DIR.resolve()
    elif source == StoredFile.SOURCE_EXTERNAL:
        return settings.EXTERNAL_STORAGE_DIR.resolve()
    raise ValueError(f"Origem desconhecida: {source}")

def resolve_safe_path(source: str, relative_path: str) -> Path:
    """
    Resolve o caminho no sistema de arquivos garantindo que não há Path Traversal.
    """
    base_dir = get_base_dir(source)
    # Remove barras iniciais e limpa o caminho
    clean_relative = os.path.normpath(relative_path).lstrip('/\\')
    target_path = (base_dir / clean_relative).resolve()

    if not str(target_path).startswith(str(base_dir)):
        raise PermissionError("Acesso negado: tentativa de Path Traversal.")
    
    return target_path

def scan_storage_directory(source: str) -> dict:
    """
    Escaneia os arquivos físicos do diretório e atualiza a base de dados.
    """
    base_dir = get_base_dir(source)
    if not base_dir.exists():
        base_dir.mkdir(parents=True, exist_ok=True)

    found_rel_paths = set()
    created_count = 0
    updated_count = 0

    # followlinks=True permite navegar dentro de symlinks de pastas (comum no Jellyfin/Plex)
    for root, dirs, files in os.walk(base_dir, followlinks=True):
        # Ignora diretórios ocultos
        dirs[:] = [d for d in dirs if not d.startswith('.')]
        for filename in files:
            if filename.startswith('.'):
                continue

            full_path = Path(root) / filename
            try:
                if not full_path.is_file():
                    continue

                rel_path = str(full_path.relative_to(base_dir)).replace('\\', '/')
                found_rel_paths.add(rel_path)

                stat = full_path.stat()
                file_size = stat.st_size
                mime_type, _ = mimetypes.guess_type(str(full_path))
                if not mime_type:
                    mime_type = 'application/octet-stream'

                obj, created = StoredFile.objects.update_or_create(
                    source=source,
                    relative_path=rel_path,
                    defaults={
                        'name': filename,
                        'size': file_size,
                        'mime_type': mime_type,
                    }
                )

                if created:
                    created_count += 1
                else:
                    updated_count += 1
            except Exception:
                continue

    # Remover arquivos do banco que foram excluídos fisicamente do disco
    deleted_count, _ = StoredFile.objects.filter(
        source=source
    ).exclude(
        relative_path__in=found_rel_paths
    ).delete()

    return {
        'source': source,
        'scanned': len(found_rel_paths),
        'created': created_count,
        'updated': updated_count,
        'removed_from_db': deleted_count,
    }

def list_directory_contents(source: str, subfolder: str = "") -> dict:
    """
    Lista pastas e arquivos em tempo real dentro de um subdiretório seguro.
    Garante sincronização automática dos arquivos encontrados com a base de dados.
    """
    base_dir = get_base_dir(source)
    if not base_dir.exists():
        base_dir.mkdir(parents=True, exist_ok=True)

    try:
        target_dir = resolve_safe_path(source, subfolder)
    except PermissionError:
        target_dir = base_dir
        subfolder = ""

    if not target_dir.exists() or not target_dir.is_dir():
        target_dir = base_dir
        subfolder = ""

    current_rel_folder = ""
    if target_dir != base_dir:
        current_rel_folder = str(target_dir.relative_to(base_dir)).replace('\\', '/').strip('/')

    folders = []
    files = []

    try:
        with os.scandir(target_dir) as entries:
            for entry in entries:
                try:
                    name = entry.name
                    if name.startswith('.'):
                        continue

                    if entry.is_dir(follow_symlinks=True):
                        folder_rel = f"{current_rel_folder}/{name}".strip('/') if current_rel_folder else name
                        folders.append({
                            'name': name,
                            'path': folder_rel,
                            'is_dir': True,
                        })
                    elif entry.is_file(follow_symlinks=True):
                        rel_file_path = f"{current_rel_folder}/{name}".strip('/') if current_rel_folder else name
                        stat = entry.stat(follow_symlinks=True)
                        file_size = stat.st_size
                        mime_type, _ = mimetypes.guess_type(name)
                        if not mime_type:
                            mime_type = 'application/octet-stream'

                        stored_file, _ = StoredFile.objects.get_or_create(
                            source=source,
                            relative_path=rel_file_path,
                            defaults={
                                'name': name,
                                'size': file_size,
                                'mime_type': mime_type,
                            }
                        )
                        files.append(stored_file)
                except (PermissionError, OSError):
                    continue
    except (PermissionError, OSError):
        pass

    folders.sort(key=lambda x: x['name'].lower())
    files.sort(key=lambda x: x.name.lower())

    breadcrumbs = []
    if current_rel_folder:
        parts = current_rel_folder.split('/')
        accumulated = []
        for part in parts:
            accumulated.append(part)
            breadcrumbs.append({
                'name': part,
                'path': '/'.join(accumulated),
            })

    parent_folder = None
    if current_rel_folder:
        parent_parts = current_rel_folder.split('/')[:-1]
        parent_folder = '/'.join(parent_parts) if parent_parts else ""

    return {
        'source': source,
        'current_folder': current_rel_folder,
        'parent_folder': parent_folder,
        'breadcrumbs': breadcrumbs,
        'folders': folders,
        'files': files,
    }

def save_uploaded_file(uploaded_file, subfolder: str = "") -> StoredFile:
    """
    Salva com segurança um arquivo enviado via upload.
    """
    base_dir = settings.UPLOAD_STORAGE_DIR.resolve()
    clean_subfolder = os.path.normpath(subfolder).lstrip('/\\') if subfolder else ""
    target_dir = (base_dir / clean_subfolder).resolve()

    if not str(target_dir).startswith(str(base_dir)):
        raise PermissionError("Subpasta inválida.")

    target_dir.mkdir(parents=True, exist_ok=True)

    # Sanitizar o nome do arquivo para evitar caracteres maliciosos
    safe_filename = Path(uploaded_file.name).name
    target_path = target_dir / safe_filename

    # Se já existir arquivo com o mesmo nome, adiciona sufixo numérico
    counter = 1
    stem = Path(safe_filename).stem
    suffix = Path(safe_filename).suffix
    while target_path.exists():
        safe_filename = f"{stem}_{counter}{suffix}"
        target_path = target_dir / safe_filename
        counter += 1

    # Gravar em blocos para suportar arquivos de múltiplos gigabytes sem estourar RAM
    with open(target_path, 'wb+') as destination:
        for chunk in uploaded_file.chunks(chunk_size=1024 * 1024 * 4): # Chunks de 4MB
            destination.write(chunk)

    rel_path = str(target_path.relative_to(base_dir)).replace('\\', '/')
    mime_type, _ = mimetypes.guess_type(str(target_path))
    if not mime_type:
        mime_type = 'application/octet-stream'

    stored_file = StoredFile.objects.create(
        source=StoredFile.SOURCE_UPLOAD,
        name=safe_filename,
        relative_path=rel_path,
        size=target_path.stat().st_size,
        mime_type=mime_type,
    )

    return stored_file

def delete_stored_file(file_id: int) -> bool:
    """
    Exclui um arquivo fisicamente do disco e do banco de dados (libera espaço real em disco).
    """
    try:
        stored_file = StoredFile.objects.get(id=file_id, source=StoredFile.SOURCE_UPLOAD)
        path = stored_file.absolute_path
        if path.exists():
            if path.is_file():
                path.unlink(missing_ok=True)
            elif path.is_dir():
                import shutil
                shutil.rmtree(path, ignore_errors=True)
        stored_file.delete()
        return True
    except (StoredFile.DoesNotExist, Exception):
        return False

