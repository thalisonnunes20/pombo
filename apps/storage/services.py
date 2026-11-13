import os
import struct
import time
import zlib
import mimetypes
from pathlib import Path
from urllib.parse import quote
from django.conf import settings
from django.utils.http import content_disposition_header
from .models import StoredFile

def format_size_bytes(num: int) -> str:
    val = float(num or 0)
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if abs(val) < 1024.0:
            return f"{val:3.1f} {unit}"
        val /= 1024.0
    return f"{val:.1f} PB"

def classify_file_category(filename: str, mime_type: str) -> str:
    mime = (mime_type or '').lower()
    ext = Path(filename).suffix.lower()
    if mime.startswith('image/') or ext in ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.svg', '.bmp']:
        return 'image'
    if mime.startswith('video/') or ext in ['.mp4', '.mkv', '.webm', '.mov', '.avi']:
        return 'video'
    if mime.startswith('audio/') or ext in ['.mp3', '.wav', '.ogg', '.flac', '.m4a']:
        return 'audio'
    if ext in ['.zip', '.tar', '.gz', '.bz2', '.7z', '.rar']:
        return 'archive'
    if ext in ['.pdf', '.txt', '.md', '.json', '.csv', '.doc', '.docx']:
        return 'document'
    return 'other'

def build_accel_redirect_path(stored_file) -> str:
    """
    Monta o caminho interno do X-Accel-Redirect com percent-encoding.
    Sem isso, nomes contendo '?', '#', '%', espacos ou caracteres nao-ASCII
    (comuns em bibliotecas Jellyfin/Plex) quebram a resolucao no Nginx.
    """
    return f"/_protected/{stored_file.source}/{quote(stored_file.relative_path, safe='/')}"

def build_accel_redirect_for_relpath(source: str, relative_path: str) -> str:
    """Monta o caminho interno do X-Accel-Redirect para qualquer arquivo relativo à raiz da origem."""
    return f"/_protected/{source}/{quote(relative_path, safe='/')}"

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
        mime_type=StoredFile.MIME_DIRECTORY
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


def get_or_create_folder_record(source: str, folder_path: str = "") -> StoredFile:
    """
    Valida uma pasta física no disco e cria/atualiza seu registro StoredFile (mime_type='inode/directory')
    para permitir a geração de links compartilháveis de pastas inteiras.
    """
    base_dir = get_base_dir(source)
    clean_folder = (folder_path or "").strip()
    if not clean_folder or clean_folder == ".":
        target_dir = base_dir
    else:
        target_dir = resolve_safe_path(source, clean_folder)

    if not target_dir.exists() or not target_dir.is_dir():
        raise FileNotFoundError("Pasta não encontrada no disco.")

    if target_dir == base_dir:
        rel_path = "."
        folder_name = "external" if source == StoredFile.SOURCE_EXTERNAL else "uploads"
    else:
        rel_path = str(target_dir.relative_to(base_dir)).replace('\\', '/').strip('/')
        folder_name = target_dir.name

    # Calcula tamanho total dos arquivos dentro da pasta (com limite de segurança para não travar em NAS gigantes)
    total_size = 0
    counted_files = 0
    max_stat_files = 5000
    try:
        for root, dirs, files in os.walk(target_dir, followlinks=True):
            dirs[:] = [d for d in dirs if not d.startswith('.')]
            for fname in files:
                if fname.startswith('.'):
                    continue
                try:
                    fp = Path(root) / fname
                    if fp.is_file():
                        total_size += fp.stat().st_size
                        counted_files += 1
                        if counted_files >= max_stat_files:
                            break
                except OSError:
                    continue
            if counted_files >= max_stat_files:
                break
    except OSError:
        pass

    folder_obj, _ = StoredFile.objects.update_or_create(
        source=source,
        relative_path=rel_path,
        defaults={
            'name': folder_name,
            'size': total_size,
            'mime_type': StoredFile.MIME_DIRECTORY,
        }
    )
    return folder_obj


