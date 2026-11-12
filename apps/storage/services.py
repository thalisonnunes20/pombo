import os
import mimetypes
from pathlib import Path
from django.conf import settings
from .models import StoredFile

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

    for root, _, files in os.walk(base_dir):
        for filename in files:
            full_path = Path(root) / filename
            if not full_path.is_file():
                continue

            try:
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

