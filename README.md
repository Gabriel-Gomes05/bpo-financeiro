# FLIC — Gestão financeira para BPO

Aplicação web interna para operação financeira de clínicas e consultórios: receitas,
contas a pagar, plano de contas, centros de custo, rateios, importações, conciliação
bancária e de cartões, orçamento, DRE, rotinas e fechamento.

O projeto usa FastAPI, SQLAlchemy, PostgreSQL, Jinja2 e Docker. Foi estruturado como um
monólito simples para facilitar manutenção, implantação e entendimento por desenvolvedores
em início de carreira.

## Estado atual

- Banco PostgreSQL 15 com separação de dados por cliente.
- Campos pessoais e bancários cifrados na aplicação.
- Autenticação por JWT em cookie `HttpOnly`.
- Perfis de coordenador, editor, funcionário, secretária e médico.
- Cadastro de procedimentos e grupos administrativos.
- Lançamentos e contas a pagar com criação, edição, recorrência e importação em lote.
- Modelos de planilha versionados em `static/modelos/` para orientar as importações.
- Auditorias automáticas de banco, ORM, relacionamentos, rotas e criptografia.
- Aplicação local em `http://localhost:8888`.

## Tecnologias

- Python 3.11, FastAPI e Uvicorn;
- SQLAlchemy e PostgreSQL 15;
- Jinja2, HTML, CSS e JavaScript;
- pandas e openpyxl para importações;
- Docker Compose para o ambiente local;
- Ruff e Pytest para qualidade e testes.

## Documentação

| Documento | Quando consultar |
|---|---|
| [Arquitetura](docs/ARQUITETURA.md) | Para entender módulos, banco e fluxo das requisições. |
| [Guia de manutenção](docs/GUIA_MANUTENCAO.md) | Antes de criar ou alterar funcionalidades. |
| [Referência de funções](docs/REFERENCIA_FUNCOES.md) | Para localizar e entender cada função Python. |
| [Segurança e dados](docs/SEGURANCA_E_DADOS.md) | Ao trabalhar com dados pessoais, chaves e produção. |
| [Como contribuir](CONTRIBUTING.md) | Padrões, validação e mensagens de commit. |
| [Manual do usuário](docs/Manual_do_Usuario_FINLUZ.pdf) | Uso operacional das telas. |

## Pré-requisitos

- Docker Desktop instalado e iniciado.
- Git para versionamento.
- Python 3.11 apenas para executar ferramentas fora do Docker, opcional.

Não é necessário instalar PostgreSQL localmente.

## Primeira execução

No PowerShell:

```powershell
git clone https://github.com/Gabriel-Gomes05/bpo-financeiro.git
Set-Location bpo-financeiro
Copy-Item .env.example .env
python scripts/setup_encryption_key.py
```

Edite o `.env` e substitua os placeholders de `DATABASE_URL`, `DB_PASSWORD` e
`SECRET_KEY`. Nunca reutilize a mesma chave para JWT e criptografia de campos.

Depois execute:

```powershell
docker compose up -d --build
curl.exe --max-time 10 -o NUL -w "HTTP=%{http_code}" http://localhost:8888/login
```

O resultado esperado é `HTTP=200`. Acesse:

http://localhost:8888/login

## Variáveis de ambiente

| Variável | Finalidade |
|---|---|
| `DATABASE_URL` | URL SQLAlchemy usada pela aplicação. |
| `DB_PASSWORD` | Senha usada na criação do PostgreSQL pelo Compose. |
| `SECRET_KEY` | Assinatura dos tokens JWT. Mínimo de 32 caracteres. |
| `FIELD_ENCRYPTION_KEY` | Chave Base64 de 64 bytes para os campos cifrados. |
| `APP_ENV` | `development` ou `production`. |
| `DB_SSL_MODE` | Modo TLS do PostgreSQL; produção exige modo seguro. |
| `HTTPS_ONLY` | Obriga cookies seguros em produção. |
| `ALLOWED_ORIGINS` | Origens web autorizadas, separadas por vírgula. |

Veja todos os valores disponíveis em [.env.example](.env.example). O arquivo `.env` real é
ignorado pelo Git.

## Dados de demonstração

Com os contêineres em execução:

```powershell
docker compose exec -T web python seed.py
```

> Atenção: `seed.py` é destrutivo e apaga os dados existentes. Use apenas em desenvolvimento.

Para uma base maior de testes, revise primeiro `app/seed_massivo.py`. Nunca execute seeds em
produção.

