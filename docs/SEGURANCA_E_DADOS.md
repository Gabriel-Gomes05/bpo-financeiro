# Segurança e tratamento de dados

## Segredos

- `.env` é local e nunca deve ser commitado.
- `SECRET_KEY` assina sessões JWT.
- `FIELD_ENCRYPTION_KEY` cifra dados persistidos e deve ser guardada separadamente.
- Senhas de usuário usam bcrypt e não são reversíveis.
- Produção deve armazenar segredos no gerenciador da plataforma, não em arquivos publicados.

## Dados cifrados

PII, identificadores bancários, informações de pacientes, descrições privadas, observações,
dados de cartão e detalhes de auditoria usam criptografia autenticada na aplicação. A lista
canônica está em `SENSITIVE_FIELDS`, em `app/field_encryption.py`.

Valores, datas, status e chaves estrangeiras permanecem tipados para permitir cálculo, filtro,
integridade e relatórios. A proteção desses dados depende também de TLS, controle de acesso,
backup cifrado e criptografia do disco do provedor.

## Publicação

Em produção configure, no mínimo:

```dotenv
APP_ENV=production
HTTPS_ONLY=true
DB_SSL_MODE=verify-full
ALLOWED_ORIGINS=https://seu-dominio.example
```

Use uma senha aleatória de banco com pelo menos 16 caracteres e chaves independentes. Execute
o sistema com usuário PostgreSQL sem privilégios administrativos. O usuário de runtime deve
ter apenas os privilégios necessários nas tabelas e sequências da aplicação.

## Backup

Backups contêm os dados em estado recuperável e são tão sensíveis quanto o banco. Use
`scripts/backup_crypto.py` para cifrar o dump e teste periodicamente a restauração. Guarde a
chave fora do mesmo local do backup.

## Limitações atuais conhecidas

- O isolamento multiempresa é aplicado pela aplicação; ainda não há RLS no PostgreSQL.
- A aplicação ainda executa evolução de schema no startup.
- Rotação automática da chave de campos ainda não foi implementada.
- O ambiente local usa PostgreSQL sem TLS dentro da rede privada do Docker.

Esses pontos são aceitáveis para desenvolvimento local, mas devem entrar no plano de produção.

