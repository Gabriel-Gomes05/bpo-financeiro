# FLIC

Sistema web interno para gestão financeira de clínicas e consultórios médicos.

---

## Pré-requisitos

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) instalado e rodando
- Windows, Mac ou Linux

Só isso. Não precisa instalar Python, PostgreSQL nem nada mais.

---

## Como subir o sistema pela primeira vez

```bash
# 1. Entre na pasta do projeto
cd bpo-financeiro

# 2. Copie o arquivo de configuração
cp .env.example .env

# 3. Suba os containers (banco + sistema)
docker-compose up --build
```

Aguarde aparecer a mensagem:
```
FLIC iniciado. Acesse: http://localhost:8888
```

---

## Como acessar

Abra o navegador em: **http://localhost:8888**

---

## Como criar o primeiro usuário coordenador (seed)

Com o sistema rodando, abra outro terminal:

```bash
docker-compose exec web python seed.py
```

Isso cria 4 usuários e 9 clientes de exemplo. Credenciais criadas:

| E-mail               | Senha    | Perfil       |
|----------------------|----------|--------------|
| renato@bpo.com       | admin123 | Coordenador  |
| ana@bpo.com          | 123456   | Funcionário  |
| marcos@bpo.com       | 123456   | Funcionário  |
| julia@bpo.com        | 123456   | Funcionário  |

> **Atenção:** O seed apaga todos os dados existentes antes de recriar. Use só em ambiente de teste.

---

## Como fazer backup do banco

```bash
# Salva um arquivo .sql com todos os dados
docker-compose exec db pg_dump -U bpo bpo_financeiro > backup_$(date +%Y%m%d).sql
```

Para restaurar:

```bash
docker-compose exec -T db psql -U bpo bpo_financeiro < backup_20240101.sql
```

---

## Como adicionar um novo cliente

1. Faça login com uma conta de coordenador
2. Vá em **Admin → Equipe**
3. Clique em **Novo cliente BPO**
4. Preencha nome, especialidade e atribua um funcionário responsável
5. O cliente aparecerá nos painéis do funcionário atribuído

---

## Como atualizar o sistema após mudança de código

Se você alterou algum arquivo Python ou HTML:

```bash
# Para e reinicia só o container web (banco continua rodando)
docker-compose restart web
```

Se adicionou um novo pacote ao `requirements.txt`:

```bash
# Rebuilda a imagem do zero
docker-compose up --build
```

---

## Estrutura de pastas

```
bpo-financeiro/
│
├── app/                        ← Todo o código Python
│   ├── main.py                 ← Ponto de entrada — registra routers e middleware
│   ├── database.py             ← Conexão com o PostgreSQL (SQLAlchemy)
│   ├── models.py               ← Todas as tabelas do banco (ORM)
│   ├── auth.py                 ← Login, JWT, proteção de rotas
│   │
│   ├── routers/                ← Uma rota por funcionalidade
│   │   ├── auth.py             ← GET/POST /login e POST /logout
│   │   ├── dashboard.py        ← GET / (visão geral)
│   │   ├── lancamentos.py      ← Atendimentos (contas a receber)
│   │   ├── conciliacao.py      ← Upload de extratos + matching automático
│   │   ├── contas_pagar.py     ← Despesas e vencimentos
│   │   ├── fechamento.py       ← Fechamento diário por cliente
│   │   ├── rotinas.py          ← Tarefas diárias com checkbox (HTMX)
│   │   └── admin.py            ← Usuários e clientes (só coordenador)
│   │
│   ├── services/               ← Lógica de negócio separada dos routers
│   │   ├── conciliacao_service.py  ← Lê Excel/CSV e pareia com lançamentos
│   │   └── fechamento_service.py   ← Calcula totais e gera texto para cliente
│   │
│   └── templates/              ← HTML com Jinja2
│       ├── base.html           ← Layout base (sidebar + topbar)
│       ├── login.html
│       ├── dashboard.html
│       ├── lancamentos.html
│       ├── conciliacao.html
│       ├── contas_pagar.html
│       ├── fechamento.html
│       ├── rotinas.html
│       └── admin/
│           └── equipe.html
│
├── static/
│   └── app.js                  ← JS mínimo (fechamento de alertas)
│
├── uploads/                    ← Arquivos enviados (documentos, extratos)
├── seed.py                     ← Popula o banco com dados de exemplo
├── docker-compose.yml          ← Define os serviços web + db
├── Dockerfile                  ← Imagem do sistema
├── requirements.txt            ← Pacotes Python
└── .env                        ← Configurações sensíveis (não commitar)
```

---

## Fluxo de trabalho do dia a dia

1. **Lançar atendimentos** → `/lancamentos` — registra consultas e gera parcelas automaticamente
2. **Conciliar** → `/conciliacao` — faz upload do extrato da maquininha e pareia com os lançamentos
3. **Contas a pagar** → `/contas-pagar` — verifica vencimentos e marca como pago
4. **Rotinas** → `/rotinas` — marca as tarefas do dia como concluídas
5. **Fechamento** → `/fechamento` — calcula o dia e gera o texto para enviar ao cliente

---

## Perfis de acesso

| Perfil       | O que pode fazer                                                  |
|--------------|-------------------------------------------------------------------|
| Coordenador  | Tudo + gerenciar usuários e clientes em `/admin/equipe`           |
| Funcionário  | Vê e opera apenas os clientes atribuídos a ele                    |

---

## Dúvidas frequentes

**O sistema não abre no navegador**
→ Verifique se o Docker está rodando: `docker-compose ps`

**Esqueci a senha de um usuário**
→ Acesse como coordenador → Admin → Equipe → crie um novo usuário (não há recuperação de senha ainda)

**Quero acessar de outra máquina na rede**
→ Troque `localhost` pelo IP da máquina onde o Docker está rodando

**Como parar o sistema**
→ `docker-compose down` (banco é preservado no volume `postgres_data`)