def list_shared_folder_contents(folder_file: StoredFile, subpath: str = "") -> dict:
    """
    Lista subpastas e arquivos dentro de uma pasta compartilhada publicamente,
    garantindo isolamento estrito (sandbox) dentro de folder_file.absolute_path.
    """
    folder_root = folder_file.absolute_path.resolve()
    if not folder_root.exists() or not folder_root.is_dir():
        return {
            'current_sub': '',
            'parent_sub': None,
            'breadcrumbs': [],
            'folders': [],
            'files': [],
        }

    clean_sub = (subpath or "").strip().strip('/\\')
    if clean_sub:
        norm_sub = os.path.normpath(clean_sub).lstrip('/\\')
        target_dir = (folder_root / norm_sub).resolve()
        # Garante que target_dir está estritamente dentro da pasta compartilhada
        if not str(target_dir).startswith(str(folder_root)) or not target_dir.exists() or not target_dir.is_dir():
            target_dir = folder_root
    else:
        target_dir = folder_root

    current_sub = ""
    if target_dir != folder_root:
        current_sub = str(target_dir.relative_to(folder_root)).replace('\\', '/').strip('/')

    folders = []
    files = []

    try:
        with os.scandir(target_dir) as entries:
            for entry in entries:
                try:
                    name = entry.name
                    if name.startswith('.'):
                        continue
                    rel_inside_share = f"{current_sub}/{name}".strip('/') if current_sub else name
                    if entry.is_dir(follow_symlinks=True):
                        folders.append({
                            'name': name,
                            'subpath': rel_inside_share,
                        })
                    elif entry.is_file(follow_symlinks=True):
                        stat = entry.stat(follow_symlinks=True)
                        fsize = stat.st_size
                        mime_type, _ = mimetypes.guess_type(name)
                        if not mime_type:
                            mime_type = 'application/octet-stream'
                        files.append({
                            'name': name,
                            'rel_path': rel_inside_share,
                            'size': fsize,
                            'formatted_size': format_size_bytes(fsize),
                            'mime_type': mime_type,
                            'category': classify_file_category(name, mime_type),
                        })
                except (PermissionError, OSError):
                    continue
    except (PermissionError, OSError):
        pass

    folders.sort(key=lambda x: x['name'].lower())
    files.sort(key=lambda x: x['name'].lower())

    breadcrumbs = []
    if current_sub:
        parts = current_sub.split('/')
        acc = []
        for p in parts:
            acc.append(p)
            breadcrumbs.append({
                'name': p,
                'subpath': '/'.join(acc),
            })

    parent_sub = None
    if current_sub:
        parent_parts = current_sub.split('/')[:-1]
        parent_sub = '/'.join(parent_parts) if parent_parts else ""

    return {
        'current_sub': current_sub,
        'parent_sub': parent_sub,
        'breadcrumbs': breadcrumbs,
        'folders': folders,
        'files': files,
    }


def resolve_file_in_shared_folder(folder_file: StoredFile, file_rel_path: str) -> tuple[Path, str, str]:
    """
    Resolve um arquivo individual dentro de uma pasta compartilhada, bloqueando qualquer Path Traversal
    para fora da pasta compartilhada. Retorna (caminho_absoluto, caminho_relativo_na_origem, mime_type).
    """
    if not file_rel_path:
        raise PermissionError("Caminho de arquivo inválido.")

    base_dir = get_base_dir(folder_file.source)
    folder_root = folder_file.absolute_path.resolve()
    clean_rel = os.path.normpath(file_rel_path).lstrip('/\\')
    target_file = (folder_root / clean_rel).resolve()

    # Deve estar estritamente dentro de folder_root e também dentro de base_dir
    folder_root_prefix = str(folder_root) + os.sep if not str(folder_root).endswith(os.sep) else str(folder_root)
    if not str(target_file).startswith(folder_root_prefix) or not str(target_file).startswith(str(base_dir)):
        raise PermissionError("Acesso negado fora da pasta compartilhada.")

    if not target_file.exists() or not target_file.is_file():
        raise FileNotFoundError("Arquivo não encontrado na pasta compartilhada.")

    source_rel_path = str(target_file.relative_to(base_dir)).replace('\\', '/')
    mime_type, _ = mimetypes.guess_type(target_file.name)
    if not mime_type:
        mime_type = 'application/octet-stream'

    return target_file, source_rel_path, mime_type