## Comandos do dia a dia

```powershell
# Estado dos serviços
docker compose ps

# Logs da aplicação
docker compose logs --tail 100 web

# Reiniciar somente a aplicação
docker compose restart web

# Recriar após mudar dependências ou Dockerfile
docker compose up -d --build --force-recreate web

# Parar sem excluir o volume do banco
docker compose down
```

Não use `docker compose down -v` sem um backup validado: `-v` remove o volume do PostgreSQL.

## Validação antes de publicar

```powershell
python -m pip install -r requirements-dev.txt
ruff check app scripts tests
pytest
python -m compileall app scripts
python scripts/generate_function_reference.py --check

docker compose exec -T web python scripts/audit_connections.py
docker compose exec -T web python scripts/verify_field_encryption.py

curl.exe --max-time 10 -o NUL -w "HTTP=%{http_code}" http://localhost:8888/login
```

O auditor de conexões verifica tabelas, chaves estrangeiras, models, relacionamentos ORM e
as principais telas autenticadas. O verificador de criptografia confirma que não restou
texto legado nos campos protegidos.

## Boas práticas

- Crie uma branch por mudança e mantenha commits pequenos e objetivos.
- Use mensagens de commit no padrão `feat:`, `fix:`, `docs:`, `refactor:` ou `chore:`.
- Preserve o filtro por `cliente_id` em consultas para evitar acesso entre clientes.
- Valide autorização no servidor; controles visuais não substituem essa validação.
- Não registre senhas, tokens, chaves, dados bancários ou conteúdo de documentos nos logs.
- Nunca versione `.env`, uploads, dumps, backups ou dados reais de clientes.
- Atualize testes e documentação junto com mudanças de comportamento.
- Execute Ruff, Pytest, compilação e auditorias antes de publicar.

O fluxo completo para contribuições está em [CONTRIBUTING.md](CONTRIBUTING.md).

## Backup seguro

Crie o dump dentro do contêiner e copie para a pasta ignorada pelo Git:

```powershell
New-Item -ItemType Directory -Force backups | Out-Null
docker compose exec -T db pg_dump -U bpo -d bpo_financeiro -Fc -f /tmp/flic.dump
docker cp bpo-financeiro-db-1:/tmp/flic.dump backups/flic.dump
python scripts/backup_crypto.py encrypt backups/flic.dump backups/flic.dump.enc --delete-source
```

Para preparar uma restauração:

```powershell
python scripts/backup_crypto.py decrypt backups/flic.dump.enc backups/flic.restore.dump
```

Depois valide o arquivo em um banco isolado. Não teste restauração sobre a base ativa.

## Estrutura resumida

```text
bpo-financeiro/
|- app/
|  |- main.py              # inicialização e routers
|  |- config.py            # configurações e validações
|  |- database.py          # conexão, sessão e schema
|  |- models.py            # tabelas e relacionamentos
|  |- field_encryption.py  # criptografia de campos sensíveis
|  |- routers/             # endpoints por funcionalidade
|  |- services/            # regras reutilizáveis
|  `- templates/           # telas Jinja2
|- docs/                   # arquitetura, segurança e manuais
|- scripts/                # auditoria, chaves, backup e documentação
|- static/                 # JavaScript e imagens
|  `- modelos/             # planilhas-modelo sem dados reais
|- tests/                  # testes automatizados
|- docker-compose.yml      # aplicação e PostgreSQL
|- Dockerfile
`- requirements.txt
```

## Fluxos principais

1. Cadastre usuários, clientes, contas bancárias e centros de custo.
2. Lance receitas e despesas, com rateio quando necessário.
3. Importe movimentos bancários e vendas de cartão.
4. Revise e confirme as sugestões de conciliação.
5. Acompanhe orçamento, DRE, rotinas e fechamento.

## Produção

Antes de usar dados reais:

- configure `APP_ENV=production`, HTTPS e TLS do PostgreSQL;
- use banco gerenciado e usuário sem privilégios administrativos;
- armazene chaves em um gerenciador de segredos;
- configure backup automático cifrado e teste de restauração;
- mantenha `FIELD_ENCRYPTION_KEY` fora do repositório e com cópia segura;
- restrinja `ALLOWED_ORIGINS` ao domínio oficial;
- execute as auditorias em cada publicação.

Este repositório é privado. Ainda assim, trate qualquer commit como potencialmente público:
segredos e dados de clientes nunca devem entrar no histórico Git.
