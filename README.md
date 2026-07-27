# FLIC — Gestão financeira para BPO

Aplicação web interna para a operação financeira de clínicas e consultórios:
receitas, contas a pagar, centros de custo, rateios, conciliação bancária e de
cartões, orçamento, DRE, rotinas e fechamento.

O sistema usa FastAPI, Jinja2, SQLAlchemy, PostgreSQL, Redis, Alembic e Docker.
O schema aplica isolamento entre clientes, UUIDs públicos, ciclo de vida,
constraints, índices e auditoria.

## Segurança e produção

- Autenticação JWT em cookie `HttpOnly` ou header Bearer, sem token em URL.
- Revogação imediata no logout e rate limiting compartilhado no Redis.
- Limites separados por IP e conta no login.
- CORS por allowlist exata, proteção de origem e headers contra clickjacking.
- Autorização central por perfil e filtros de acesso por cliente.
- Senhas com bcrypt; mensagens de login não enumeram usuários.
- Dados clínicos, bancários e financeiros sensíveis cifrados na aplicação;
  dados cadastrais básicos ficam legíveis para relatórios e integrações.
- Usuários distintos para migrations e runtime; o runtime não pode executar DDL.
- Logs JSON, request ID, `/health`, `/ready` e `/version`.
- Imagem sem reload, sem bind mount, filesystem somente leitura e usuário não-root.

## Primeira execução local

Pré-requisitos: Docker Desktop iniciado e Python 3.11 para gerar o `.env`.

No PowerShell:

```powershell
python scripts/setup_local_env.py
docker compose --profile tools up -d --build
```

O gerador cria apenas as credenciais técnicas e chaves necessárias à
infraestrutura. Para criar o primeiro coordenador, forneça as credenciais
transitoriamente, sem salvá-las no `.env`:

```powershell
$env:BOOTSTRAP_ADMIN_NAME="Administrador FLIC"
$env:BOOTSTRAP_ADMIN_EMAIL="admin@empresa.com.br"
$env:BOOTSTRAP_ADMIN_PASSWORD="defina-uma-senha-forte"
docker compose run --rm --no-deps `
  -e BOOTSTRAP_ADMIN_NAME -e BOOTSTRAP_ADMIN_EMAIL -e BOOTSTRAP_ADMIN_PASSWORD `
  web python scripts/bootstrap_admin.py
Remove-Item Env:BOOTSTRAP_ADMIN_NAME,Env:BOOTSTRAP_ADMIN_EMAIL,Env:BOOTSTRAP_ADMIN_PASSWORD
```

O bootstrap cria somente o primeiro coordenador e não altera um usuário
existente.

Serviços locais:

- Aplicação: http://127.0.0.1:8888/login
- Adminer: http://127.0.0.1:8080
- Prontidão: http://127.0.0.1:8888/ready

No Adminer, use sistema PostgreSQL, servidor `db`, banco `flic` e as credenciais
`APP_DB_USER`/`APP_DB_PASSWORD` do `.env`. Esse usuário permite visualizar e
operar dados, mas não alterar o schema. O Adminer só sobe com o perfil `tools` e
só é publicado no loopback da máquina.

## Migrations

O startup da aplicação não cria nem modifica tabelas. O serviço `migrate`
executa Alembic antes do `web`:

```powershell
docker compose run --rm migrate alembic upgrade head
docker compose run --rm migrate alembic current
```

A migration `0001` cria um banco vazio ou adota tabelas existentes. A `0002`
adiciona colunas de ciclo de vida, UUID, constraints, índices e auditoria de
forma incremental. Constraints `NOT VALID` protegem registros novos sem
bloquear a adoção de dados legados; a validação do legado deve ocorrer antes de
uma migration futura executar `VALIDATE CONSTRAINT`.

## Configuração

Toda configuração está em variáveis de ambiente. Veja [.env.example](.env.example).
As principais são:

| Variável | Finalidade |
|---|---|
| `DATABASE_URL` | Conexão de runtime, sem privilégio de DDL. |
| `MIGRATION_DATABASE_URL` | Conexão usada apenas pelo Alembic. |
| `SECRET_KEY` | Assinatura JWT; mínimo de 64 caracteres aleatórios. |
| `FIELD_ENCRYPTION_KEY` | Chave Base64 de 64 bytes para campos cifrados. |
| `BACKUP_ENCRYPTION_KEY` | Chave independente para backups. |
| `REDIS_URL` | Rate limit e revogação compartilhados. |
| `APP_URL` | URL pública e origem principal da aplicação. |
| `EXTRA_ALLOWED_ORIGINS` | Origens adicionais opcionais, como um Hub externo. |
| `TRUSTED_PROXY_CIDRS` | Redes autorizadas a enviar IP encaminhado. |
| `DB_SSL_MODE` | TLS da conexão PostgreSQL. |
| `DB_ALLOW_INSECURE_PRIVATE` | Exceção explícita para banco na rede Docker privada. |

