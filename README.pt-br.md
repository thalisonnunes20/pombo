# Pombo CDN

[Read in English](README.md)

**Repositório**: [https://github.com/thalisonnunes20/pombo](https://github.com/thalisonnunes20/pombo)  
**Imagem Docker**: `ghcr.io/thalisonnunes20/pombo:latest` (ou `:v0.0.1`)  
**Versão**: `v0.0.1` | **Status**: Pronto para Produção | **Licença**: MIT

O Pombo CDN é um sistema auto-hospedado, leve e de alta performance para distribuição de arquivos, CDN e compartilhamento seguro, empacotado em um contêiner único (*All-in-One* Docker). Desenvolvido para velocidade e simplicidade, combina o poder do Nginx `X-Accel-Redirect` para streaming direto do disco com o Django 5.1, um painel administrativo moderno em tons de cinza escuro neutro, suporte flexível a banco de dados (SQLite nativo com modo WAL ou PostgreSQL/MySQL externo), regras avançadas de expiração de links e sistema completo de logs de auditoria.

---

## Visão Geral da Arquitetura

O Pombo CDN executa todos os serviços essenciais em um único contêiner Docker orquestrado de forma limpa pelo Supervisor:

```
[ Requisição do Usuário ]
          |
          v
[ Nginx (Porta 80) ]
   ├── Arquivos Estáticos (/static/) ──────────> Entregues direto de /app/staticfiles/
   ├── Zonas de Rate Limiting ─────────────────> 30r/m (Login), 40r/s (Downloads), 60r/s (API)
   ├── Cabeçalhos de Segurança & Bloqueio de Dotfiles
   └── Proxy Reverso (Porta 8000)
              |
              v
       [ Gunicorn / Django 5.1 ]
          ├── Autenticação & Permissões de Usuários
          ├── Verificação de Tokens e Expiração de Links
          ├── Bloqueio Anti-Força Bruta em Cache
          ├── Registro em Logs de Auditoria
          └── Resposta: HTTP 200 com "X-Accel-Redirect: /_protected/..."
              |
              v (Transmissão Interna)
[ Motor Nginx X-Accel-Redirect ]
   ├── Lê o arquivo solicitado direto do disco (pipeline sendfile C/C++ do kernel)
   ├── Processa HTTP Range Requests (avanço rápido em áudio e vídeo com HTTP 206)
   └── Transmite o conteúdo para o cliente com consumo de RAM do Python próximo de zero
```

---

## Principais Recursos

- **Contêiner Único (*All-in-One*)**: Nginx, Gunicorn, Django e SQLite orquestrados de forma transparente via Supervisor em uma imagem leve (`python:3.12-slim-bookworm`).
- **Entrega Acelerada Direta do Disco (`X-Accel-Redirect`)**: O Django valida tokens, permissões e contadores em microssegundos; o Nginx entrega o arquivo pesado diretamente do disco via chamada de sistema `sendfile` do kernel. O consumo de memória dos workers Python permanece estável mesmo com arquivos de múltiplos gigabytes.
- **Mapeamento Duplo de Armazenamento**:
  - `storage/uploads`: Pasta local onde novos arquivos enviados pelo painel web são gravados.
  - `storage/external`: Pastas pré-existentes do seu servidor host mapeadas diretamente no contêiner (em modo leitura por padrão) para indexar, explorar e gerar links sem copiar ou duplicar nenhum arquivo.
- **Motor de Links Compartilháveis**:
  - **Links infinitos**: Sem limite de downloads e sem data de expiração.
  - **Limite por contagem de downloads**: O link expira automaticamente após um número definido de downloads (ex: links descartáveis de uso único).
  - **Validade temporal**: O link expira após 1 hora, 24 horas, 7 dias, 30 dias ou em data e hora personalizada.
  - **Regras combinadas**: O link expira assim que o tempo limite for atingido OU a quantidade de downloads for alcançada (o que ocorrer primeiro).
  - **Modos de entrega**: Download binário direto / stream CDN raw (`/d/<token>/`) ou página web de apresentação (`/s/<token>/`) com player de mídia integrado e botão de download.
- **Design Totalmente Responsivo para Celular**:
  - Suporte completo a telas de smartphones e tablets com gaveta lateral de navegação retrátil (*off-canvas*).
  - Barra superior acessível com botão de alternância (hambúrguer).
  - Tabelas responsivas, área de upload (*dropzone*) e modais calibrados para toque em telas móveis.
- **Salvar Login ("Remember Login")**:
  - Opção para manter a sessão ativa por 30 dias via cookie persistente ou expirar ao fechar o navegador.
  - Armazenamento local no navegador para preenchimento automático do nome de usuário.
- **Telas de Carregamento Globais e Localizadas**:
  - Tela de carregamento em tela inteira no primeiro acesso, F5, envio de login, logout e troca de idioma.
  - Indicador de carregamento (*spinner*) localizado dentro do painel para transições suaves e instantâneas entre as abas (Visão Geral, Upload, Explorador, Links, Usuários, Logs).
- **Exclusão Física Real no Disco**:
  - Excluir um arquivo enviado remove-o fisicamente do disco do servidor, liberando espaço real de armazenamento imediatamente.
- **Logs de Auditoria Integrados**:
  - Registro de Criação de Links, Downloads, Uploads, Exclusões, Tentativas de Autenticação e Erros do Sistema.
  - Botão de 1 clique para "Copiar Logs" formatados para a área de transferência e "Limpar Logs" com confirmação segura em modal.
- **Suporte Multilíngue em Tempo Real (EN-US / PT-BR)**:
  - Idioma padrão configurável via `DEFAULT_LANGUAGE=en` ou `DEFAULT_LANGUAGE=pt-br`.
  - Seletor de idioma instantâneo (`EN-US | PT-BR`) na tela de login, no painel administrativo e nas páginas públicas de download.
- **Flexibilidade de Banco de Dados**:
  - Padrão: SQLite nativo armazenado em `/app/data/pombo.sqlite3` com modo Write-Ahead Logging (WAL) ativado para alta concorrência.
  - Externo: Basta definir a variável `DATABASE_URL=postgres://...` ou `DATABASE_URL=mysql://...` para conectar a bancos externos sem alterar código.

---

## Como Instalar e Rodar via Docker

Você pode executar o Pombo CDN de duas formas: baixando a imagem oficial pré-compilada do GitHub Container Registry ou construindo a partir do código-fonte.

### Método 1: Imagem Pré-Compilada Oficial (Mais Rápido - Recomendado)

Não é necessário clonar o repositório nem ter código-fonte. Basta criar um arquivo `docker-compose.yml` em uma pasta qualquer:

```yaml
services:
  pombo:
    image: ghcr.io/thalisonnunes20/pombo:latest
    container_name: pombo
    restart: unless-stopped
    ports:
      - "8080:80"
    environment:
      - SECRET_KEY=pombo-altere-para-um-token-aleatorio-forte-em-producao
      - DEBUG=0
      - ALLOWED_HOSTS=*
      - CSRF_TRUSTED_ORIGINS=http://localhost:8080,http://127.0.0.1:8080
      - ADMIN_USERNAME=admin
      - ADMIN_PASSWORD=adminpassword123
      - ADMIN_EMAIL=admin@pombo.local
      - DEFAULT_LANGUAGE=pt-br
      - USE_X_ACCEL=1
    volumes:
      - ./data:/app/data
      - ./storage/uploads:/app/storage/uploads
      - ./storage/external:/app/storage/external:ro
```

E iniciar o contêiner:

```bash
docker compose up -d
```

#### Ou executar em comando único via `docker run`:

```bash
docker run -d \
  --name pombo \
  -p 8080:80 \
  -e SECRET_KEY="sua-chave-secreta-de-producao" \
  -e ADMIN_USERNAME="admin" \
  -e ADMIN_PASSWORD="adminpassword123" \
  -e DEFAULT_LANGUAGE="pt-br" \
  -v $(pwd)/data:/app/data \
  -v $(pwd)/storage/uploads:/app/storage/uploads \
  -v $(pwd)/storage/external:/app/storage/external:ro \
  --restart unless-stopped \
  ghcr.io/thalisonnunes20/pombo:latest
```

---

### Método 2: Construir a partir do Código-Fonte via Git Clone

Se você deseja inspecionar ou alterar os arquivos do sistema:

```bash
# 1. Clonar o repositório
git clone https://github.com/thalisonnunes20/pombo.git
cd pombo

# 2. Configurar o arquivo de ambiente
cp .env.example .env
# Edite o .env para definir SECRET_KEY, ADMIN_PASSWORD, etc.

# 3. Construir e iniciar o contêiner
docker compose up -d --build
```

---

### Acessar o Painel

Assim que o contêiner estiver em execução, abra o navegador em:
```
http://localhost:8080/
```

- **Usuário Padrão**: `admin` (ou o valor definido em `ADMIN_USERNAME`)
- **Senha Padrão**: `adminpassword123` (ou a senha definida em `ADMIN_PASSWORD`)

---

## Automação de Geração da Imagem Docker (GitHub Actions CI/CD)

O Pombo CDN conta com fluxo automatizado de integração contínua configurado em `.github/workflows/docker-publish.yml`.

A cada commit enviado para a branch `main` ou publicação de tag de versão (`v*`), o GitHub Actions executa automaticamente:
1. Compilação da imagem Docker multicamada.
2. Publicação e versionamento direto no GitHub Container Registry (`ghcr.io/thalisonnunes20/pombo:latest` e `ghcr.io/thalisonnunes20/pombo:v0.0.1`).
3. Suporte a execução manual com 1 clique pela aba "Actions" no GitHub (`workflow_dispatch`).

---

## Tabela de Variáveis de Ambiente

| Variável | Valor Padrão | Valores Permitidos | Descrição |
| :--- | :--- | :--- | :--- |
| `SECRET_KEY` | `pombo-insecure-production-secret-key...` | Qualquer string (mín. 32 chars) | Chave criptográfica secreta do Django. Deve ser única e mantida em sigilo absoluto em produção. |
| `DEBUG` | `0` | `0` (Falso), `1` (Verdadeiro) | Modo de depuração. Mantenha em `0` em produção. Use `1` somente para desenvolvimento local. |
| `ALLOWED_HOSTS` | `*` | Domínios separados por vírgula ou `*` | Nomes de host/domínio aceitos pelo servidor (ex: `cdn.seudominio.com,localhost`). |
| `CSRF_TRUSTED_ORIGINS` | `http://localhost:8080,http://127.0.0.1:8080` | URLs completas separadas por vírgula | URLs completas com protocolo (`http://` ou `https://`) aceitas no envio de formulários. Obrigatório em proxies reversos com SSL. |
| `ADMIN_USERNAME` | `admin` | String alfanumérica | Nome do superadministrador inicial criado automaticamente na primeira inicialização. |
| `ADMIN_PASSWORD` | `adminpassword123` | String (mín. 8 caracteres) | Senha do superadministrador inicial. |
| `ADMIN_EMAIL` | `admin@pombo.local` | E-mail válido | E-mail do superadministrador inicial. |
| `DEFAULT_LANGUAGE` | `en` | `en`, `pt-br` | Idioma padrão da interface do sistema (`en` para Inglês dos EUA, `pt-br` para Português do Brasil). |
| `USE_X_ACCEL` | `1` | `1` (Ativado), `0` (Desativado) | Ativa o streaming direto do Nginx via `X-Accel-Redirect`. Mantenha `1` no Docker. Só use `0` em testes locais sem Nginx. |
| `DATABASE_URL` | *(vazio - usa SQLite nativo)* | `postgres://...`, `mysql://...` | String de conexão com banco de dados externo. Se omitido, o Pombo utiliza SQLite com WAL nativo. |
| `UPLOAD_STORAGE_DIR` | `/app/storage/uploads` | Caminho absoluto no disco | Diretório onde os arquivos enviados via painel web serão gravados no sistema de arquivos. |
| `EXTERNAL_STORAGE_DIR` | `/app/storage/external` | Caminho absoluto no disco | Diretório onde arquivos pré-existentes do host são montados para indexação e compartilhamento. |

---

## Mapeamento de Pastas e Volumes

O arquivo `docker-compose.yml` mapeia três volumes fundamentais:

```yaml
volumes:
  # 1. Banco de Dados e Persistência de Estado:
  - ./data:/app/data

  # 2. Pasta de Arquivos Enviados pelo Painel:
  - ./storage/uploads:/app/storage/uploads

  # 3. Pasta com Arquivos Existentes do Host (Apenas Leitura):
  - /caminho/para/seus/arquivos:/app/storage/external:ro
```

- **`./data:/app/data`**: Armazena o arquivo do banco de dados SQLite (`pombo.sqlite3`) e seus arquivos de diário WAL (`.sqlite3-wal`, `.sqlite3-shm`). Mantém todos os usuários, links, acessos e logs de auditoria intactos mesmo ao recriar contêineres.
- **`./storage/uploads:/app/storage/uploads`**: Armazena todos os uploads realizados pela interface administrativa. Requer permissão de escrita para o usuário `www-data` (UID 33).
- **`./storage/external:/app/storage/external:ro`**: Permite montar qualquer pasta de arquivos já existentes no servidor (fotos, acervos, vídeos, backups). O Pombo indexa e distribui sem duplicar arquivos no disco. O sufixo `:ro` garante que seus arquivos originais fiquem protegidos contra alterações ou deleções acidentais.

---

## Configuração com Proxy Reverso (HTTPS / SSL)

Ao publicar o Pombo CDN atrás de um proxy reverso externo (como Cloudflare, Traefik, Caddy ou Nginx Proxy Manager), certifique-se de repassar os cabeçalhos padrão e configurar o `CSRF_TRUSTED_ORIGINS`:

### Exemplo de Configuração no Nginx do Servidor Host:

```nginx
server {
    listen 443 ssl http2;
    server_name cdn.seudominio.com;

    ssl_certificate /caminho/para/cert.pem;
    ssl_certificate_key /caminho/para/privkey.pem;

    # Permitir uploads de arquivos pesados
    client_max_body_size 0;

    location / {
        proxy_pass http://127.0.0.1:8080;
        proxy_set_header Host $http_host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        proxy_read_timeout 1800s;
        proxy_connect_timeout 60s;
        proxy_send_timeout 1800s;
        proxy_request_buffering off;
    }
}
```

No arquivo `.env`, configure:
```ini
CSRF_TRUSTED_ORIGINS=https://cdn.seudominio.com
ALLOWED_HOSTS=cdn.seudominio.com
```

---

## Arquitetura de Segurança & Blindagem

O Pombo CDN conta com camadas robustas de proteção corporativa:

1. **Rate Limiting Multicamadas**:
   - **Endpoint de Login (`/auth/login/`)**: Limitado no Nginx a `30r/m` com `burst=20 nodelay`.
   - **Bloqueio Anti-Força Bruta In-App**: 5 tentativas consecutivas de senha incorreta bloqueiam o IP de origem por 5 minutos (retorna HTTP 429 e registra a tentativa nos logs de auditoria).
   - **Endpoints de Download & Streaming (`/d/`, `/s/`)**: Limitados no Nginx a `40r/s` com `burst=30 nodelay` para evitar varredura automatizada ou adivinhação de tokens.
   - **API & Uploads (`/storage/api/`)**: Limitados no Nginx a `60r/s` com `burst=50 nodelay`.

2. **Defesa contra Path Traversal**:
   - Todo acesso a arquivos é verificado pela função `resolve_safe_path()`, que garante que o caminho canônico do arquivo no disco reside estritamente dentro das pastas autorizadas. Tentativas de acessar arquivos do sistema via `../` ou symlinks são barradas com HTTP 403.

3. **Proteção contra Stored XSS e MIME Spoofing**:
   - Somente tipos de mídia seguros (`image/jpeg`, `image/png`, `image/webp`, `video/mp4`, `video/webm`, `audio/mpeg`, `application/pdf`) são exibidos inline no navegador.
   - Arquivos potencialmente perigosos ou executáveis (`.html`, `.svg`, `.js`, `.sh`, `.exe`, `.bat`) têm sempre o download forçado como anexo (`Content-Disposition: attachment`) e cabeçalho `X-Content-Type-Options: nosniff` para impedir execução de scripts.

4. **Cabeçalhos HTTP Blindados**:
   - `X-Frame-Options: SAMEORIGIN` (impede clickjacking)
   - `X-Content-Type-Options: nosniff` (impede farejamento de MIME)
   - `X-XSS-Protection: 1; mode=block`
   - `Referrer-Policy: strict-origin-when-cross-origin`
   - `server_tokens off` (oculta a versão do Nginx)
   - Bloqueio direto de arquivos ocultos (`.env`, `.git`) e extensões de código/banco (`.sqlite3`, `.py`, `.sh`, `.log`).

---

## Operação & Manutenção

### Verificando a Saúde do Contêiner

O Pombo CDN inclui um `HEALTHCHECK` interno do Docker testando `http://localhost/health/` a cada 30 segundos:

```bash
docker inspect --format='{{json .State.Health}}' pombo
```

### Visualizando os Logs

```bash
# Ver logs unificados do contêiner (Nginx + Gunicorn + Supervisor)
docker compose logs -f pombo

# Ver apenas os logs da aplicação Django/Gunicorn
docker compose exec pombo supervisorctl tail -f gunicorn

# Ver apenas os logs de acesso e erro do Nginx
docker compose exec pombo supervisorctl tail -f nginx
```

### Criar ou Redefinir Senha de Administrador

```bash
docker compose exec pombo python manage.py initadmin
# ou interativamente:
docker compose exec pombo python manage.py createsuperuser
```

### Procedimento de Backup

Para fazer o backup completo da sua instância do Pombo CDN, basta copiar as pastas `./data` e `./storage/uploads`:

```bash
# Backup consistente do banco de dados SQLite via comando interno:
docker compose exec pombo sqlite3 /app/data/pombo.sqlite3 ".backup /app/data/pombo_backup.sqlite3"
cp data/pombo_backup.sqlite3 /caminho/do/backup/
tar -czvf uploads_backup.tar.gz storage/uploads/
```

---

## Histórico de Versões

### `v0.0.1` (Lançamento Inicial de Produção)
- Contêiner All-in-One com Nginx, Gunicorn, Django 5.1 e Supervisor.
- Pipeline automatizado de compilação via GitHub Actions para o GitHub Container Registry (`ghcr.io/thalisonnunes20/pombo`).
- Motor de entrega acelerada direta do disco via `X-Accel-Redirect`.
- Interface gráfica moderna com tema escuro e navegação responsiva em gaveta para celulares.
- Funcionalidade "Salvar login" com persistência de 30 dias e preenchimento de usuário.
- Rate limiting multicamadas e bloqueio automatizado anti-força bruta.
- Motor completo de expiração de links (por downloads, por tempo ou regras combinadas).
- Painel de auditoria em tempo real com cópia para área de transferência e limpeza segura.
- Alternância de idioma instantânea (`EN-US` / `PT-BR`).
- Suporte a armazenamento duplo (uploads locais e pastas externas mapeadas em modo leitura).
