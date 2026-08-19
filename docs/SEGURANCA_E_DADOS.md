# Segurança e tratamento de dados

## Segredos

- `.env` é local e nunca deve ser commitado.
- `SECRET_KEY` assina sessões JWT.
- `FIELD_ENCRYPTION_KEY` cifra dados persistidos e deve ser guardada separadamente.
- Senhas de usuário usam bcrypt e não são reversíveis.
- Produção deve armazenar segredos no gerenciador da plataforma, não em arquivos publicados.

## Classificação dos dados

Dados clínicos de pacientes, contas bancárias, movimentações, cartões,
informações financeiras, observações privadas e detalhes técnicos de auditoria
usam criptografia autenticada na aplicação. A lista canônica está em
`SENSITIVE_FIELDS`, em `app/field_encryption.py`.

Dados cadastrais básicos necessários para relatórios e integrações permanecem
legíveis no PostgreSQL: nome e e-mail de usuário, nome, razão social e CNPJ de
cliente, nome de centro de custo, descrição de rotina e nomes de usuário/cliente
na auditoria. A lista canônica está em `BASIC_PLAINTEXT_FIELDS`.

Essa classificação não torna os campos básicos públicos: eles continuam
protegidos por autenticação, autorização, isolamento entre clientes, TLS,
auditoria e controle de acesso ao banco.

Valores, datas, status e chaves estrangeiras permanecem tipados para permitir cálculo, filtro,
integridade e relatórios. A proteção desses dados depende também de TLS, controle de acesso,
backup cifrado e criptografia do disco do provedor.

## Publicação

Em produção configure, no mínimo:

```dotenv
APP_ENV=production
APP_URL=https://seu-dominio.example
TRUSTED_PROXY_CIDRS=192.168.0.250/32
DB_SSL_MODE=verify-full
```

Em produção, HTTPS, cookies seguros e HSTS são ativados automaticamente por
`APP_ENV`. A origem principal permitida é derivada de `APP_URL`.

`INSECURE_PRIVATE_ORIGINS` permite, excepcionalmente, acesso HTTP a um IP
privado com porta explícita. A aplicação mantém cookies `Secure` no domínio
público e desativa esse atributo apenas quando `Host` e `Origin` correspondem
exatamente à origem privada configurada. Essa exceção deve ser temporária.

Use uma senha aleatória de banco com pelo menos 16 caracteres e chaves independentes. Execute
o sistema com usuário PostgreSQL sem privilégios administrativos. O usuário de runtime deve
ter apenas os privilégios necessários nas tabelas e sequências da aplicação.

## Backup

Backups contêm os dados em estado recuperável e são tão sensíveis quanto o banco. Use
`scripts/backup_crypto.py` para cifrar o dump e teste periodicamente a restauração. Guarde a
chave fora do mesmo local do backup.

## Limitações atuais conhecidas

- O isolamento multiempresa é aplicado pela aplicação; ainda não há RLS no PostgreSQL.
- Constraints compostas impedem novos vínculos inconsistentes entre clientes, mas
  constraints adotadas como `NOT VALID` exigem saneamento e validação posterior do legado.
- Rotação automática da chave de campos ainda não foi implementada.
- O ambiente local usa PostgreSQL sem TLS dentro da rede privada do Docker.

O banco externo de produção deve usar TLS. A exceção sem TLS exige configuração
explícita e só é aceita para host privado da mesma rede Docker.