def stream_folder_as_zip(folder_path: Path):
    """
    Gerador que transmite uma pasta inteira como arquivo .zip em tempo real (streaming),
    sem carregar os arquivos na memória RAM.
    """
    folder_root = folder_path.resolve()
    central_directory = []
    offset = 0

    for root, dirs, files in os.walk(folder_root, followlinks=True):
        dirs[:] = sorted([d for d in dirs if not d.startswith('.')])
        for filename in sorted(files):
            if filename.startswith('.'):
                continue
            full_path = Path(root) / filename
            try:
                if not full_path.is_file():
                    continue
                stat = full_path.stat()
            except OSError:
                continue

            rel_arcname = str(full_path.relative_to(folder_root)).replace('\\', '/')
            arcname_bytes = rel_arcname.encode('utf-8')

            mtime = time.localtime(stat.st_mtime)
            dos_date = ((max(mtime.tm_year, 1980) - 1980) << 9) | (mtime.tm_mon << 5) | mtime.tm_mday
            dos_time = (mtime.tm_hour << 11) | (mtime.tm_min << 5) | (mtime.tm_sec // 2)

            # Bit 3 (0x0008): Data Descriptor; Bit 11 (0x0800): UTF-8 filename
            flags = 0x0808
            method = 8  # ZIP_DEFLATED
            version = 20

            local_header = struct.pack(
                '<4sHHHHHIIIHH',
                b'PK\x03\x04',
                version,
                flags,
                method,
                dos_time,
                dos_date,
                0,
                0,
                0,
                len(arcname_bytes),
                0,
            ) + arcname_bytes

            file_header_offset = offset
            yield local_header
            offset += len(local_header)

            crc = 0
            uncompressed_size = 0
            compressed_size = 0
            compressor = zlib.compressobj(1, zlib.DEFLATED, -15)

            try:
                with open(full_path, 'rb') as fh:
                    while True:
                        chunk = fh.read(512 * 1024)
                        if not chunk:
                            break
                        uncompressed_size += len(chunk)
                        crc = zlib.crc32(chunk, crc)
                        comp_chunk = compressor.compress(chunk)
                        if comp_chunk:
                            compressed_size += len(comp_chunk)
                            offset += len(comp_chunk)
                            yield comp_chunk
                tail = compressor.flush()
                if tail:
                    compressed_size += len(tail)
                    offset += len(tail)
                    yield tail
            except OSError:
                pass

            crc &= 0xffffffff
            data_descriptor = struct.pack('<4sIII', b'PK\x07\x08', crc, compressed_size, uncompressed_size)
            yield data_descriptor
            offset += len(data_descriptor)

            cd_header = struct.pack(
                '<4sHHHHHHIIIHHHHHII',
                b'PK\x01\x02',
                version,
                version,
                flags,
                method,
                dos_time,
                dos_date,
                crc,
                compressed_size & 0xffffffff,
                uncompressed_size & 0xffffffff,
                len(arcname_bytes),
                0,
                0,
                0,
                0,
                0x81A40000,
                file_header_offset & 0xffffffff,
            ) + arcname_bytes
            central_directory.append(cd_header)

    cd_offset = offset
    cd_size = 0
    for cd_entry in central_directory:
        yield cd_entry
        cd_size += len(cd_entry)

    count = len(central_directory)
    eocd = struct.pack(
        '<4sHHHHIIH',
        b'PK\x05\x06',
        0,
        0,
        count & 0xffff,
        count & 0xffff,
        cd_size & 0xffffffff,
        cd_offset & 0xffffffff,
        0,
    )
    yield eocd


