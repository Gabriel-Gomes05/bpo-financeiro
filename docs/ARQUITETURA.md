# Arquitetura do FLIC

## Visão geral

O FLIC é um monólito web simples. FastAPI recebe a requisição, o router valida acesso,
o SQLAlchemy lê ou grava no PostgreSQL e o Jinja renderiza a resposta HTML.

```text
Navegador
   -> middlewares de segurança e autenticação
   -> router da funcionalidade
   -> service/helper de regra de negócio
   -> model SQLAlchemy
   -> PostgreSQL
   -> template Jinja
```

Essa estrutura foi escolhida para manter a operação compreensível por uma equipe pequena.
Não crie microserviços ou camadas abstratas sem uma necessidade concreta.

## Responsabilidade das pastas

| Local | Responsabilidade |
|---|---|
| `app/main.py` | Inicialização, middlewares e registro dos routers. |
| `app/config.py` | Leitura e validação das variáveis de ambiente. |
| `app/database.py` | Engine, sessões e evolução idempotente do schema. |
| `app/models.py` | Tabelas, enums e relacionamentos SQLAlchemy. |
| `app/auth.py` | Senhas, JWT, usuário atual e autorização. |
| `app/security.py` | Headers HTTP, origem e proteções da requisição. |
| `app/routers/` | Entrada HTTP, validação e coordenação de cada fluxo. |
| `app/services/` | Regras reutilizáveis, cálculos, importação e conciliação. |
| `app/templates/` | Interface HTML; não deve decidir regras financeiras. |
| `scripts/` | Auditoria, chaves, backup e documentação automática. |

## Domínio e relacionamentos

`ClienteBPO` é a raiz dos dados multiempresa. Receitas (`Atendimento`), despesas
(`ContaPagar`), bancos, cartões, centros de custo e relatórios apontam para um cliente.

```text
ClienteBPO
 |- Atendimento -> AtendimentoCentroCustoRateio
 |- ContaPagar -> ContaPagarCentroCustoRateio
 |             -> PagamentoParcialContaPagar
 |- ContaBancaria -> MovimentacaoBancaria
 |- VendaCartao -> TransferenciaCartao
 |- CentroCusto
 |- OrcamentoValor
 `- FechamentoDiario
```

Regra essencial: uma operação nunca pode relacionar registros de clientes diferentes.
O banco possui chaves estrangeiras estruturais, mas o isolamento por cliente também depende
dos filtros e validações da aplicação.

## Como uma tela funciona

Exemplo de contas a pagar:

1. `templates/contas_pagar.html` envia o formulário.
2. `routers/contas_pagar.py` valida usuário, cliente e campos.
3. O router cria `ContaPagar` e seus rateios.
4. `db.commit()` confirma a transação.
5. O usuário é redirecionado para a listagem.

Ao alterar esse fluxo, confira as cinco etapas. Modificar apenas o template geralmente cria
uma interface bonita que não aplica a regra no servidor.

## Evolução do banco

O startup executa `criar_tabelas()` e `migrar_schema()`. As alterações de schema são
idempotentes: devem poder rodar mais de uma vez sem perder dados. Antes de uma mudança:

1. faça backup;
2. adicione a alteração em `migrar_schema()`;
3. atualize o model;
4. teste banco vazio e banco já populado;
5. execute `scripts/audit_connections.py`.

No futuro, com mais desenvolvedores ou múltiplos ambientes, recomenda-se migrar esse fluxo
para Alembic, mantendo um histórico versionado de migrations.

