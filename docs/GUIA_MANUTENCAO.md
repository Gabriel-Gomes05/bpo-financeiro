# Guia de manutenção para desenvolvedores

## Por onde começar

1. Leia o `README.md` e suba o Docker.
2. Abra `app/main.py` para enxergar os módulos registrados.
3. Localize a URL em `app/routers/`.
4. Siga os models e services usados pela rota.
5. Localize o template retornado pela função.

A [referência de funções](REFERENCIA_FUNCOES.md) informa arquivo, linha, assinatura, rota e
responsabilidade de cada função Python do projeto.

## Receita para adicionar uma funcionalidade

1. Defina a regra em uma frase e identifique o cliente dono dos dados.
2. Modele os dados em `models.py`, com chave estrangeira e nulabilidade explícitas.
3. Adicione a evolução idempotente em `database.py` quando necessário.
4. Coloque cálculo reutilizável em `services/`.
5. Crie ou altere a rota, validando acesso antes de consultar dados.
6. Atualize o template sem duplicar a regra de negócio.
7. Registre a ação relevante em `LogAuditoria`.
8. Teste sucesso, entrada inválida e tentativa de acessar outro cliente.

## Regras que não podem ser quebradas

- Todo dado financeiro pertence a um `cliente_id`.
- Funcionário opera apenas clientes atribuídos; coordenador possui visão geral.
- Rateios de receita e despesa devem totalizar exatamente 100%.
- Conciliação só é finalizada mediante ação explícita ou regra validada pelo fluxo.
- Campos sensíveis usam `EncryptedText`; não use `String` ou `Text` para novos dados pessoais.
- A chave `FIELD_ENCRYPTION_KEY` nunca deve aparecer em código, log ou commit.
- Uploads precisam passar por `salvar_upload_temporario`.
- Caminhos recebidos do usuário nunca podem ser usados diretamente no sistema de arquivos.

## Criptografia de campos

`app/field_encryption.py` cifra e autentica o conteúdo antes do `INSERT`/`UPDATE` e o decifra
na leitura ORM. O modo aleatório é o padrão. O modo determinístico só é usado quando o sistema
precisa comparar por igualdade, como no login por e-mail.

Consequências práticas:

- `LIKE` e `ILIKE` não funcionam diretamente em campos cifrados;
- ordenação SQL de conteúdo cifrado não representa ordem alfabética;
- busca parcial deve filtrar um conjunto já limitado e autorizado após descriptografar;
- perder a chave significa perder definitivamente o conteúdo;
- trocar a chave exige uma rotina de rotação, nunca apenas substituir o `.env`.

## Diagnóstico rápido

| Sintoma | Verificação |
|---|---|
| Página não abre | `docker compose ps` e `docker compose logs --tail 100 web`. |
| Banco indisponível | Confirme se `db` está `healthy` e revise `DATABASE_URL`. |
| Erro ao descriptografar | Confirme a mesma `FIELD_ENCRYPTION_KEY`; não gere outra. |
| Tela vazia para funcionário | Confira atribuição do cliente e filtros de acesso. |
| DRE divergente | Confira rateios e fallback de categorias antigas. |
| Importação duplicada | Confira identificador externo e conta bancária do arquivo. |
| Template quebra | Execute o parse Jinja e confira variáveis enviadas pelo router. |

## Checklist antes de publicar

- `python -m compileall app scripts`
- `python scripts/generate_function_reference.py --check`
- `docker compose exec -T web python scripts/audit_connections.py`
- `docker compose exec -T web python scripts/verify_field_encryption.py`
- `GET /login` retorna 200
- `.env`, `uploads/` e `backups/` continuam ignorados pelo Git
- variáveis de produção usam senhas fortes, HTTPS e TLS no banco

