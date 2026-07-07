# Como contribuir

Este projeto prioriza mudanças pequenas, legíveis e fáceis de validar. Leia também
o [guia de manutenção](docs/GUIA_MANUTENCAO.md) e a
[arquitetura](docs/ARQUITETURA.md) antes de alterar regras financeiras.

## Fluxo recomendado

1. Crie uma branch curta: `git switch -c feat/nome-da-mudanca`.
2. Identifique o fluxo completo: template, router, service e model.
3. Evite colocar regra de negócio em HTML ou JavaScript.
4. Preserve o filtro por `cliente_id` em toda consulta multiempresa.
5. Nunca registre ou retorne chaves, senhas ou valores cifrados.
6. Atualize a documentação quando criar função, rota ou variável de ambiente.
7. Execute as validações antes do commit.

```powershell
python -m compileall app scripts
python scripts/generate_function_reference.py --check
docker compose exec -T web python scripts/audit_connections.py
docker compose exec -T web python scripts/verify_field_encryption.py
curl.exe --max-time 10 -o NUL -w "HTTP=%{http_code}" http://localhost:8888/login
```

## Padrões de código

- Nomes de domínio em português; nomes técnicos consagrados podem permanecer em inglês.
- Funções pequenas e com uma responsabilidade.
- Helpers privados começam com `_`.
- Rotas validam entrada e autorização; services concentram cálculos e regras reutilizáveis.
- Transações devem terminar em `commit()` apenas após todas as validações.
- Erros esperados devem produzir mensagem clara; erros inesperados não devem expor detalhes.
- Toda nova função precisa de docstring ou nome suficientemente descritivo para a referência automática.
- Não faça consultas sem escopo de cliente em telas de funcionário.

## Commits

Use mensagens objetivas:

- `feat: adiciona rateio por centro de custo`
- `fix: impede conciliação entre clientes`
- `docs: atualiza guia de implantação`
- `refactor: separa cálculo do fechamento`

Não inclua `.env`, bancos, backups, uploads ou credenciais no Git.

