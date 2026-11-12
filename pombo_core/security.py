from django.core.cache import cache
import time

def get_client_ip(request) -> str:
    """
    Obtém o IP real do cliente, considerando proxy reverso Nginx.
    """
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0].strip()
    else:
        ip = request.META.get('HTTP_X_REAL_IP') or request.META.get('REMOTE_ADDR', '127.0.0.1')
    return ip

def check_rate_limit(key: str, max_requests: int, window_seconds: int) -> tuple[bool, int]:
    """
    Verifica se uma chave (ex: IP ou ação) excedeu o limite de requisições.
    Retorna (is_blocked, retry_after_seconds).
    """
    now = int(time.time())
    cache_key = f"ratelimit:{key}"
    history = cache.get(cache_key, [])
    
    # Manter apenas requisições dentro da janela de tempo
    valid_history = [t for t in history if now - t < window_seconds]
    
    if len(valid_history) >= max_requests:
        oldest = valid_history[0]
        retry_after = window_seconds - (now - oldest)
        return True, max(1, retry_after)
    
    valid_history.append(now)
    cache.set(cache_key, valid_history, timeout=window_seconds)
    return False, 0

def check_login_lockout(request, username: str) -> tuple[bool, int]:
    """
    Verifica se o IP ou usuário está temporariamente bloqueado por excesso de tentativas.
    Limite: 5 tentativas falhas em 5 minutos -> Bloqueio de 5 minutos.
    """
    ip = get_client_ip(request)
    lockout_key = f"lockout:{ip}"
    locked_until = cache.get(lockout_key)
    
    now = int(time.time())
    if locked_until and locked_until > now:
        return True, locked_until - now
    
    return False, 0

def record_login_attempt(request, username: str, success: bool) -> tuple[bool, int]:
    """
    Registra tentativa de login. Se atingir 5 falhas consecutivas, ativa o bloqueio temporário.
    """
    ip = get_client_ip(request)
    counter_key = f"login_fails:{ip}"
    lockout_key = f"lockout:{ip}"
    now = int(time.time())

    if success:
        cache.delete(counter_key)
        cache.delete(lockout_key)
        return False, 0

    fails = cache.get(counter_key, 0) + 1
    cache.set(counter_key, fails, timeout=300)

    if fails >= 5:
        lockout_duration = 300 # 5 minutos
        cache.set(lockout_key, now + lockout_duration, timeout=lockout_duration)
        return True, lockout_duration

    return False, 0