O `.env` real é ignorado pelo Git. Nunca reutilize chaves entre JWT, campos e
backups.

## Operação

```powershell
# Estado e logs
docker compose --profile tools ps
docker compose logs --tail 100 web

# Rebuild e migration
docker compose build web migrate
docker compose run --rm migrate alembic upgrade head
docker compose up -d --force-recreate web

# Parar sem remover os dados
docker compose down
```

Não execute `docker compose down -v` sem backup validado: `-v` remove os volumes
do PostgreSQL, Redis e uploads.

## Dados demonstrativos

```powershell
$env:SEED_ADMIN_PASSWORD="defina-uma-senha-forte"
$env:SEED_USER_PASSWORD="defina-outra-senha-forte"
docker compose run --rm --no-deps `
  -e SEED_ADMIN_PASSWORD -e SEED_USER_PASSWORD web python seed.py
Remove-Item Env:SEED_ADMIN_PASSWORD,Env:SEED_USER_PASSWORD
```

O seed exige senhas fortes via ambiente e é destrutivo: ele apaga dados
existentes. Use apenas em um banco local descartável. O bootstrap de
administrador não é destrutivo.

## Backup cifrado

```powershell
New-Item -ItemType Directory -Force backups | Out-Null
docker compose exec -T db pg_dump -U flic_migrator -d flic -Fc -f /tmp/flic.dump
docker cp flic-db-1:/tmp/flic.dump backups/flic.dump
python scripts/backup_crypto.py encrypt backups/flic.dump backups/flic.dump.enc --delete-source
```

Restaure primeiro em um banco isolado:

```powershell
python scripts/backup_crypto.py decrypt backups/flic.dump.enc backups/flic.restore.dump
```

O utilitário usa AES-GCM em streaming e uma chave exclusiva de backup.

## Validação

```powershell
python -m compileall app alembic scripts tests
docker compose run --rm --no-deps web sh -c "pip install --target /tmp/testdeps 'pytest>=8,<9' 'httpx2>=2.9,<3' && PYTHONPATH=/tmp/testdeps:/app python -m pytest -q -o cache_dir=/tmp/pytest-cache"
curl.exe http://127.0.0.1:8888/health
curl.exe http://127.0.0.1:8888/ready
curl.exe http://127.0.0.1:8888/version
```

Antes de publicar, execute também `pip-audit` contra `requirements.txt`.

## Proxy HTTPS externo

O HTTPS é terminado pelo Caddy central na VM `192.168.0.250`. A configuração
do Caddy pertence à infraestrutura central e não fica neste repositório.

- use `APP_ENV=production`;
- defina `APP_URL=https://seu-dominio`;
- mantenha `BIND_ADDRESS=0.0.0.0` para testes locais e acesso pela rede;
- mantenha `TRUSTED_PROXY_CIDRS=192.168.0.250/32`;
- permita a porta da aplicação no firewall somente para a VM do Caddy;
- preserve o `.env` operacional durante atualizações;
- não inicie o perfil `tools` em produção.

`APP_ENV=production` ativa automaticamente cookies seguros e HSTS. `APP_URL`
define automaticamente a origem principal aceita; use `EXTRA_ALLOWED_ORIGINS`
apenas quando outro frontend, como o futuro Hub, precisar chamar a aplicação.

Use TLS para PostgreSQL externo. Quando o banco estiver exclusivamente na rede
Docker privada da mesma VM, use `DB_SSL_MODE=disable` somente junto de
`DB_ALLOW_INSECURE_PRIVATE=true`.

Não publique PostgreSQL ou Redis. Como `BIND_ADDRESS=0.0.0.0` aceita conexões
pelas interfaces de rede da VM, a restrição de origem deve ser feita no
firewall.

## Estrutura

```text
Flic/
|- alembic/                # migrations versionadas
|- app/
|  |- config.py           # configuração e validação
|  |- database.py         # engine e sessão de runtime
|  |- models.py           # tabelas e relacionamentos
|  |- authorization.py    # matriz central de permissões
|  |- routers/            # endpoints por módulo
|  |- services/           # regras reutilizáveis
|  `- templates/          # interface Jinja2
|- docker/                # inicialização do PostgreSQL
|- scripts/               # bootstrap, auditoria, backup e chaves
|- tests/                 # regressões funcionais e de segurança
|- docker-compose.yml
|- Dockerfile
`- requirements.txt
```
