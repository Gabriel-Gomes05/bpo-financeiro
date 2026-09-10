# Referência de funções

> Arquivo gerado por `python scripts/generate_function_reference.py`.
> Não edite manualmente; melhore nomes/docstrings no código e gere novamente.

Esta referência ajuda o desenvolvedor a localizar responsabilidades. Ela complementa
o código e não substitui a leitura das regras de negócio e validações de acesso.

## `app/auth.py`

Autenticação, sessão JWT e revogação compartilhada.

### `normalizar_email(email: str) -> str`

- Local: [normalizar_email](../app/auth.py#L32)
- Responsabilidade: Função auxiliar que normaliza email.

### `validar_senha_nova(senha: str) -> bool`

- Local: [validar_senha_nova](../app/auth.py#L36)
- Responsabilidade: Função auxiliar que valida senha nova.

### `hash_senha(senha: str) -> str`

- Local: [hash_senha](../app/auth.py#L41)
- Responsabilidade: Função auxiliar responsável pelo fluxo “hash senha”.

### `verificar_senha(senha_plana: str, senha_hash: str) -> bool`

- Local: [verificar_senha](../app/auth.py#L47)
- Responsabilidade: Função auxiliar que verifica senha.

### `verificar_senha_constante(senha_plana: str, senha_hash: str | None) -> bool`

- Local: [verificar_senha_constante](../app/auth.py#L63)
- Responsabilidade: Executa bcrypt mesmo quando o usuário não existe, reduzindo enumeração temporal.

### `criar_token(data: dict, *, auth_version: int=0) -> str`

- Local: [criar_token](../app/auth.py#L71)
- Responsabilidade: Função auxiliar que cria token.

### `decodificar_token(token: str) -> Optional[dict]`

- Local: [decodificar_token](../app/auth.py#L87)
- Responsabilidade: Função auxiliar que decodifica token.

### `get_token_da_requisicao(request: Request) -> Optional[str]`

- Local: [get_token_da_requisicao](../app/auth.py#L104)
- Responsabilidade: Função auxiliar que obtém token da requisicao.

### `_revocation_key(jti: str) -> str`

- Local: [_revocation_key](../app/auth.py#L113)
- Responsabilidade: Função auxiliar responsável pelo fluxo “revocation key”.

### `token_revogado(jti: str) -> bool`

- Local: [token_revogado](../app/auth.py#L117)
- Responsabilidade: Função auxiliar responsável pelo fluxo “token revogado”.

### `token_revogado_async(jti: str) -> bool`

- Local: [token_revogado_async](../app/auth.py#L125)
- Responsabilidade: Função auxiliar responsável pelo fluxo “token revogado async”.

### `revogar_token(payload: dict) -> None`

- Local: [revogar_token](../app/auth.py#L133)
- Responsabilidade: Função auxiliar responsável pelo fluxo “revogar token”.

### `get_usuario_atual(request: Request, db: Session=Depends(get_db)) -> Usuario`

- Local: [get_usuario_atual](../app/auth.py#L141)
- Responsabilidade: Função auxiliar que obtém usuario atual.

### `requer_coordenador(usuario: Usuario=Depends(get_usuario_atual)) -> Usuario`

- Local: [requer_coordenador](../app/auth.py#L176)
- Responsabilidade: Função auxiliar que valida a permissão necessária para coordenador.

### `tem_acesso_geral(usuario: Usuario) -> bool`

- Local: [tem_acesso_geral](../app/auth.py#L182)
- Responsabilidade: Função auxiliar que informa se existe permissão ou condição para acesso geral.

### `__init__(self, app)`

- Local: [AuthMiddleware.__init__](../app/auth.py#L192)
- Responsabilidade: Função auxiliar responsável pelo fluxo “init”.

### `__call__(self, scope, receive, send)`

- Local: [AuthMiddleware.__call__](../app/auth.py#L195)
- Responsabilidade: Função auxiliar responsável pelo fluxo “call”.

## `app/authorization.py`

Matriz central de permissões e dependências de autorização.

### `has_permission(usuario: Usuario, permission: Permission) -> bool`

- Local: [has_permission](../app/authorization.py#L56)
- Responsabilidade: Função auxiliar responsável pelo fluxo “has permission”.

### `require_permission(permission: Permission) -> Callable`

- Local: [require_permission](../app/authorization.py#L60)
- Responsabilidade: Função auxiliar responsável pelo fluxo “require permission”.

### `dependency(usuario: Usuario=Depends(get_usuario_atual)) -> Usuario`

- Local: [require_permission.dependency](../app/authorization.py#L61)
- Responsabilidade: Função auxiliar responsável pelo fluxo “dependency”.

## `app/config.py`

Configuração centralizada e validada da aplicação.

### `_required(name: str) -> str`

- Local: [_required](../app/config.py#L14)
- Responsabilidade: Função auxiliar responsável pelo fluxo “required”.

### `_int(name: str, default: int, *, minimum: int=0, maximum: int | None=None) -> int`

- Local: [_int](../app/config.py#L21)
- Responsabilidade: Função auxiliar responsável pelo fluxo “int”.

### `_bool(name: str, default: bool=False) -> bool`

- Local: [_bool](../app/config.py#L31)
- Responsabilidade: Função auxiliar responsável pelo fluxo “bool”.

### `_csv(name: str) -> list[str]`

- Local: [_csv](../app/config.py#L38)
- Responsabilidade: Função auxiliar responsável pelo fluxo “csv”.

### `_decode_key(name: str, encoded: str) -> bytes`

- Local: [_decode_key](../app/config.py#L113)
- Responsabilidade: Função auxiliar responsável pelo fluxo “decode key”.

### `_validar_origens() -> None`

- Local: [_validar_origens](../app/config.py#L123)
- Responsabilidade: Função auxiliar que valida origens.

### `_validar_configuracao() -> None`

- Local: [_validar_configuracao](../app/config.py#L159)
- Responsabilidade: Função auxiliar que valida configuracao.

## `app/database.py`

### `schema_esta_atualizado(connection) -> bool`

- Local: [schema_esta_atualizado](../app/database.py#L40)
- Responsabilidade: Confere se todas as tabelas e colunas mapeadas existem no banco.

### `_preencher_auditoria(session: Session, _flush_context, _instances) -> None`

- Local: [_preencher_auditoria](../app/database.py#L59)
- Responsabilidade: Propaga ator e request ID para a auditoria de aplicação e banco.

### `get_db()`

- Local: [get_db](../app/database.py#L83)
- Responsabilidade: Dependência do FastAPI — fornece sessão do banco e garante fechamento.

### `criar_tabelas()`

- Local: [criar_tabelas](../app/database.py#L92)
- Responsabilidade: Cria todas as tabelas no banco se ainda não existirem.

### `migrar_schema()`

- Local: [migrar_schema](../app/database.py#L98)
- Responsabilidade: Adiciona colunas novas em tabelas existentes (idempotente).

## `app/errors.py`

Mensagens públicas estáveis para falhas inesperadas.

### `public_import_error(logger: logging.Logger, operation: str) -> str`

- Local: [public_import_error](../app/errors.py#L7)
- Responsabilidade: Função auxiliar responsável pelo fluxo “public import error”.

## `app/field_encryption.py`

Criptografia autenticada para campos sensiveis persistidos pelo SQLAlchemy.

### `_key() -> bytes`

- Local: [_key](../app/field_encryption.py#L80)
- Responsabilidade: Carrega e valida a chave de 64 bytes, mantendo-a em cache no processo.

### `is_encrypted(value: object) -> bool`

- Local: [is_encrypted](../app/field_encryption.py#L97)
- Responsabilidade: Informa se o valor usa o envelope versionado de criptografia do projeto.

### `encrypt_value(value: object, context: str, deterministic: bool=False) -> str | None`

- Local: [encrypt_value](../app/field_encryption.py#L102)
- Responsabilidade: Cifra um valor com contexto autenticado e retorna texto seguro para persistência.

### `decrypt_value(value: object, context: str) -> str | None`

- Local: [decrypt_value](../app/field_encryption.py#L122)
- Responsabilidade: Valida e decifra um valor; aceita plaintext somente para migração de legado.

### `__init__(self, context: str, *, deterministic: bool=False, **kwargs)`

- Local: [EncryptedText.__init__](../app/field_encryption.py#L149)
- Responsabilidade: Configura o contexto da coluna e se ela precisa permitir comparação exata.

### `process_bind_param(self, value, dialect)`

- Local: [EncryptedText.process_bind_param](../app/field_encryption.py#L155)
- Responsabilidade: Cifra valores automaticamente antes de enviá-los ao banco.

### `process_result_value(self, value, dialect)`

- Local: [EncryptedText.process_result_value](../app/field_encryption.py#L159)
- Responsabilidade: Decifra valores automaticamente ao materializar um objeto ORM.

## `app/jinja.py`

Instância única de Jinja2Templates compartilhada por todos os routers. Registra T (strings) e now como globais — disponíveis em qualquer template sem precisar passar como contexto.

### `TemplateResponse(self, *args, **kwargs)`

- Local: [ApplicationTemplates.TemplateResponse](../app/jinja.py#L15)
- Responsabilidade: Função auxiliar responsável pelo fluxo “TemplateResponse”.

### `strftime(self, fmt: str) -> str`

- Local: [_Today.strftime](../app/jinja.py#L33)
- Responsabilidade: Função auxiliar responsável pelo fluxo “strftime”.

### `__bool__(self) -> bool`

- Local: [_Today.__bool__](../app/jinja.py#L35)
- Responsabilidade: Função auxiliar responsável pelo fluxo “bool”.

### `__str__(self) -> str`

- Local: [_Today.__str__](../app/jinja.py#L37)
- Responsabilidade: Função auxiliar responsável pelo fluxo “str”.

## `app/logging_config.py`

Logging JSON estruturado para aplicação e containers.

### `format(self, record: logging.LogRecord) -> str`

- Local: [JsonFormatter.format](../app/logging_config.py#L42)
- Responsabilidade: Função auxiliar responsável pelo fluxo “format”.

### `configure_logging() -> None`

- Local: [configure_logging](../app/logging_config.py#L60)
- Responsabilidade: Função auxiliar responsável pelo fluxo “configure logging”.

### `dispatch(self, request: Request, call_next)`

- Local: [RequestLoggingMiddleware.dispatch](../app/logging_config.py#L71)
- Responsabilidade: Função auxiliar responsável pelo fluxo “dispatch”.

## `app/main.py`

Bootstrap HTTP da aplicação FLIC.

### `lifespan(_: FastAPI)`

- Local: [lifespan](../app/main.py#L47)
- Responsabilidade: Função auxiliar responsável pelo fluxo “lifespan”.

### `manter_empresa_selecionada(request: Request, call_next)`

- Local: [manter_empresa_selecionada](../app/main.py#L83)
- Responsabilidade: Função auxiliar responsável pelo fluxo “manter empresa selecionada”.

### `health()`

- Local: [health](../app/main.py#L121)
- Rota: `GET /health`
- Responsabilidade: Endpoint que executa o fluxo health e devolve a resposta HTTP correspondente.

### `ready()`

- Local: [ready](../app/main.py#L126)
- Rota: `GET /ready`
- Responsabilidade: Endpoint que executa o fluxo ready e devolve a resposta HTTP correspondente.

### `version()`

- Local: [version](../app/main.py#L147)
- Rota: `GET /version`
- Responsabilidade: Endpoint que executa o fluxo version e devolve a resposta HTTP correspondente.

### `_wants_json(request: Request) -> bool`

- Local: [_wants_json](../app/main.py#L155)
- Responsabilidade: Função auxiliar responsável pelo fluxo “wants json”.

### `validation_error_handler(request: Request, _: RequestValidationError)`

- Local: [validation_error_handler](../app/main.py#L160)
- Responsabilidade: Função auxiliar responsável pelo fluxo “validation error handler”.

### `unhandled_error_handler(request: Request, exc: Exception)`

- Local: [unhandled_error_handler](../app/main.py#L184)
- Responsabilidade: Função auxiliar responsável pelo fluxo “unhandled error handler”.

## `app/models.py`

### `created_by(cls)`

- Local: [AuditMixin.created_by](../app/models.py#L121)
- Responsabilidade: Função auxiliar responsável pelo fluxo “created by”.

### `updated_by(cls)`

- Local: [AuditMixin.updated_by](../app/models.py#L125)
- Responsabilidade: Função auxiliar responsável pelo fluxo “updated by”.

### `valor_pago_total(self)`

- Local: [ContaPagar.valor_pago_total](../app/models.py#L320)
- Responsabilidade: Função auxiliar responsável pelo fluxo “valor pago total”.

### `saldo_pendente(self)`

- Local: [ContaPagar.saldo_pendente](../app/models.py#L324)
- Responsabilidade: Função auxiliar responsável pelo fluxo “saldo pendente”.

## `app/rate_limit.py`

Rate limiting distribuído com janela fixa atômica no Redis.

### `opaque_key(value: str) -> str`

- Local: [opaque_key](../app/rate_limit.py#L21)
- Responsabilidade: Função auxiliar responsável pelo fluxo “opaque key”.

### `consume(key: str, limit: int, window_seconds: int) -> tuple[bool, int, int]`

- Local: [consume](../app/rate_limit.py#L29)
- Responsabilidade: Retorna permitido, tentativas restantes e segundos até liberar.

### `inspect_limit(key: str, limit: int) -> tuple[bool, int]`

- Local: [inspect_limit](../app/rate_limit.py#L42)
- Responsabilidade: Consulta um limite sem registrar uma nova tentativa.

### `clear(key: str) -> None`

- Local: [clear](../app/rate_limit.py#L53)
- Responsabilidade: Função auxiliar responsável pelo fluxo “clear”.

## `app/redis_client.py`

Clientes Redis compartilhados por rate limit e revogação.

### `redis_sync() -> redis.Redis`

- Local: [redis_sync](../app/redis_client.py#L13)
- Responsabilidade: Função auxiliar responsável pelo fluxo “redis sync”.

### `redis_async() -> async_redis.Redis`

- Local: [redis_async](../app/redis_client.py#L23)
- Responsabilidade: Função auxiliar responsável pelo fluxo “redis async”.

## `app/routers/admin.py`

### `clientes_do_usuario(db: Session, usuario: Usuario)`

- Local: [clientes_do_usuario](../app/routers/admin.py#L39)
- Responsabilidade: Função auxiliar responsável pelo fluxo “clientes do usuario”.

### `pode_acessar_cliente(db: Session, usuario: Usuario, cliente_id: int) -> bool`

- Local: [pode_acessar_cliente](../app/routers/admin.py#L53)
- Responsabilidade: Função auxiliar responsável pelo fluxo “pode acessar cliente”.

### `_url_retorno_maquininha(cliente_id: int, origem: str | None, maquininha_id: int | None=None) -> str`

- Local: [_url_retorno_maquininha](../app/routers/admin.py#L68)
- Responsabilidade: Monta apenas destinos internos conhecidos após gerenciar uma maquininha.

### `_float_opcional(valor: str | None) -> Optional[float]`

- Local: [_float_opcional](../app/routers/admin.py#L84)
- Responsabilidade: Função auxiliar responsável pelo fluxo “float opcional”.

### `pagina_equipe(usuario: Usuario=Depends(get_usuario_atual))`

- Local: [pagina_equipe](../app/routers/admin.py#L91)
- Rota: `GET /admin/equipe`
- Responsabilidade: Endpoint que renderiza a página de equipe e devolve a resposta HTTP correspondente.

### `pagina_clientes(request: Request, db: Session=Depends(get_db), usuario: Usuario=Depends(get_usuario_atual))`

- Local: [pagina_clientes](../app/routers/admin.py#L98)
- Rota: `GET /admin/clientes`
- Responsabilidade: Endpoint que renderiza a página de clientes e devolve a resposta HTTP correspondente.

### `pagina_grupos(request: Request, db: Session=Depends(get_db), usuario: Usuario=Depends(get_usuario_atual))`

- Local: [pagina_grupos](../app/routers/admin.py#L126)
- Rota: `GET /admin/grupos`
- Responsabilidade: Endpoint que renderiza a página de grupos e devolve a resposta HTTP correspondente.

### `criar_grupo(nome: str=Form(...), db: Session=Depends(get_db), usuario: Usuario=Depends(get_usuario_atual))`

- Local: [criar_grupo](../app/routers/admin.py#L152)
- Rota: `POST /admin/grupos`
- Responsabilidade: Endpoint que cria grupo e devolve a resposta HTTP correspondente.

### `renomear_grupo(grupo_id: int, nome: str=Form(...), funcionario_id: Optional[int]=Form(None), db: Session=Depends(get_db), usuario: Usuario=Depends(get_usuario_atual))`

- Local: [renomear_grupo](../app/routers/admin.py#L172)
- Rota: `POST /admin/grupos/{grupo_id}/renomear`
- Responsabilidade: Endpoint que executa o fluxo renomear grupo e devolve a resposta HTTP correspondente.

### `excluir_grupo(grupo_id: int, db: Session=Depends(get_db), usuario: Usuario=Depends(get_usuario_atual))`

- Local: [excluir_grupo](../app/routers/admin.py#L200)
- Rota: `POST /admin/grupos/{grupo_id}/excluir`
- Responsabilidade: Endpoint que exclui grupo e devolve a resposta HTTP correspondente.

### `pagina_funcionarios(request: Request, db: Session=Depends(get_db), usuario: Usuario=Depends(requer_coordenador))`

- Local: [pagina_funcionarios](../app/routers/admin.py#L218)
- Rota: `GET /admin/funcionarios`
- Responsabilidade: Endpoint que renderiza a página de funcionarios e devolve a resposta HTTP correspondente.

### `pagina_anotacoes_clientes(request: Request, db: Session=Depends(get_db), usuario: Usuario=Depends(get_usuario_atual))`

- Local: [pagina_anotacoes_clientes](../app/routers/admin.py#L233)
- Rota: `GET /admin/anotacoes-clientes`
- Responsabilidade: Endpoint que renderiza a página de anotacoes clientes e devolve a resposta HTTP correspondente.

### `pagina_anotacoes_cliente(cliente_id: int, request: Request, db: Session=Depends(get_db), usuario: Usuario=Depends(get_usuario_atual))`

- Local: [pagina_anotacoes_cliente](../app/routers/admin.py#L247)
- Rota: `GET /admin/anotacoes-clientes/{cliente_id}`
- Responsabilidade: Endpoint que renderiza a página de anotacoes cliente e devolve a resposta HTTP correspondente.

### `criar_anotacao_cliente(cliente_id: int, categoria: str=Form('procedimento'), titulo: str=Form(...), conteudo: str=Form(...), db: Session=Depends(get_db), usuario: Usuario=Depends(get_usuario_atual))`

- Local: [criar_anotacao_cliente](../app/routers/admin.py#L271)
- Rota: `POST /admin/anotacoes-clientes/{cliente_id}/nova`
- Responsabilidade: Endpoint que cria anotacao cliente e devolve a resposta HTTP correspondente.

### `editar_anotacao_cliente(anotacao_id: int, categoria: str=Form('procedimento'), titulo: str=Form(...), conteudo: str=Form(...), db: Session=Depends(get_db), usuario: Usuario=Depends(get_usuario_atual))`

- Local: [editar_anotacao_cliente](../app/routers/admin.py#L300)
- Rota: `POST /admin/anotacoes-clientes/anotacao/{anotacao_id}/editar`
- Responsabilidade: Endpoint que edita anotacao cliente e devolve a resposta HTTP correspondente.

### `excluir_anotacao_cliente(anotacao_id: int, db: Session=Depends(get_db), usuario: Usuario=Depends(get_usuario_atual))`

- Local: [excluir_anotacao_cliente](../app/routers/admin.py#L322)
- Rota: `POST /admin/anotacoes-clientes/anotacao/{anotacao_id}/excluir`
- Responsabilidade: Endpoint que exclui anotacao cliente e devolve a resposta HTTP correspondente.

### `criar_usuario(nome: str=Form(...), email: str=Form(...), senha: str=Form(...), perfil: str=Form('funcionario'), db: Session=Depends(get_db), _: Usuario=Depends(requer_coordenador))`

- Local: [criar_usuario](../app/routers/admin.py#L340)
- Rota: `POST /admin/equipe/usuario`
- Responsabilidade: Endpoint que cria usuario e devolve a resposta HTTP correspondente.

### `editar_usuario(usuario_id: int, nome: str=Form(...), email: str=Form(...), perfil: str=Form(...), senha: Optional[str]=Form(None), db: Session=Depends(get_db), coordenador: Usuario=Depends(requer_coordenador))`

- Local: [editar_usuario](../app/routers/admin.py#L376)
- Rota: `POST /admin/funcionarios/usuario/{usuario_id}/editar`
- Responsabilidade: Endpoint que edita usuario e devolve a resposta HTTP correspondente.

### `excluir_usuario(usuario_id: int, db: Session=Depends(get_db), coordenador: Usuario=Depends(requer_coordenador))`

- Local: [excluir_usuario](../app/routers/admin.py#L420)
- Rota: `POST /admin/funcionarios/usuario/{usuario_id}/excluir`
- Responsabilidade: Endpoint que exclui usuario e devolve a resposta HTTP correspondente.

### `toggle_usuario(usuario_id: int, db: Session=Depends(get_db), coordenador: Usuario=Depends(requer_coordenador))`

- Local: [toggle_usuario](../app/routers/admin.py#L447)
- Rota: `POST /admin/equipe/usuario/{usuario_id}/toggle`
- Responsabilidade: Endpoint que alterna o estado de usuario e devolve a resposta HTTP correspondente.

### `criar_cliente(nome: str=Form(...), razao_social: Optional[str]=Form(None), cnpj: Optional[str]=Form(None), especialidade: Optional[str]=Form(None), tem_maquininha: str=Form('nao'), rede_maquininha: Optional[str]=Form(None), antecipa: str=Form('nao'), bandeira: List[str]=Form(default=[]), taxa_percentual: List[str]=Form(default=[]), funcionario_id: Optional[int]=Form(None), grupo_empresarial_id: Optional[int]=Form(None), db: Session=Depends(get_db), usuario: Usuario=Depends(get_usuario_atual))`

- Local: [criar_cliente](../app/routers/admin.py#L469)
- Rota: `POST /admin/equipe/cliente`
- Responsabilidade: Endpoint que cria cliente e devolve a resposta HTTP correspondente.

### `atribuir_cliente(cliente_id: int, funcionario_id: Optional[int]=Form(None), db: Session=Depends(get_db), _: Usuario=Depends(requer_coordenador))`

- Local: [atribuir_cliente](../app/routers/admin.py#L520)
- Rota: `POST /admin/equipe/cliente/{cliente_id}/atribuir`
- Responsabilidade: Endpoint que executa o fluxo atribuir cliente e devolve a resposta HTTP correspondente.

### `atualizar_cliente(cliente_id: int, razao_social: Optional[str]=Form(None), cnpj: Optional[str]=Form(None), especialidade: Optional[str]=Form(None), tem_maquininha: str=Form('nao'), rede_maquininha: Optional[str]=Form(None), antecipa: str=Form('nao'), db: Session=Depends(get_db), usuario: Usuario=Depends(get_usuario_atual))`

- Local: [atualizar_cliente](../app/routers/admin.py#L534)
- Rota: `POST /admin/clientes/cliente/{cliente_id}/atualizar`
- Responsabilidade: Endpoint que atualiza cliente e devolve a resposta HTTP correspondente.

### `pagina_editar_cliente(cliente_id: int, request: Request, db: Session=Depends(get_db), usuario: Usuario=Depends(get_usuario_atual))`

- Local: [pagina_editar_cliente](../app/routers/admin.py#L559)
- Rota: `GET /admin/clientes/cliente/{cliente_id}/editar`
- Responsabilidade: Endpoint que renderiza a página de editar cliente e devolve a resposta HTTP correspondente.

### `editar_cliente_completo(cliente_id: int, nome: str=Form(...), razao_social: Optional[str]=Form(None), cnpj: Optional[str]=Form(None), especialidade: Optional[str]=Form(None), regime_tributario: Optional[str]=Form(None), banco: Optional[str]=Form(None), agencia: Optional[str]=Form(None), conta: Optional[str]=Form(None), tem_maquininha: str=Form('nao'), rede_maquininha: Optional[str]=Form(None), antecipa: str=Form('nao'), funcionario_id: Optional[int]=Form(None), grupo_empresarial_id: Optional[int]=Form(None), db: Session=Depends(get_db), usuario: Usuario=Depends(get_usuario_atual))`

- Local: [editar_cliente_completo](../app/routers/admin.py#L591)
- Rota: `POST /admin/clientes/cliente/{cliente_id}/editar`
- Responsabilidade: Endpoint que edita cliente completo e devolve a resposta HTTP correspondente.

### `excluir_cliente(cliente_id: int, db: Session=Depends(get_db), usuario: Usuario=Depends(requer_coordenador))`

- Local: [excluir_cliente](../app/routers/admin.py#L662)
- Rota: `POST /admin/clientes/cliente/{cliente_id}/excluir`
- Responsabilidade: Endpoint que exclui cliente e devolve a resposta HTTP correspondente.

### `pagina_taxas_cartao(request: Request, cliente_id: Optional[int]=None, maquininha_id: Optional[int]=None, db: Session=Depends(get_db), usuario: Usuario=Depends(get_usuario_atual))`

- Local: [pagina_taxas_cartao](../app/routers/admin.py#L700)
- Rota: `GET /admin/taxas-cartao`
- Responsabilidade: Endpoint que renderiza a página de taxas cartao e devolve a resposta HTTP correspondente.

### `criar_taxa(cliente_id: int=Form(...), maquininha_id: Optional[int]=Form(None), bandeira: str=Form(...), faixa_parcelamento: str=Form('avista_credito'), parcela_inicial: Optional[int]=Form(None), parcela_final: Optional[int]=Form(None), taxa_percentual: float=Form(...), db: Session=Depends(get_db), usuario: Usuario=Depends(get_usuario_atual))`

- Local: [criar_taxa](../app/routers/admin.py#L759)
- Rota: `POST /admin/taxas-cartao`
- Responsabilidade: Endpoint que cria taxa e devolve a resposta HTTP correspondente.

### `excluir_taxa(taxa_id: int, cliente_id: int=Form(...), maquininha_id: Optional[int]=Form(None), db: Session=Depends(get_db), _: Usuario=Depends(requer_coordenador))`

- Local: [excluir_taxa](../app/routers/admin.py#L841)
- Rota: `POST /admin/taxas-cartao/{taxa_id}/excluir`
- Responsabilidade: Endpoint que exclui taxa e devolve a resposta HTTP correspondente.

### `adicionar_maquininha(cliente_id: int, rede: str=Form(...), apelido: Optional[str]=Form(None), antecipa: str=Form('nao'), origem: Optional[str]=Form(None), db: Session=Depends(get_db), usuario: Usuario=Depends(get_usuario_atual))`

- Local: [adicionar_maquininha](../app/routers/admin.py#L863)
- Rota: `POST /admin/clientes/cliente/{cliente_id}/maquininha/adicionar`
- Responsabilidade: Endpoint que adiciona maquininha e devolve a resposta HTTP correspondente.

### `editar_maquininha(maquininha_id: int, rede: str=Form(...), apelido: Optional[str]=Form(None), antecipa: str=Form('nao'), origem: Optional[str]=Form(None), db: Session=Depends(get_db), usuario: Usuario=Depends(get_usuario_atual))`

- Local: [editar_maquininha](../app/routers/admin.py#L912)
- Rota: `POST /admin/maquininha/{maquininha_id}/editar`
- Responsabilidade: Endpoint que edita maquininha e devolve a resposta HTTP correspondente.

### `toggle_antecipa_cliente(cliente_id: int=Form(...), db: Session=Depends(get_db), usuario: Usuario=Depends(get_usuario_atual))`

- Local: [toggle_antecipa_cliente](../app/routers/admin.py#L949)
- Rota: `POST /admin/taxas-cartao/toggle-antecipa`
- Responsabilidade: Endpoint que alterna o estado de antecipa cliente e devolve a resposta HTTP correspondente.

### `criar_taxa_antecipacao(cliente_id: int=Form(...), bandeira: str=Form(...), descricao: str=Form(...), taxa_percentual: float=Form(...), db: Session=Depends(get_db), usuario: Usuario=Depends(get_usuario_atual))`

- Local: [criar_taxa_antecipacao](../app/routers/admin.py#L968)
- Rota: `POST /admin/taxas-antecipacao`
- Responsabilidade: Endpoint que cria taxa antecipacao e devolve a resposta HTTP correspondente.

### `selecionar_taxa_antecipacao(taxa_id: int, cliente_id: int=Form(...), db: Session=Depends(get_db), usuario: Usuario=Depends(get_usuario_atual))`

- Local: [selecionar_taxa_antecipacao](../app/routers/admin.py#L996)
- Rota: `POST /admin/taxas-antecipacao/{taxa_id}/selecionar`
- Responsabilidade: Endpoint que seleciona taxa antecipacao e devolve a resposta HTTP correspondente.

### `toggle_ativo_antecipacao(taxa_id: int, cliente_id: int=Form(...), db: Session=Depends(get_db), usuario: Usuario=Depends(get_usuario_atual))`

- Local: [toggle_ativo_antecipacao](../app/routers/admin.py#L1021)
- Rota: `POST /admin/taxas-antecipacao/{taxa_id}/toggle-ativo`
- Responsabilidade: Endpoint que alterna o estado de ativo antecipacao e devolve a resposta HTTP correspondente.

### `excluir_taxa_antecipacao(taxa_id: int, cliente_id: int=Form(...), db: Session=Depends(get_db), _: Usuario=Depends(requer_coordenador))`

- Local: [excluir_taxa_antecipacao](../app/routers/admin.py#L1042)
- Rota: `POST /admin/taxas-antecipacao/{taxa_id}/excluir`
- Responsabilidade: Endpoint que exclui taxa antecipacao e devolve a resposta HTTP correspondente.

### `pagina_centros_custo(request: Request, cliente_id: int, db: Session=Depends(get_db), usuario: Usuario=Depends(get_usuario_atual))`

- Local: [pagina_centros_custo](../app/routers/admin.py#L1059)
- Rota: `GET /admin/centros-custo`
- Responsabilidade: Endpoint que renderiza a página de centros custo e devolve a resposta HTTP correspondente.

### `criar_centro_custo(cliente_id: int=Form(...), codigo: str=Form(...), nome: str=Form(...), is_medico: bool=Form(False), especialidade: Optional[str]=Form(None), db: Session=Depends(get_db), usuario: Usuario=Depends(get_usuario_atual))`

- Local: [criar_centro_custo](../app/routers/admin.py#L1081)
- Rota: `POST /admin/centros-custo`
- Responsabilidade: Endpoint que cria centro custo e devolve a resposta HTTP correspondente.

### `excluir_centro_custo(cc_id: int, db: Session=Depends(get_db), usuario: Usuario=Depends(get_usuario_atual))`

- Local: [excluir_centro_custo](../app/routers/admin.py#L1105)
- Rota: `POST /admin/centros-custo/{cc_id}/excluir`
- Responsabilidade: Endpoint que exclui centro custo e devolve a resposta HTTP correspondente.

### `editar_centro_custo(cc_id: int, is_medico: bool=Form(False), especialidade: Optional[str]=Form(None), db: Session=Depends(get_db), usuario: Usuario=Depends(get_usuario_atual))`

- Local: [editar_centro_custo](../app/routers/admin.py#L1119)
- Rota: `POST /admin/centros-custo/{cc_id}/editar`
- Responsabilidade: Endpoint que edita centro custo e devolve a resposta HTTP correspondente.

### `remover_maquininha(maquininha_id: int, origem: Optional[str]=Form(None), db: Session=Depends(get_db), usuario: Usuario=Depends(get_usuario_atual))`

- Local: [remover_maquininha](../app/routers/admin.py#L1136)
- Rota: `POST /admin/maquininha/{maquininha_id}/remover`
- Responsabilidade: Endpoint que executa o fluxo remover maquininha e devolve a resposta HTTP correspondente.

## `app/routers/auth.py`

### `pagina_login(request: Request)`

- Local: [pagina_login](../app/routers/auth.py#L36)
- Rota: `GET /login`
- Responsabilidade: Endpoint que renderiza a página de login e devolve a resposta HTTP correspondente.

### `fazer_login(request: Request, email: str=Form(..., max_length=320), senha: str=Form(..., max_length=256), db: Session=Depends(get_db))`

- Local: [fazer_login](../app/routers/auth.py#L41)
- Rota: `POST /login`
- Responsabilidade: Endpoint que executa login e devolve a resposta HTTP correspondente.

### `pagina_inicio(request: Request, usuario: Usuario=Depends(get_usuario_atual))`

- Local: [pagina_inicio](../app/routers/auth.py#L135)
- Rota: `GET /inicio`
- Responsabilidade: Endpoint que renderiza a página de inicio e devolve a resposta HTTP correspondente.

### `logout(request: Request, db: Session=Depends(get_db), usuario: Usuario=Depends(get_usuario_atual))`

- Local: [logout](../app/routers/auth.py#L145)
- Rota: `POST /logout`
- Responsabilidade: Endpoint que executa o fluxo logout e devolve a resposta HTTP correspondente.

## `app/routers/cliente_ativo.py`

### `painel_geral(request: Request, db: Session=Depends(get_db), usuario: Usuario=Depends(get_usuario_atual))`

- Local: [painel_geral](../app/routers/cliente_ativo.py#L18)
- Rota: `GET /painel`
- Responsabilidade: Endpoint que executa o fluxo painel geral e devolve a resposta HTTP correspondente.

### `selecionar_cliente(request: Request, cliente_id: Optional[str]=Form(None), db: Session=Depends(get_db), usuario: Usuario=Depends(get_usuario_atual))`

- Local: [selecionar_cliente](../app/routers/cliente_ativo.py#L37)
- Rota: `POST /cliente/selecionar`
- Responsabilidade: Endpoint que seleciona cliente e devolve a resposta HTTP correspondente.

## `app/routers/conciliacao.py`

### `clientes_do_usuario(db: Session, usuario: Usuario)`

- Local: [clientes_do_usuario](../app/routers/conciliacao.py#L56)
- Responsabilidade: Função auxiliar responsável pelo fluxo “clientes do usuario”.

### `_carregar_vendas_a_conciliar(db: Session, cliente_id: int)`

- Local: [_carregar_vendas_a_conciliar](../app/routers/conciliacao.py#L65)
- Responsabilidade: Vendas pendentes (sem atendimento vinculado).

### `_carregar_vendas_conciliadas(db: Session, cliente_id: int)`

- Local: [_carregar_vendas_conciliadas](../app/routers/conciliacao.py#L78)
- Responsabilidade: Vendas já conciliadas com atendimento mas ainda não fechadas em lote.

### `_carregar_atendimentos_pendentes(db: Session, cliente_id: int)`

- Local: [_carregar_atendimentos_pendentes](../app/routers/conciliacao.py#L91)
- Responsabilidade: Função auxiliar que carrega atendimentos pendentes.

### `_buscar_atendimentos(db: Session, cliente_id: int, venda: VendaCartao, termo: str | None)`

- Local: [_buscar_atendimentos](../app/routers/conciliacao.py#L107)
- Responsabilidade: Função auxiliar que busca atendimentos.

### `_montar_painel(db, cliente_id, vendas, atendimentos, busca_venda_id=None, busca_termo=None)`

- Local: [_montar_painel](../app/routers/conciliacao.py#L126)
- Responsabilidade: Função auxiliar que monta painel.

### `_agrupar_conciliadas(vendas_conciliadas: list) -> list`

- Local: [_agrupar_conciliadas](../app/routers/conciliacao.py#L162)
- Responsabilidade: Função auxiliar responsável pelo fluxo “agrupar conciliadas”.

### `_carregar_lotes_recentes(db: Session, cliente_id: int)`

- Local: [_carregar_lotes_recentes](../app/routers/conciliacao.py#L183)
- Responsabilidade: Função auxiliar que carrega lotes recentes.

### `_ctx(db, usuario, cliente_id, busca_venda_id=None, busca_termo=None)`

- Local: [_ctx](../app/routers/conciliacao.py#L193)
- Responsabilidade: Função auxiliar responsável pelo fluxo “ctx”.

### `pagina_conciliacao_cartao(request: Request, cliente_id: Optional[int]=None, buscar_venda: Optional[int]=Query(default=None), termo: Optional[str]=Query(default=None), db: Session=Depends(get_db), usuario: Usuario=Depends(require_conciliacao))`

- Local: [pagina_conciliacao_cartao](../app/routers/conciliacao.py#L216)
- Rota: `GET /conciliacao`
- Responsabilidade: Endpoint que renderiza a página de conciliacao cartao e devolve a resposta HTTP correspondente.

### `importar_extrato_maquininha(request: Request, cliente_id: int=Form(...), arquivo: UploadFile=File(...), db: Session=Depends(get_db), usuario: Usuario=Depends(require_conciliacao))`

- Local: [importar_extrato_maquininha](../app/routers/conciliacao.py#L238)
- Rota: `POST /conciliacao/importar`
- Responsabilidade: Endpoint que importa extrato maquininha e devolve a resposta HTTP correspondente.

### `conciliar_todos_prontos(cliente_id: int=Form(...), db: Session=Depends(get_db), usuario: Usuario=Depends(require_conciliacao))`

- Local: [conciliar_todos_prontos](../app/routers/conciliacao.py#L284)
- Rota: `POST /conciliacao/conciliar-todos-prontos`
- Responsabilidade: Endpoint que concilia todos prontos e devolve a resposta HTTP correspondente.

### `_aplicar_conciliacao(db: Session, venda: VendaCartao, at: Atendimento)`

- Local: [_aplicar_conciliacao](../app/routers/conciliacao.py#L300)
- Responsabilidade: Função auxiliar que aplica conciliacao.

### `_conciliar_vendas_prontas(db: Session, cliente_id: int, usuario: Usuario | None=None) -> int`

- Local: [_conciliar_vendas_prontas](../app/routers/conciliacao.py#L313)
- Responsabilidade: Função auxiliar que concilia vendas prontas.

### `_conciliar_pix_ted_prontos(db: Session, cliente_id: int, usuario: Usuario | None=None) -> int`

- Local: [_conciliar_pix_ted_prontos](../app/routers/conciliacao.py#L337)
- Responsabilidade: Função auxiliar que concilia pix ted prontos.

### `conciliar_venda(venda_id: int, cliente_id: int=Form(...), atendimento_id: int=Form(...), origem: str=Form('sugestao'), db: Session=Depends(get_db), usuario: Usuario=Depends(require_conciliacao))`

- Local: [conciliar_venda](../app/routers/conciliacao.py#L395)
- Rota: `POST /conciliacao/venda/{venda_id}/conciliar`
- Responsabilidade: Endpoint que concilia venda e devolve a resposta HTTP correspondente.

### `editar_venda(venda_id: int, cliente_id: int=Form(...), atendimento_id: Optional[int]=Form(default=None), valor_bruto: str=Form(...), taxa_percentual: str=Form(''), valor_liquido: str=Form(...), at_valor_servico: str=Form(...), at_taxa_cartao: str=Form(''), at_valor_liquido: str=Form(...), db: Session=Depends(get_db), usuario: Usuario=Depends(require_conciliacao))`

- Local: [editar_venda](../app/routers/conciliacao.py#L422)
- Rota: `POST /conciliacao/venda/{venda_id}/editar`
- Responsabilidade: Endpoint que edita venda e devolve a resposta HTTP correspondente.

### `reabrir_lote(lote_id: int, cliente_id: int=Form(...), db: Session=Depends(get_db), usuario: Usuario=Depends(require_conciliacao))`

- Local: [reabrir_lote](../app/routers/conciliacao.py#L475)
- Rota: `POST /conciliacao/lote/{lote_id}/reabrir`
- Responsabilidade: Endpoint que executa o fluxo reabrir lote e devolve a resposta HTTP correspondente.

### `desvincular_venda(venda_id: int, cliente_id: int=Form(...), db: Session=Depends(get_db), usuario: Usuario=Depends(require_conciliacao))`

- Local: [desvincular_venda](../app/routers/conciliacao.py#L508)
- Rota: `POST /conciliacao/venda/{venda_id}/desvincular`
- Responsabilidade: Endpoint que executa o fluxo desvincular venda e devolve a resposta HTTP correspondente.

### `criar_e_conciliar_venda(venda_id: int, cliente_id: int=Form(...), data_atendimento: str=Form(...), nome_paciente: str=Form(''), cpf_paciente: str=Form(''), medico: str=Form(''), especialidade: str=Form(''), tipo_servico: str=Form(''), descricao_servico: str=Form(''), observacao: str=Form(''), db: Session=Depends(get_db), usuario: Usuario=Depends(require_conciliacao))`

- Local: [criar_e_conciliar_venda](../app/routers/conciliacao.py#L531)
- Rota: `POST /conciliacao/venda/{venda_id}/criar-e-conciliar`
- Responsabilidade: Endpoint que cria e conciliar venda e devolve a resposta HTTP correspondente.

### `cancelar_venda(venda_id: int, cliente_id: int=Form(...), db: Session=Depends(get_db), usuario: Usuario=Depends(require_conciliacao))`

- Local: [cancelar_venda](../app/routers/conciliacao.py#L592)
- Rota: `POST /conciliacao/venda/{venda_id}/cancelar`
- Responsabilidade: Endpoint que executa o fluxo cancelar venda e devolve a resposta HTTP correspondente.

### `fechar_lote(cliente_id: int=Form(...), data_pagamento: str=Form(...), bandeira: str=Form(''), db: Session=Depends(get_db), usuario: Usuario=Depends(require_conciliacao))`

- Local: [fechar_lote](../app/routers/conciliacao.py#L608)
- Rota: `POST /conciliacao/fechar-lote`
- Responsabilidade: Endpoint que fecha lote e devolve a resposta HTTP correspondente.

### `_reabrir_lote_duplicado_removido(lote_id: int, cliente_id: int=Form(...), db: Session=Depends(get_db), usuario: Usuario=Depends(require_conciliacao))`

- Local: [_reabrir_lote_duplicado_removido](../app/routers/conciliacao.py#L637)
- Responsabilidade: Função auxiliar responsável pelo fluxo “reabrir lote duplicado removido”.

### `_carregar_lancamentos(db: Session, cliente_id: int)`

- Local: [_carregar_lancamentos](../app/routers/conciliacao.py#L665)
- Responsabilidade: Função auxiliar que carrega lancamentos.

### `_decimal_form(valor: str) -> Decimal | None`

- Local: [_decimal_form](../app/routers/conciliacao.py#L680)
- Responsabilidade: Função auxiliar responsável pelo fluxo “decimal form”.

### `_calcular_intervalos_lancamento(forma_pagamento: str, parcela_total: int, recorrencia: str | None)`

- Local: [_calcular_intervalos_lancamento](../app/routers/conciliacao.py#L687)
- Responsabilidade: Função auxiliar que calcula intervalos lancamento.

### `_taxa_cartao_cliente(db: Session, cliente_id: int, bandeira: str | None) -> Decimal | None`

- Local: [_taxa_cartao_cliente](../app/routers/conciliacao.py#L698)
- Responsabilidade: Função auxiliar responsável pelo fluxo “taxa cartao cliente”.

### `_rateios_lancamento_manual(raw: str, centros: dict[int, CentroCusto]) -> list[dict]`

- Local: [_rateios_lancamento_manual](../app/routers/conciliacao.py#L719)
- Responsabilidade: Função auxiliar responsável pelo fluxo “rateios lancamento manual”.

### `pagina_lancamentos(request: Request, cliente_id: Optional[int]=None, flash: Optional[str]=None, db: Session=Depends(get_db), usuario: Usuario=Depends(require_conciliacao))`

- Local: [pagina_lancamentos](../app/routers/conciliacao.py#L747)
- Rota: `GET /conciliacao/lancamentos`
- Responsabilidade: Endpoint que renderiza a página de lancamentos e devolve a resposta HTTP correspondente.

### `importar_lancamentos_conciliacao(request: Request, cliente_id: int=Form(...), arquivo: UploadFile=File(...), db: Session=Depends(get_db), usuario: Usuario=Depends(require_conciliacao))`

- Local: [importar_lancamentos_conciliacao](../app/routers/conciliacao.py#L780)
- Rota: `POST /conciliacao/lancamentos/importar`
- Responsabilidade: Endpoint que importa lancamentos conciliacao e devolve a resposta HTTP correspondente.

### `criar_lancamento_manual_conciliacao(request: Request, cliente_id: int=Form(...), data_atendimento: date_type=Form(...), nome_paciente: str=Form(''), cpf_paciente: str=Form(''), centro_custo_id: str=Form(''), rateios_json: str=Form('[]'), especialidade: str=Form(''), descricao_servico: str=Form(''), plano_conta_id: Optional[int]=Form(None), valor_servico: str=Form(...), forma_pagamento: str=Form(''), condicao_pagamento: str=Form('avista'), parcela_total: int=Form(1), recorrencia: str=Form(''), ultimos_digitos_cartao: str=Form(''), bandeira_cartao: str=Form(''), percentual_medico: str=Form(''), observacao: str=Form(''), db: Session=Depends(get_db), usuario: Usuario=Depends(require_conciliacao))`

- Local: [criar_lancamento_manual_conciliacao](../app/routers/conciliacao.py#L841)
- Rota: `POST /conciliacao/lancamentos/manual`
- Responsabilidade: Endpoint que cria lancamento manual conciliacao e devolve a resposta HTTP correspondente.

## `app/routers/conciliacao_banco.py`

### `_chave_centro_custo(cc: CentroCusto) -> str`

- Local: [_chave_centro_custo](../app/routers/conciliacao_banco.py#L61)
- Responsabilidade: Função auxiliar responsável pelo fluxo “chave centro custo”.

### `_montar_rateios_banco(db: Session, cliente_id: int, valor_total: Decimal, rateios_json: str) -> list[dict]`

- Local: [_montar_rateios_banco](../app/routers/conciliacao_banco.py#L65)
- Responsabilidade: Função auxiliar que monta rateios banco.

### `clientes_do_usuario(db: Session, usuario: Usuario)`

- Local: [clientes_do_usuario](../app/routers/conciliacao_banco.py#L97)
- Responsabilidade: Função auxiliar responsável pelo fluxo “clientes do usuario”.

### `_total_pago_conta(db: Session, conta_id: int) -> Decimal`

- Local: [_total_pago_conta](../app/routers/conciliacao_banco.py#L106)
- Responsabilidade: Função auxiliar responsável pelo fluxo “total pago conta”.

### `_registrar_pagamento_conta(db: Session, conta: ContaPagar, valor: Decimal, data_pagamento: date, usuario_id: int | None, movimentacao_id: int | None=None, observacao: str | None=None) -> bool`

- Local: [_registrar_pagamento_conta](../app/routers/conciliacao_banco.py#L113)
- Responsabilidade: Função auxiliar que registra pagamento conta.

### `_carregar_movimentacoes(db: Session, cliente_id: int)`

- Local: [_carregar_movimentacoes](../app/routers/conciliacao_banco.py#L145)
- Responsabilidade: Retorna pix_ted pendentes que NÃO estão vinculados a lote de cartão.

### `_carregar_lancamentos_pendentes(db: Session, cliente_id: int)`

- Local: [_carregar_lancamentos_pendentes](../app/routers/conciliacao_banco.py#L166)
- Responsabilidade: Função auxiliar que carrega lancamentos pendentes.

### `_buscar_no_sistema(db: Session, cliente_id: int, mov: MovimentacaoBancaria, termo: str | None)`

- Local: [_buscar_no_sistema](../app/routers/conciliacao_banco.py#L183)
- Responsabilidade: Função auxiliar que busca no sistema.

### `_montar_painel(db: Session, cliente_id: int, lancamentos: list, movimentacoes: list, busca_mov_id: Optional[int]=None, busca_termo: Optional[str]=None)`

- Local: [_montar_painel](../app/routers/conciliacao_banco.py#L210)
- Responsabilidade: Função auxiliar que monta painel.

### `_aplicar_conciliacao(db: Session, mov: MovimentacaoBancaria, at: Atendimento)`

- Local: [_aplicar_conciliacao](../app/routers/conciliacao_banco.py#L256)
- Responsabilidade: Função auxiliar que aplica conciliacao.

### `_conciliar_pix_ted_prontos(db: Session, cliente_id: int, usuario: Usuario | None=None) -> int`

- Local: [_conciliar_pix_ted_prontos](../app/routers/conciliacao_banco.py#L265)
- Responsabilidade: Função auxiliar que concilia pix ted prontos.

### `_auto_match_lotes(db: Session, cliente_id: int, usuario: Usuario | None=None) -> int`

- Local: [_auto_match_lotes](../app/routers/conciliacao_banco.py#L289)
- Responsabilidade: Função auxiliar responsável pelo fluxo “auto match lotes”.

### `_carregar_saidas_banco(db: Session, cliente_id: int)`

- Local: [_carregar_saidas_banco](../app/routers/conciliacao_banco.py#L326)
- Responsabilidade: Saídas bancárias ainda não vinculadas a uma conta a pagar.

### `_carregar_contas_agendadas(db: Session, cliente_id: int)`

- Local: [_carregar_contas_agendadas](../app/routers/conciliacao_banco.py#L346)
- Responsabilidade: Contas a pagar com status agendado aguardando conciliação bancária.

### `_carregar_lotes_cartao(db: Session, cliente_id: int)`

- Local: [_carregar_lotes_cartao](../app/routers/conciliacao_banco.py#L360)
- Responsabilidade: Função auxiliar que carrega lotes cartao.

### `_carregar_creditos_banco_para_lote(db: Session, cliente_id: int)`

- Local: [_carregar_creditos_banco_para_lote](../app/routers/conciliacao_banco.py#L369)
- Responsabilidade: MovimentacaoBancaria pix_ted ainda não vinculadas a lote de cartão (disponíveis para match).

### `_carregar_pix_conciliados(db: Session, cliente_id: int)`

- Local: [_carregar_pix_conciliados](../app/routers/conciliacao_banco.py#L391)
- Responsabilidade: PIX/TED já conciliados com atendimento — para exibir com opção de desvincular.

### `_resumo_periodo_movimentacoes(movimentacoes: list) -> str`

- Local: [_resumo_periodo_movimentacoes](../app/routers/conciliacao_banco.py#L410)
- Responsabilidade: Função auxiliar responsável pelo fluxo “resumo periodo movimentacoes”.

### `_opcoes_mes_movimentacoes(movimentacoes: list) -> list[dict]`

- Local: [_opcoes_mes_movimentacoes](../app/routers/conciliacao_banco.py#L423)
- Responsabilidade: Função auxiliar responsável pelo fluxo “opcoes mes movimentacoes”.

### `_carregar_saidas_conciliadas(db: Session, cliente_id: int)`

- Local: [_carregar_saidas_conciliadas](../app/routers/conciliacao_banco.py#L440)
- Responsabilidade: Saídas bancárias já conciliadas com conta a pagar — para exibir com opção de desvincular.

### `_carregar_arquivados(db: Session, cliente_id: int)`

- Local: [_carregar_arquivados](../app/routers/conciliacao_banco.py#L457)
- Responsabilidade: Função auxiliar que carrega arquivados.

### `_conta_bancaria_do_ofx(db: Session, cliente_id: int, df) -> ContaBancaria`

- Local: [_conta_bancaria_do_ofx](../app/routers/conciliacao_banco.py#L488)
- Responsabilidade: Função auxiliar responsável pelo fluxo “conta bancaria do ofx”.

### `_resumo_saldos_bancarios(db: Session, cliente_id: int | None) -> list[dict]`

- Local: [_resumo_saldos_bancarios](../app/routers/conciliacao_banco.py#L514)
- Responsabilidade: Função auxiliar responsável pelo fluxo “resumo saldos bancarios”.

### `_movimentacoes_do_extrato(db: Session, cliente_id: int | None)`

- Local: [_movimentacoes_do_extrato](../app/routers/conciliacao_banco.py#L544)
- Responsabilidade: Função auxiliar responsável pelo fluxo “movimentacoes do extrato”.

### `_ctx_padrao(db, usuario, cliente_id, busca_mov_id=None, busca_termo=None, mes_conciliado=None)`

- Local: [_ctx_padrao](../app/routers/conciliacao_banco.py#L554)
- Responsabilidade: Função auxiliar responsável pelo fluxo “ctx padrao”.

### `pagina_banco(request: Request, cliente_id: Optional[int]=None, buscar_mov: Optional[int]=Query(default=None), termo: Optional[str]=Query(default=None), lote_fechado: Optional[int]=Query(default=None), mes_conciliado: Optional[str]=Query(default=None), arquivados: bool=Query(default=False), manual_criado: Optional[str]=Query(default=None), db: Session=Depends(get_db), usuario: Usuario=Depends(require_conciliacao))`

- Local: [pagina_banco](../app/routers/conciliacao_banco.py#L607)
- Rota: `GET /conciliacao/banco`
- Responsabilidade: Endpoint que renderiza a página de banco e devolve a resposta HTTP correspondente.

### `criar_receita_manual_banco(request: Request, cliente_id: int=Form(...), descricao: str=Form(...), nome_pagador: str=Form(''), valor: Decimal=Form(...), data_recebimento: date=Form(...), forma_pagamento: str=Form('pix'), observacao: str=Form(''), rateios_json: str=Form('[]'), db: Session=Depends(get_db), usuario: Usuario=Depends(require_conciliacao))`

- Local: [criar_receita_manual_banco](../app/routers/conciliacao_banco.py#L663)
- Rota: `POST /conciliacao/banco/manual/receita`
- Responsabilidade: Endpoint que cria receita manual banco e devolve a resposta HTTP correspondente.

### `criar_movimentacao_manual_banco(request: Request, cliente_id: int=Form(...), conta_bancaria_id: Optional[int]=Form(None), banco: str=Form(''), conta_numero: str=Form(''), sentido: str=Form(...), data_movimento: date=Form(...), valor: Decimal=Form(...), descricao: str=Form(...), db: Session=Depends(get_db), usuario: Usuario=Depends(require_conciliacao))`

- Local: [criar_movimentacao_manual_banco](../app/routers/conciliacao_banco.py#L722)
- Rota: `POST /conciliacao/banco/manual/movimentacao`
- Responsabilidade: Endpoint que cria movimentacao manual banco e devolve a resposta HTTP correspondente.

### `criar_despesa_manual_banco(request: Request, cliente_id: int=Form(...), descricao: str=Form(...), fornecedor: str=Form(''), valor: Decimal=Form(...), vencimento: date=Form(...), observacao: str=Form(''), rateios_json: str=Form('[]'), db: Session=Depends(get_db), usuario: Usuario=Depends(require_conciliacao))`

- Local: [criar_despesa_manual_banco](../app/routers/conciliacao_banco.py#L794)
- Rota: `POST /conciliacao/banco/manual/despesa`
- Responsabilidade: Endpoint que cria despesa manual banco e devolve a resposta HTTP correspondente.

### `criar_pagamento_parcial_banco(request: Request, cliente_id: int=Form(...), conta_id: int=Form(...), valor: Decimal=Form(...), data_pagamento: date=Form(...), observacao: str=Form(''), db: Session=Depends(get_db), usuario: Usuario=Depends(require_conciliacao))`

- Local: [criar_pagamento_parcial_banco](../app/routers/conciliacao_banco.py#L846)
- Rota: `POST /conciliacao/banco/manual/pagamento-parcial`
- Responsabilidade: Endpoint que cria pagamento parcial banco e devolve a resposta HTTP correspondente.

### `importar_lancamentos_banco(request: Request, cliente_id: int=Form(...), arquivo: UploadFile=File(...), db: Session=Depends(get_db), usuario: Usuario=Depends(require_conciliacao))`

- Local: [importar_lancamentos_banco](../app/routers/conciliacao_banco.py#L886)
- Rota: `POST /conciliacao/banco/importar-lancamentos`
- Responsabilidade: Endpoint que importa lancamentos banco e devolve a resposta HTTP correspondente.

### `importar_extrato_banco(request: Request, cliente_id: int=Form(...), arquivo: UploadFile=File(...), db: Session=Depends(get_db), usuario: Usuario=Depends(require_conciliacao))`

- Local: [importar_extrato_banco](../app/routers/conciliacao_banco.py#L929)
- Rota: `POST /conciliacao/banco/importar-extrato`
- Responsabilidade: Endpoint que importa extrato banco e devolve a resposta HTTP correspondente.

### `conciliar_todos_prontos(cliente_id: int=Form(...), db: Session=Depends(get_db), usuario: Usuario=Depends(require_conciliacao))`

- Local: [conciliar_todos_prontos](../app/routers/conciliacao_banco.py#L985)
- Rota: `POST /conciliacao/banco/conciliar-todos-prontos`
- Responsabilidade: Endpoint que concilia todos prontos e devolve a resposta HTTP correspondente.

### `conciliar_movimentacao(mov_id: int, cliente_id: int=Form(...), atendimento_id: int=Form(...), origem: str=Form('sugestao'), db: Session=Depends(get_db), usuario: Usuario=Depends(require_conciliacao))`

- Local: [conciliar_movimentacao](../app/routers/conciliacao_banco.py#L1000)
- Rota: `POST /conciliacao/banco/movimentacao/{mov_id}/conciliar`
- Responsabilidade: Endpoint que concilia movimentacao e devolve a resposta HTTP correspondente.

### `revisar_movimentacao(mov_id: int, cliente_id: int=Form(...), db: Session=Depends(get_db), usuario: Usuario=Depends(require_conciliacao))`

- Local: [revisar_movimentacao](../app/routers/conciliacao_banco.py#L1023)
- Rota: `POST /conciliacao/banco/movimentacao/{mov_id}/revisar`
- Responsabilidade: Endpoint que executa o fluxo revisar movimentacao e devolve a resposta HTTP correspondente.

### `arquivar_movimentacao(mov_id: int, cliente_id: int=Form(...), db: Session=Depends(get_db), usuario: Usuario=Depends(require_conciliacao))`

- Local: [arquivar_movimentacao](../app/routers/conciliacao_banco.py#L1041)
- Rota: `POST /conciliacao/banco/movimentacao/{mov_id}/arquivar`
- Responsabilidade: Endpoint que arquiva movimentacao e devolve a resposta HTTP correspondente.

### `restaurar_movimentacao(mov_id: int, cliente_id: int=Form(...), db: Session=Depends(get_db), usuario: Usuario=Depends(require_conciliacao))`

- Local: [restaurar_movimentacao](../app/routers/conciliacao_banco.py#L1059)
- Rota: `POST /conciliacao/banco/movimentacao/{mov_id}/restaurar`
- Responsabilidade: Endpoint que restaura movimentacao e devolve a resposta HTTP correspondente.

### `arquivar_lancamento_sistema(atendimento_id: int, cliente_id: int=Form(...), db: Session=Depends(get_db), usuario: Usuario=Depends(require_conciliacao))`

- Local: [arquivar_lancamento_sistema](../app/routers/conciliacao_banco.py#L1074)
- Rota: `POST /conciliacao/banco/lancamento/{atendimento_id}/arquivar`
- Responsabilidade: Endpoint que arquiva lancamento sistema e devolve a resposta HTTP correspondente.

### `restaurar_lancamento_sistema(atendimento_id: int, cliente_id: int=Form(...), db: Session=Depends(get_db), usuario: Usuario=Depends(require_conciliacao))`

- Local: [restaurar_lancamento_sistema](../app/routers/conciliacao_banco.py#L1092)
- Rota: `POST /conciliacao/banco/lancamento/{atendimento_id}/restaurar`
- Responsabilidade: Endpoint que restaura lancamento sistema e devolve a resposta HTTP correspondente.

### `arquivar_conta_sistema(conta_id: int, cliente_id: int=Form(...), db: Session=Depends(get_db), usuario: Usuario=Depends(require_conciliacao))`

- Local: [arquivar_conta_sistema](../app/routers/conciliacao_banco.py#L1107)
- Rota: `POST /conciliacao/banco/conta/{conta_id}/arquivar`
- Responsabilidade: Endpoint que arquiva conta sistema e devolve a resposta HTTP correspondente.

### `restaurar_conta_sistema(conta_id: int, cliente_id: int=Form(...), db: Session=Depends(get_db), usuario: Usuario=Depends(require_conciliacao))`

- Local: [restaurar_conta_sistema](../app/routers/conciliacao_banco.py#L1125)
- Rota: `POST /conciliacao/banco/conta/{conta_id}/restaurar`
- Responsabilidade: Endpoint que restaura conta sistema e devolve a resposta HTTP correspondente.

### `desvincular_movimentacao_pix(mov_id: int, cliente_id: int=Form(...), db: Session=Depends(get_db), usuario: Usuario=Depends(require_conciliacao))`

- Local: [desvincular_movimentacao_pix](../app/routers/conciliacao_banco.py#L1140)
- Rota: `POST /conciliacao/banco/movimentacao/{mov_id}/desvincular`
- Responsabilidade: Endpoint que executa o fluxo desvincular movimentacao pix e devolve a resposta HTTP correspondente.

### `criar_e_conciliar(mov_id: int, cliente_id: int=Form(...), data_atendimento: str=Form(...), nome_paciente: str=Form(''), cpf_paciente: str=Form(''), medico: str=Form(''), especialidade: str=Form(''), tipo_servico: str=Form(''), descricao_servico: str=Form(''), observacao: str=Form(''), db: Session=Depends(get_db), usuario: Usuario=Depends(require_conciliacao))`

- Local: [criar_e_conciliar](../app/routers/conciliacao_banco.py#L1167)
- Rota: `POST /conciliacao/banco/movimentacao/{mov_id}/criar-e-conciliar`
- Responsabilidade: Endpoint que cria e conciliar e devolve a resposta HTTP correspondente.

### `importar_conta_corrente(request: Request, cliente_id: int=Form(...), arquivo: UploadFile=File(...), db: Session=Depends(get_db), usuario: Usuario=Depends(require_conciliacao))`

- Local: [importar_conta_corrente](../app/routers/conciliacao_banco.py#L1228)
- Rota: `POST /conciliacao/banco/conta-corrente/importar`
- Responsabilidade: Endpoint que importa conta corrente e devolve a resposta HTTP correspondente.

### `conciliar_lote_com_banco(lote_id: int, cliente_id: int=Form(...), mov_id: int=Form(...), db: Session=Depends(get_db), usuario: Usuario=Depends(require_conciliacao))`

- Local: [conciliar_lote_com_banco](../app/routers/conciliacao_banco.py#L1270)
- Rota: `POST /conciliacao/banco/lote/{lote_id}/conciliar`
- Responsabilidade: Endpoint que concilia lote com banco e devolve a resposta HTTP correspondente.

### `auto_match_lotes(cliente_id: int=Form(...), db: Session=Depends(get_db), usuario: Usuario=Depends(require_conciliacao))`

- Local: [auto_match_lotes](../app/routers/conciliacao_banco.py#L1295)
- Rota: `POST /conciliacao/banco/lote/auto-match`
- Responsabilidade: Auto-concilia lotes pendentes com MovimentacaoBancaria de valor exato.

### `desvincular_lote(lote_id: int, cliente_id: int=Form(...), db: Session=Depends(get_db), usuario: Usuario=Depends(require_conciliacao))`

- Local: [desvincular_lote](../app/routers/conciliacao_banco.py#L1310)
- Rota: `POST /conciliacao/banco/lote/{lote_id}/desvincular`
- Responsabilidade: Endpoint que executa o fluxo desvincular lote e devolve a resposta HTTP correspondente.

### `conciliar_saida_com_conta(mov_id: int, cliente_id: int=Form(...), conta_id: int=Form(...), db: Session=Depends(get_db), usuario: Usuario=Depends(require_conciliacao))`

- Local: [conciliar_saida_com_conta](../app/routers/conciliacao_banco.py#L1337)
- Rota: `POST /conciliacao/banco/saida/{mov_id}/conciliar`
- Responsabilidade: Endpoint que concilia saida com conta e devolve a resposta HTTP correspondente.

### `desvincular_saida(mov_id: int, cliente_id: int=Form(...), db: Session=Depends(get_db), usuario: Usuario=Depends(require_conciliacao))`

- Local: [desvincular_saida](../app/routers/conciliacao_banco.py#L1366)
- Rota: `POST /conciliacao/banco/saida/{mov_id}/desvincular`
- Responsabilidade: Endpoint que executa o fluxo desvincular saida e devolve a resposta HTTP correspondente.

### `auto_match_saidas(cliente_id: int=Form(...), db: Session=Depends(get_db), usuario: Usuario=Depends(require_conciliacao))`

- Local: [auto_match_saidas](../app/routers/conciliacao_banco.py#L1400)
- Rota: `POST /conciliacao/banco/saida/auto-match`
- Responsabilidade: Concilia em lote, por acao do usuario, saidas com contas de valor exato.

## `app/routers/contas_pagar.py`

### `_planos_despesa(db: Session, cliente_ids: list[int]) -> list[PlanoConta]`

- Local: [_planos_despesa](../app/routers/contas_pagar.py#L50)
- Responsabilidade: Função auxiliar responsável pelo fluxo “planos despesa”.

### `_plano_despesa_valido(db: Session, cliente_id: int, plano_conta_id: int | None) -> PlanoConta | None`

- Local: [_plano_despesa_valido](../app/routers/contas_pagar.py#L58)
- Responsabilidade: Função auxiliar responsável pelo fluxo “plano despesa valido”.

### `clientes_do_usuario(db: Session, usuario: Usuario)`

- Local: [clientes_do_usuario](../app/routers/contas_pagar.py#L70)
- Responsabilidade: Função auxiliar responsável pelo fluxo “clientes do usuario”.

### `_ids_clientes_do_usuario(db: Session, usuario: Usuario) -> list[int]`

- Local: [_ids_clientes_do_usuario](../app/routers/contas_pagar.py#L79)
- Responsabilidade: Função auxiliar responsável pelo fluxo “ids clientes do usuario”.

### `_key_centro_custo(cc: CentroCusto) -> str`

- Local: [_key_centro_custo](../app/routers/contas_pagar.py#L83)
- Responsabilidade: Função auxiliar responsável pelo fluxo “key centro custo”.

### `_centros_custo_por_cliente(db: Session, cliente_ids: list[int]) -> dict[int, list[dict]]`

- Local: [_centros_custo_por_cliente](../app/routers/contas_pagar.py#L88)
- Responsabilidade: Função auxiliar responsável pelo fluxo “centros custo por cliente”.

### `_categoria_nome_com_centros(centros_por_cliente: dict[int, list[dict]]) -> dict[str, str]`

- Local: [_categoria_nome_com_centros](../app/routers/contas_pagar.py#L107)
- Responsabilidade: Função auxiliar responsável pelo fluxo “categoria nome com centros”.

### `_categoria_dre_valida(db: Session, cliente_id: int, categoria_dre: Optional[str]) -> str | None`

- Local: [_categoria_dre_valida](../app/routers/contas_pagar.py#L116)
- Responsabilidade: Função auxiliar responsável pelo fluxo “categoria dre valida”.

### `_decimal_rateio(valor: str) -> Decimal | None`

- Local: [_decimal_rateio](../app/routers/contas_pagar.py#L129)
- Responsabilidade: Função auxiliar responsável pelo fluxo “decimal rateio”.

### `_centro_por_key(db: Session, cliente_id: int, key: str) -> CentroCusto | None`

- Local: [_centro_por_key](../app/routers/contas_pagar.py#L136)
- Responsabilidade: Função auxiliar responsável pelo fluxo “centro por key”.

### `_montar_rateios_conta(db: Session, cliente_id: int, valor_total: Decimal, categorias: List[str], percentuais: List[str]) -> list[dict]`

- Local: [_montar_rateios_conta](../app/routers/contas_pagar.py#L147)
- Responsabilidade: Função auxiliar que monta rateios conta.

### `_status_permitidos(atual: StatusContaPagar) -> list[StatusContaPagar]`

- Local: [_status_permitidos](../app/routers/contas_pagar.py#L195)
- Responsabilidade: Função auxiliar responsável pelo fluxo “status permitidos”.

### `_alterar_status_conta(db: Session, conta: ContaPagar, novo_status: StatusContaPagar, usuario: Usuario) -> bool`

- Local: [_alterar_status_conta](../app/routers/contas_pagar.py#L199)
- Responsabilidade: Aplica a transição se permitida pela matriz. Retorna True se mudou algo.

### `_data_recorrencia(origem: date, intervalo: str, dias_personalizado: Optional[int], indice: int) -> date`

- Local: [_data_recorrencia](../app/routers/contas_pagar.py#L220)
- Responsabilidade: Data da N-ésima ocorrência futura (indice=1,2,3...), sempre calculada a partir da data de origem — evita que o dia do mês "derrape" (ex: 31 -> 28 -> 28 -> 28) quando uma ocorrência intermediária cai num mês mais curto.

### `listar_contas(request: Request, cliente_id: Optional[int]=None, situacao: Optional[str]=None, status: Optional[str]=None, forma_pagamento: Optional[str]=None, vencimento_inicio: Optional[str]=None, vencimento_fim: Optional[str]=None, flash: Optional[str]=None, db: Session=Depends(get_db), usuario: Usuario=Depends(require_contas_pagar))`

- Local: [listar_contas](../app/routers/contas_pagar.py#L240)
- Rota: `GET /contas-pagar`
- Responsabilidade: Endpoint que lista contas e devolve a resposta HTTP correspondente.

### `pagina_nova_conta(request: Request, cliente_id: Optional[int]=None, db: Session=Depends(get_db), usuario: Usuario=Depends(get_usuario_atual))`

- Local: [pagina_nova_conta](../app/routers/contas_pagar.py#L315)
- Rota: `GET /contas-pagar/novo`
- Responsabilidade: Endpoint que renderiza a página de nova conta e devolve a resposta HTTP correspondente.

### `baixar_documento_conta(conta_id: int, db: Session=Depends(get_db), usuario: Usuario=Depends(require_contas_pagar))`

- Local: [baixar_documento_conta](../app/routers/contas_pagar.py#L337)
- Rota: `GET /contas-pagar/{conta_id}/documento`
- Responsabilidade: Endpoint que executa o fluxo baixar documento conta e devolve a resposta HTTP correspondente.

### `form_editar_conta(conta_id: int, request: Request, db: Session=Depends(get_db), usuario: Usuario=Depends(get_usuario_atual))`

- Local: [form_editar_conta](../app/routers/contas_pagar.py#L361)
- Rota: `GET /contas-pagar/{conta_id}/editar`
- Responsabilidade: Endpoint que executa o fluxo form editar conta e devolve a resposta HTTP correspondente.

### `salvar_edicao_conta(conta_id: int, descricao: str=Form(...), fornecedor: Optional[str]=Form(None), valor: Decimal=Form(...), vencimento: date=Form(...), data_competencia: Optional[date]=Form(None), forma_pagamento: Optional[str]=Form(None), plano_conta_id: Optional[int]=Form(None), observacao: Optional[str]=Form(None), escopo_valor: str=Form('somente'), rateio_centro_custo_key: Optional[List[str]]=Form(None), rateio_percentual: Optional[List[str]]=Form(None), db: Session=Depends(get_db), usuario: Usuario=Depends(require_contas_pagar))`

- Local: [salvar_edicao_conta](../app/routers/contas_pagar.py#L388)
- Rota: `POST /contas-pagar/{conta_id}/editar`
- Responsabilidade: Endpoint que salva edicao conta e devolve a resposta HTTP correspondente.

### `_ids_protegidos(db: Session, contas: list[ContaPagar]) -> set[int]`

- Local: [_ids_protegidos](../app/routers/contas_pagar.py#L488)
- Responsabilidade: IDs de contas com pagamento ou conciliação, que não podem ser alteradas/excluídas.

### `_preparar_exclusao_recorrencias(db: Session, contas: list[ContaPagar]) -> None`

- Local: [_preparar_exclusao_recorrencias](../app/routers/contas_pagar.py#L505)
- Responsabilidade: Preserva o grupo restante quando seu lançamento de referência é excluído.

### `excluir_conta(conta_id: int, request: Request, cliente_id: int=Form(...), escopo: str=Form('somente'), db: Session=Depends(get_db), usuario: Usuario=Depends(require_contas_pagar))`

- Local: [excluir_conta](../app/routers/contas_pagar.py#L529)
- Rota: `POST /contas-pagar/{conta_id}/excluir`
- Responsabilidade: Endpoint que exclui conta e devolve a resposta HTTP correspondente.

### `criar_conta(cliente_id: int=Form(...), descricao: str=Form(...), fornecedor: Optional[str]=Form(None), valor: Decimal=Form(...), vencimento: date=Form(...), data_competencia: Optional[date]=Form(None), forma_pagamento: Optional[str]=Form(None), categoria_dre: Optional[str]=Form(None), plano_conta_id: Optional[int]=Form(None), rateio_centro_custo_key: List[str]=Form(default=[]), rateio_percentual: List[str]=Form(default=[]), especialidade: Optional[str]=Form(None), observacao: Optional[str]=Form(None), documento: Optional[UploadFile]=File(None), recorrente: bool=Form(False), recorrencia_intervalo: str=Form('mensal'), recorrencia_dias: Optional[int]=Form(None), recorrencia_qtd: int=Form(1), db: Session=Depends(get_db), usuario: Usuario=Depends(require_contas_pagar))`

- Local: [criar_conta](../app/routers/contas_pagar.py#L587)
- Rota: `POST /contas-pagar`
- Responsabilidade: Endpoint que cria conta e devolve a resposta HTTP correspondente.

### `importar_contas(request: Request, cliente_id: int=Form(...), arquivo: UploadFile=File(...), db: Session=Depends(get_db), usuario: Usuario=Depends(require_contas_pagar))`

- Local: [importar_contas](../app/routers/contas_pagar.py#L729)
- Rota: `POST /contas-pagar/importar`
- Responsabilidade: Endpoint que importa contas e devolve a resposta HTTP correspondente.

### `_norm(nome: str) -> str`

- Local: [importar_contas._norm](../app/routers/contas_pagar.py#L740)
- Responsabilidade: Função auxiliar responsável pelo fluxo “norm”.

### `_col(df, opcoes)`

- Local: [importar_contas._col](../app/routers/contas_pagar.py#L745)
- Responsabilidade: Função auxiliar responsável pelo fluxo “col”.

### `alterar_status_conta_rota(conta_id: int, novo_status: str=Form(...), db: Session=Depends(get_db), usuario: Usuario=Depends(require_contas_pagar))`

- Local: [alterar_status_conta_rota](../app/routers/contas_pagar.py#L872)
- Rota: `POST /contas-pagar/{conta_id}/status`
- Responsabilidade: Endpoint que executa o fluxo alterar status conta rota e devolve a resposta HTTP correspondente.

### `agendar_pagamento(conta_id: int, db: Session=Depends(get_db), usuario: Usuario=Depends(get_usuario_atual))`

- Local: [agendar_pagamento](../app/routers/contas_pagar.py#L900)
- Rota: `POST /contas-pagar/{conta_id}/agendar`
- Responsabilidade: Wrapper de compatibilidade — equivalente a status=agendado.

### `cancelar_conta(conta_id: int, db: Session=Depends(get_db), usuario: Usuario=Depends(require_contas_pagar))`

- Local: [cancelar_conta](../app/routers/contas_pagar.py#L917)
- Rota: `POST /contas-pagar/{conta_id}/cancelar`
- Responsabilidade: Wrapper de compatibilidade — equivalente a status=cancelado.

### `aplicar_lote_contas(request: Request, ids: List[int]=Form(...), acao: str=Form(...), plano_conta_id: Optional[int]=Form(None), centro_custo_id: Optional[int]=Form(None), novo_status: str=Form(''), db: Session=Depends(get_db), usuario: Usuario=Depends(require_contas_pagar))`

- Local: [aplicar_lote_contas](../app/routers/contas_pagar.py#L934)
- Rota: `POST /contas-pagar/lote/aplicar`
- Responsabilidade: Endpoint que aplica lote contas e devolve a resposta HTTP correspondente.

### `erro(mensagem)`

- Local: [aplicar_lote_contas.erro](../app/routers/contas_pagar.py#L951)
- Responsabilidade: Função auxiliar responsável pelo fluxo “erro”.

## `app/routers/contas_pagar_conciliacao.py`

### `clientes_do_usuario(db: Session, usuario: Usuario)`

- Local: [clientes_do_usuario](../app/routers/contas_pagar_conciliacao.py#L36)
- Responsabilidade: Função auxiliar responsável pelo fluxo “clientes do usuario”.

### `_contas_pendentes(db: Session, cliente_id: int)`

- Local: [_contas_pendentes](../app/routers/contas_pagar_conciliacao.py#L45)
- Responsabilidade: Função auxiliar responsável pelo fluxo “contas pendentes”.

### `_sugestao_conta(valor_banco: Decimal, data_banco, contas: list)`

- Local: [_sugestao_conta](../app/routers/contas_pagar_conciliacao.py#L57)
- Responsabilidade: Função auxiliar responsável pelo fluxo “sugestao conta”.

### `pagina_conciliacao_cartao_pagar(request: Request, cliente_id: Optional[int]=None, buscar_mov: Optional[int]=Query(default=None), termo: Optional[str]=Query(default=None), db: Session=Depends(get_db), usuario: Usuario=Depends(require_conciliacao))`

- Local: [pagina_conciliacao_cartao_pagar](../app/routers/contas_pagar_conciliacao.py#L77)
- Rota: `GET /contas-pagar/conciliacao-cartao`
- Responsabilidade: Endpoint que renderiza a página de conciliacao cartao pagar e devolve a resposta HTTP correspondente.

### `importar_cartao_pagar(request: Request, cliente_id: int=Form(...), arquivo: UploadFile=File(...), db: Session=Depends(get_db), usuario: Usuario=Depends(require_conciliacao))`

- Local: [importar_cartao_pagar](../app/routers/contas_pagar_conciliacao.py#L147)
- Rota: `POST /contas-pagar/conciliacao-cartao/processar`
- Responsabilidade: Endpoint que importa cartao pagar e devolve a resposta HTTP correspondente.

### `_col(names)`

- Local: [importar_cartao_pagar._col](../app/routers/contas_pagar_conciliacao.py#L174)
- Responsabilidade: Função auxiliar responsável pelo fluxo “col”.

### `conciliar_cartao_pagar(mov_id: int, cliente_id: int=Form(...), conta_pagar_id: int=Form(...), db: Session=Depends(get_db), usuario: Usuario=Depends(require_conciliacao))`

- Local: [conciliar_cartao_pagar](../app/routers/contas_pagar_conciliacao.py#L241)
- Rota: `POST /contas-pagar/conciliacao-cartao/mov/{mov_id}/conciliar`
- Responsabilidade: Endpoint que concilia cartao pagar e devolve a resposta HTTP correspondente.

### `ignorar_cartao_pagar(mov_id: int, cliente_id: int=Form(...), db: Session=Depends(get_db), usuario: Usuario=Depends(require_conciliacao))`

- Local: [ignorar_cartao_pagar](../app/routers/contas_pagar_conciliacao.py#L271)
- Rota: `POST /contas-pagar/conciliacao-cartao/mov/{mov_id}/ignorar`
- Responsabilidade: Endpoint que ignora cartao pagar e devolve a resposta HTTP correspondente.

### `pagina_conciliacao_banco_pagar(request: Request, cliente_id: Optional[int]=None, buscar_linha: Optional[int]=Query(default=None), termo: Optional[str]=Query(default=None), db: Session=Depends(get_db), usuario: Usuario=Depends(require_conciliacao))`

- Local: [pagina_conciliacao_banco_pagar](../app/routers/contas_pagar_conciliacao.py#L293)
- Rota: `GET /contas-pagar/conciliacao-banco`
- Responsabilidade: Endpoint que renderiza a página de conciliacao banco pagar e devolve a resposta HTTP correspondente.

### `importar_banco_pagar(request: Request, cliente_id: int=Form(...), arquivo: UploadFile=File(...), col_data: str=Form('data'), col_descricao: str=Form('descricao'), col_valor: str=Form('valor'), col_tipo: str=Form('tipo'), db: Session=Depends(get_db), usuario: Usuario=Depends(require_conciliacao))`

- Local: [importar_banco_pagar](../app/routers/contas_pagar_conciliacao.py#L360)
- Rota: `POST /contas-pagar/conciliacao-banco/importar`
- Responsabilidade: Endpoint que importa banco pagar e devolve a resposta HTTP correspondente.

### `_col(names)`

- Local: [importar_banco_pagar._col](../app/routers/contas_pagar_conciliacao.py#L391)
- Responsabilidade: Função auxiliar responsável pelo fluxo “col”.

### `conciliar_linha_banco_pagar(linha_id: int, cliente_id: int=Form(...), conta_pagar_id: int=Form(...), db: Session=Depends(get_db), usuario: Usuario=Depends(require_conciliacao))`

- Local: [conciliar_linha_banco_pagar](../app/routers/contas_pagar_conciliacao.py#L449)
- Rota: `POST /contas-pagar/conciliacao-banco/linha/{linha_id}/conciliar`
- Responsabilidade: Endpoint que concilia linha banco pagar e devolve a resposta HTTP correspondente.

### `ignorar_linha_banco_pagar(linha_id: int, cliente_id: int=Form(...), db: Session=Depends(get_db), usuario: Usuario=Depends(require_conciliacao))`

- Local: [ignorar_linha_banco_pagar](../app/routers/contas_pagar_conciliacao.py#L479)
- Rota: `POST /contas-pagar/conciliacao-banco/linha/{linha_id}/ignorar`
- Responsabilidade: Endpoint que ignora linha banco pagar e devolve a resposta HTTP correspondente.

## `app/routers/dashboard.py`

### `dashboard(request: Request, db: Session=Depends(get_db), usuario: Usuario=Depends(get_usuario_atual))`

- Local: [dashboard](../app/routers/dashboard.py#L22)
- Rota: `GET /`
- Responsabilidade: Endpoint que executa o fluxo dashboard e devolve a resposta HTTP correspondente.

### `_medias_mensais(db: Session, hoje: date, ids_clientes: list[int], meses: int) -> dict`

- Local: [_medias_mensais](../app/routers/dashboard.py#L61)
- Responsabilidade: Função auxiliar responsável pelo fluxo “medias mensais”.

### `_alertas_recorrentes(db: Session, hoje: date, ids_clientes: list) -> list`

- Local: [_alertas_recorrentes](../app/routers/dashboard.py#L81)
- Responsabilidade: Retorna contas recorrentes cujo vencimento está dentro da janela de aviso.

### `_brl(v) -> str`

- Local: [_brl](../app/routers/dashboard.py#L106)
- Responsabilidade: Função auxiliar responsável pelo fluxo “brl”.

### `_blocos_processo(db: Session, hoje: date, ids_clientes: list) -> list`

- Local: [_blocos_processo](../app/routers/dashboard.py#L110)
- Responsabilidade: Resumo por módulo/processo (Contas a Receber, Contas a Pagar, Conciliação, Fechamento).

### `_dashboard_coordenador(db: Session, hoje: date, cliente_ativo_id: int | None=None) -> dict`

- Local: [_dashboard_coordenador](../app/routers/dashboard.py#L179)
- Responsabilidade: Função auxiliar responsável pelo fluxo “dashboard coordenador”.

### `_dashboard_funcionario(db: Session, hoje: date, usuario: Usuario, cliente_ativo_id: int | None=None) -> dict`

- Local: [_dashboard_funcionario](../app/routers/dashboard.py#L290)
- Responsabilidade: Função auxiliar responsável pelo fluxo “dashboard funcionario”.

## `app/routers/fechamento.py`

### `clientes_do_usuario(db: Session, usuario: Usuario)`

- Local: [clientes_do_usuario](../app/routers/fechamento.py#L46)
- Responsabilidade: Função auxiliar responsável pelo fluxo “clientes do usuario”.

### `formatar_brl(valor: Decimal) -> str`

- Local: [formatar_brl](../app/routers/fechamento.py#L55)
- Responsabilidade: Função auxiliar que formata brl.

### `_parse_data_aprovacao(data: Optional[str]) -> tuple[date, str]`

- Local: [_parse_data_aprovacao](../app/routers/fechamento.py#L59)
- Responsabilidade: Função auxiliar responsável pelo fluxo “parse data aprovacao”.

### `_parse_saldo(saldo: Optional[str]) -> Decimal`

- Local: [_parse_saldo](../app/routers/fechamento.py#L69)
- Responsabilidade: Função auxiliar responsável pelo fluxo “parse saldo”.

### `_contas_para_aprovacao(db: Session, cliente_id: int, data_obj: date) -> list[ContaPagar]`

- Local: [_contas_para_aprovacao](../app/routers/fechamento.py#L78)
- Responsabilidade: Função auxiliar responsável pelo fluxo “contas para aprovacao”.

### `_p(texto) -> str`

- Local: [_p](../app/routers/fechamento.py#L91)
- Responsabilidade: Função auxiliar responsável pelo fluxo “p”.

### `_gerar_pdf_aprovacao(cliente: ClienteBPO, contas: list[ContaPagar], data_obj: date, saldo_conta: Decimal, total_despesas: Decimal, saldo_final: Decimal, usuario: Usuario) -> bytes`

- Local: [_gerar_pdf_aprovacao](../app/routers/fechamento.py#L95)
- Responsabilidade: Função auxiliar que gera pdf aprovacao.

### `pagina_fechamento(request: Request, cliente_id: Optional[int]=None, data: Optional[str]=None, saldo: Optional[str]=None, db: Session=Depends(get_db), usuario: Usuario=Depends(require_gestao))`

- Local: [pagina_fechamento](../app/routers/fechamento.py#L264)
- Rota: `GET /fechamento`
- Responsabilidade: Endpoint que renderiza a página de fechamento e devolve a resposta HTTP correspondente.

### `pdf_aprovacao(request: Request, cliente_id: int, data: Optional[str]=None, saldo: Optional[str]=None, db: Session=Depends(get_db), usuario: Usuario=Depends(require_gestao))`

- Local: [pdf_aprovacao](../app/routers/fechamento.py#L338)
- Rota: `GET /fechamento/aprovacao.pdf`
- Responsabilidade: Endpoint que executa o fluxo pdf aprovacao e devolve a resposta HTTP correspondente.

### `fechamento_mensal(request: Request, cliente_id: Optional[int]=None, data_inicio: Optional[str]=None, data_fim: Optional[str]=None, db: Session=Depends(get_db), usuario: Usuario=Depends(require_gestao))`

- Local: [fechamento_mensal](../app/routers/fechamento.py#L382)
- Rota: `GET /fechamento/mensal`
- Responsabilidade: Endpoint que executa o fluxo fechamento mensal e devolve a resposta HTTP correspondente.

## `app/routers/gestao.py`

### `clientes_do_usuario(db: Session, usuario: Usuario)`

- Local: [clientes_do_usuario](../app/routers/gestao.py#L25)
- Responsabilidade: Função auxiliar responsável pelo fluxo “clientes do usuario”.

### `_brl(v) -> str`

- Local: [_brl](../app/routers/gestao.py#L34)
- Responsabilidade: Função auxiliar responsável pelo fluxo “brl”.

### `_pct(valor, base) -> Decimal`

- Local: [_pct](../app/routers/gestao.py#L38)
- Responsabilidade: Função auxiliar responsável pelo fluxo “pct”.

### `_retroceder_mes(mes: int, ano: int, quantidade: int=1) -> tuple[int, int]`

- Local: [_retroceder_mes](../app/routers/gestao.py#L46)
- Responsabilidade: Função auxiliar responsável pelo fluxo “retroceder mes”.

### `_meses_no_intervalo(inicio: date, fim: date) -> list[tuple[int, int]]`

- Local: [_meses_no_intervalo](../app/routers/gestao.py#L56)
- Responsabilidade: Função auxiliar responsável pelo fluxo “meses no intervalo”.

### `_resolver_periodo(periodo: str, mes: int, ano: int, hoje: date) -> tuple[date, date, str]`

- Local: [_resolver_periodo](../app/routers/gestao.py#L70)
- Responsabilidade: Função auxiliar que resolve periodo.

### `_key_centro_custo(cc: CentroCusto | None) -> str | None`

- Local: [_key_centro_custo](../app/routers/gestao.py#L85)
- Responsabilidade: Função auxiliar responsável pelo fluxo “key centro custo”.

### `_grupos_dre_cliente(db: Session, cliente_id: int | None) -> list[dict]`

- Local: [_grupos_dre_cliente](../app/routers/gestao.py#L92)
- Responsabilidade: Função auxiliar responsável pelo fluxo “grupos dre cliente”.

### `_carregar_dre_periodo(db: Session, cliente_id: int, mes: int, ano: int, inicio: date | None=None, fim: date | None=None) -> dict`

- Local: [_carregar_dre_periodo](../app/routers/gestao.py#L134)
- Responsabilidade: Função auxiliar que carrega dre periodo.

### `_saldo_atual(db: Session, cliente_id: int, fim: date) -> dict | None`

- Local: [_saldo_atual](../app/routers/gestao.py#L322)
- Responsabilidade: Função auxiliar responsável pelo fluxo “saldo atual”.

### `_proximos_vencimentos(db: Session, cliente_id: int, hoje: date) -> dict`

- Local: [_proximos_vencimentos](../app/routers/gestao.py#L340)
- Responsabilidade: Função auxiliar responsável pelo fluxo “proximos vencimentos”.

### `resumo(lista)`

- Local: [_proximos_vencimentos.resumo](../app/routers/gestao.py#L361)
- Responsabilidade: Função auxiliar responsável pelo fluxo “resumo”.

### `_insights_dre(dre_atual: dict, comparativo: dict, vencimentos: dict | None=None) -> list[dict]`

- Local: [_insights_dre](../app/routers/gestao.py#L376)
- Responsabilidade: Função auxiliar responsável pelo fluxo “insights dre”.

### `gestao_receitas(request: Request, cliente_id: Optional[int]=None, mes: Optional[int]=None, ano: Optional[int]=None, db: Session=Depends(get_db), usuario: Usuario=Depends(require_gestao))`

- Local: [gestao_receitas](../app/routers/gestao.py#L445)
- Rota: `GET /gestao/receitas`
- Responsabilidade: Endpoint que executa o fluxo gestao receitas e devolve a resposta HTTP correspondente.

### `gestao_despesas(request: Request, cliente_id: Optional[int]=None, mes: Optional[int]=None, ano: Optional[int]=None, regime: str='vencimento', db: Session=Depends(get_db), usuario: Usuario=Depends(require_gestao))`

- Local: [gestao_despesas](../app/routers/gestao.py#L497)
- Rota: `GET /gestao/despesas`
- Responsabilidade: Endpoint que executa o fluxo gestao despesas e devolve a resposta HTTP correspondente.

### `gestao_orcamento(request: Request, cliente_id: Optional[int]=None, mes: Optional[int]=None, ano: Optional[int]=None, db: Session=Depends(get_db), usuario: Usuario=Depends(require_gestao))`

- Local: [gestao_orcamento](../app/routers/gestao.py#L557)
- Rota: `GET /gestao/orcamento`
- Responsabilidade: Endpoint que executa o fluxo gestao orcamento e devolve a resposta HTTP correspondente.

### `salvar_orcamento(request: Request, cliente_id: int=Form(...), mes: int=Form(...), ano: int=Form(...), db: Session=Depends(get_db), usuario: Usuario=Depends(require_gestao))`

- Local: [salvar_orcamento](../app/routers/gestao.py#L635)
- Rota: `POST /gestao/orcamento`
- Responsabilidade: Endpoint que salva orcamento e devolve a resposta HTTP correspondente.

### `gestao_dre_apresentacao(request: Request, cliente_id: int, mes: Optional[int]=None, ano: Optional[int]=None, periodo: str='mes', db: Session=Depends(get_db), usuario: Usuario=Depends(require_gestao))`

- Local: [gestao_dre_apresentacao](../app/routers/gestao.py#L690)
- Rota: `GET /gestao/dre/apresentacao`
- Responsabilidade: Endpoint que executa o fluxo gestao dre apresentacao e devolve a resposta HTTP correspondente.

### `gestao_dre(request: Request, cliente_id: Optional[int]=None, mes: Optional[int]=None, ano: Optional[int]=None, periodo: str='mes', visao: str='simples', db: Session=Depends(get_db), usuario: Usuario=Depends(require_gestao))`

- Local: [gestao_dre](../app/routers/gestao.py#L751)
- Rota: `GET /gestao/dre`
- Responsabilidade: Endpoint que executa o fluxo gestao dre e devolve a resposta HTTP correspondente.

## `app/routers/importacoes.py`

### `pagina_importacoes(request: Request, db: Session=Depends(get_db), usuario: Usuario=Depends(get_usuario_atual))`

- Local: [pagina_importacoes](../app/routers/importacoes.py#L15)
- Rota: `GET /importacoes`
- Responsabilidade: Endpoint que renderiza a página de importacoes e devolve a resposta HTTP correspondente.

## `app/routers/lancamentos.py`

### `formatar_brl(valor) -> str`

- Local: [formatar_brl](../app/routers/lancamentos.py#L27)
- Responsabilidade: Função auxiliar que formata brl.

### `clientes_do_usuario(db: Session, usuario: Usuario)`

- Local: [clientes_do_usuario](../app/routers/lancamentos.py#L34)
- Responsabilidade: Função auxiliar responsável pelo fluxo “clientes do usuario”.

### `_calcular_intervalos(forma_pagamento: str, parcela_total: int, recorrencia: Optional[str])`

- Local: [_calcular_intervalos](../app/routers/lancamentos.py#L43)
- Responsabilidade: Função auxiliar que calcula intervalos.

### `_str(lst: List[str], i: int) -> str`

- Local: [_str](../app/routers/lancamentos.py#L57)
- Responsabilidade: Função auxiliar responsável pelo fluxo “str”.

### `_decimal(lst: List[str], i: int) -> Optional[Decimal]`

- Local: [_decimal](../app/routers/lancamentos.py#L61)
- Responsabilidade: Função auxiliar responsável pelo fluxo “decimal”.

### `_parse_rateios_json(raw: str, centros_validos: dict[int, CentroCusto], valor: Decimal) -> list[dict]`

- Local: [_parse_rateios_json](../app/routers/lancamentos.py#L69)
- Responsabilidade: Função auxiliar responsável pelo fluxo “parse rateios json”.

### `_int(lst: List[str], i: int, default: int=1) -> int`

- Local: [_int](../app/routers/lancamentos.py#L106)
- Responsabilidade: Função auxiliar responsável pelo fluxo “int”.

### `_taxa_cartao(db: Session, cliente_id: int, bandeira: str) -> Optional[Decimal]`

- Local: [_taxa_cartao](../app/routers/lancamentos.py#L114)
- Responsabilidade: Função auxiliar responsável pelo fluxo “taxa cartao”.

### `listar_lancamentos(request: Request, cliente_id: Optional[int]=None, data_inicio: Optional[str]=None, data_fim: Optional[str]=None, status_conciliacao: Optional[str]=None, forma_pagamento: Optional[str]=None, flash: Optional[str]=None, db: Session=Depends(get_db), usuario: Usuario=Depends(require_lancamentos))`

- Local: [listar_lancamentos](../app/routers/lancamentos.py#L138)
- Rota: `GET /lancamentos`
- Responsabilidade: Endpoint que lista lancamentos e devolve a resposta HTTP correspondente.

### `pagina_novo_lancamento(request: Request, cliente_id: Optional[int]=None, db: Session=Depends(get_db), usuario: Usuario=Depends(get_usuario_atual))`

- Local: [pagina_novo_lancamento](../app/routers/lancamentos.py#L196)
- Rota: `GET /lancamentos/novo`
- Responsabilidade: Endpoint que renderiza a página de novo lancamento e devolve a resposta HTTP correspondente.

### `criar_lancamentos(request: Request, cliente_id: int=Form(...), data_atendimento: date=Form(...), nome_paciente: List[str]=Form(default=[]), cpf_paciente: List[str]=Form(default=[]), centro_custo_id: List[str]=Form(default=[]), rateios_json: List[str]=Form(default=[]), especialidade: List[str]=Form(default=[]), descricao_servico: List[str]=Form(default=[]), plano_conta_id: List[str]=Form(default=[]), valor_servico: List[str]=Form(default=[]), forma_pagamento: List[str]=Form(default=[]), condicao_pagamento: List[str]=Form(default=[]), parcela_total: List[str]=Form(default=[]), recorrencia: List[str]=Form(default=[]), ultimos_digitos_cartao: List[str]=Form(default=[]), bandeira_cartao: List[str]=Form(default=[]), percentual_medico: List[str]=Form(default=[]), observacao: List[str]=Form(default=[]), db: Session=Depends(get_db), usuario: Usuario=Depends(require_lancamentos))`

- Local: [criar_lancamentos](../app/routers/lancamentos.py#L234)
- Rota: `POST /lancamentos`
- Responsabilidade: Endpoint que cria lancamentos e devolve a resposta HTTP correspondente.

### `form_editar_lancamento(at_id: int, request: Request, db: Session=Depends(get_db), usuario: Usuario=Depends(require_lancamentos))`

- Local: [form_editar_lancamento](../app/routers/lancamentos.py#L390)
- Rota: `GET /lancamentos/{at_id}/editar`
- Responsabilidade: Endpoint que executa o fluxo form editar lancamento e devolve a resposta HTTP correspondente.

### `salvar_edicao_lancamento(at_id: int, request: Request, data_atendimento: date=Form(...), nome_paciente: str=Form(''), cpf_paciente: str=Form(''), centro_custo_id: str=Form(''), especialidade: str=Form(''), descricao_servico: str=Form(''), plano_conta_id: str=Form(''), valor_servico: str=Form(...), forma_pagamento: str=Form(''), condicao_pagamento: str=Form('avista'), parcela_numero: int=Form(1), parcela_total: int=Form(1), ultimos_digitos_cartao: str=Form(''), bandeira_cartao: str=Form(''), percentual_medico: str=Form(''), observacao: str=Form(''), data_prevista_recebimento: Optional[date]=Form(None), taxa_cartao: str=Form(''), rateio_centro_custo_id: Optional[List[str]]=Form(None), rateio_percentual: Optional[List[str]]=Form(None), banco_recebimento: str=Form(''), data_credito: Optional[date]=Form(None), data_pagamento_medico: Optional[date]=Form(None), db: Session=Depends(get_db), usuario: Usuario=Depends(require_lancamentos))`

- Local: [salvar_edicao_lancamento](../app/routers/lancamentos.py#L425)
- Rota: `POST /lancamentos/{at_id}/editar`
- Responsabilidade: Endpoint que salva edicao lancamento e devolve a resposta HTTP correspondente.

### `decimal_campo(raw, nome, limite)`

- Local: [salvar_edicao_lancamento.decimal_campo](../app/routers/lancamentos.py#L468)
- Responsabilidade: Função auxiliar responsável pelo fluxo “decimal campo”.

### `excluir_lancamento(at_id: int, request: Request, cliente_id: int=Form(...), db: Session=Depends(get_db), usuario: Usuario=Depends(require_lancamentos))`

- Local: [excluir_lancamento](../app/routers/lancamentos.py#L601)
- Rota: `POST /lancamentos/{at_id}/excluir`
- Responsabilidade: Endpoint que exclui lancamento e devolve a resposta HTTP correspondente.

### `_lancamento_vinculado(db: Session, at: Atendimento) -> bool`

- Local: [_lancamento_vinculado](../app/routers/lancamentos.py#L637)
- Responsabilidade: Função auxiliar responsável pelo fluxo “lancamento vinculado”.

### `excluir_lote_lancamentos(ids: List[int]=Form(...), db: Session=Depends(get_db), usuario: Usuario=Depends(require_lancamentos))`

- Local: [excluir_lote_lancamentos](../app/routers/lancamentos.py#L644)
- Rota: `POST /lancamentos/lote/excluir`
- Responsabilidade: Endpoint que exclui lote lancamentos e devolve a resposta HTTP correspondente.

### `importar_planilha_lancamentos(cliente_id: int=Form(...), arquivo: UploadFile=File(...), db: Session=Depends(get_db), usuario: Usuario=Depends(require_lancamentos))`

- Local: [importar_planilha_lancamentos](../app/routers/lancamentos.py#L667)
- Rota: `POST /lancamentos/importar`
- Responsabilidade: Endpoint que importa planilha lancamentos e devolve a resposta HTTP correspondente.

## `app/routers/logs.py`

### `pagina_logs(request: Request, modulo: Optional[str]=Query(None), usuario_id: Optional[str]=Query(None), data_inicio: Optional[str]=Query(None), data_fim: Optional[str]=Query(None), db: Session=Depends(get_db), usuario: Usuario=Depends(requer_coordenador))`

- Local: [pagina_logs](../app/routers/logs.py#L19)
- Rota: `GET /logs`
- Responsabilidade: Endpoint que renderiza a página de logs e devolve a resposta HTTP correspondente.

## `app/routers/plano_contas.py`

### `_slugificar(texto: str) -> str`

- Local: [_slugificar](../app/routers/plano_contas.py#L17)
- Responsabilidade: Função auxiliar responsável pelo fluxo “slugificar”.

### `_contexto_cliente(request: Request, db: Session) -> Optional[int]`

- Local: [_contexto_cliente](../app/routers/plano_contas.py#L23)
- Responsabilidade: Função auxiliar responsável pelo fluxo “contexto cliente”.

### `_voltar(cliente_id: Optional[int], mensagem: str='') -> RedirectResponse`

- Local: [_voltar](../app/routers/plano_contas.py#L35)
- Responsabilidade: Função auxiliar responsável pelo fluxo “voltar”.

### `pagina_plano_contas(request: Request, cliente_id: Optional[int]=None, db: Session=Depends(get_db), usuario: Usuario=Depends(requer_coordenador))`

- Local: [pagina_plano_contas](../app/routers/plano_contas.py#L41)
- Rota: `GET /admin/plano-contas`
- Responsabilidade: Endpoint que renderiza a página de plano contas e devolve a resposta HTTP correspondente.

### `criar_plano_conta(request: Request, tipo: str=Form(...), grupo: str=Form(...), nome: str=Form(...), codigo: Optional[str]=Form(None), disponibilidade: str=Form('todos'), clientes_ids: list[int]=Form([]), db: Session=Depends(get_db), usuario: Usuario=Depends(requer_coordenador))`

- Local: [criar_plano_conta](../app/routers/plano_contas.py#L63)
- Rota: `POST /admin/plano-contas`
- Responsabilidade: Endpoint que cria plano conta e devolve a resposta HTTP correspondente.

### `editar_plano_conta(request: Request, conta_id: int, grupo: str=Form(...), nome: str=Form(...), codigo: Optional[str]=Form(None), db: Session=Depends(get_db), usuario: Usuario=Depends(requer_coordenador))`

- Local: [editar_plano_conta](../app/routers/plano_contas.py#L94)
- Rota: `POST /admin/plano-contas/{conta_id}/editar`
- Responsabilidade: Endpoint que edita plano conta e devolve a resposta HTTP correspondente.

### `excluir_plano_conta(request: Request, conta_id: int, db: Session=Depends(get_db), usuario: Usuario=Depends(requer_coordenador))`

- Local: [excluir_plano_conta](../app/routers/plano_contas.py#L110)
- Rota: `POST /admin/plano-contas/{conta_id}/excluir`
- Responsabilidade: Endpoint que exclui plano conta e devolve a resposta HTTP correspondente.

## `app/routers/procedimentos.py`

### `_slugificar(texto: str) -> str`

- Local: [_slugificar](../app/routers/procedimentos.py#L17)
- Responsabilidade: Função auxiliar responsável pelo fluxo “slugificar”.

### `pagina_procedimentos(request: Request, db: Session=Depends(get_db), usuario: Usuario=Depends(get_usuario_atual))`

- Local: [pagina_procedimentos](../app/routers/procedimentos.py#L24)
- Rota: `GET /admin/procedimentos`
- Responsabilidade: Endpoint que renderiza a página de procedimentos e devolve a resposta HTTP correspondente.

### `criar_procedimento(nome: str=Form(...), codigo: Optional[str]=Form(None), db: Session=Depends(get_db), usuario: Usuario=Depends(get_usuario_atual))`

- Local: [criar_procedimento](../app/routers/procedimentos.py#L46)
- Rota: `POST /admin/procedimentos`
- Responsabilidade: Endpoint que cria procedimento e devolve a resposta HTTP correspondente.

### `editar_procedimento(procedimento_id: int, nome: str=Form(...), codigo: Optional[str]=Form(None), ativo: bool=Form(True), db: Session=Depends(get_db), usuario: Usuario=Depends(get_usuario_atual))`

- Local: [editar_procedimento](../app/routers/procedimentos.py#L79)
- Rota: `POST /admin/procedimentos/{procedimento_id}/editar`
- Responsabilidade: Endpoint que edita procedimento e devolve a resposta HTTP correspondente.

### `excluir_procedimento(procedimento_id: int, db: Session=Depends(get_db), usuario: Usuario=Depends(get_usuario_atual))`

- Local: [excluir_procedimento](../app/routers/procedimentos.py#L105)
- Rota: `POST /admin/procedimentos/{procedimento_id}/excluir`
- Responsabilidade: Endpoint que exclui procedimento e devolve a resposta HTTP correspondente.

## `app/routers/rotinas.py`

### `_render_li(tarefa: TarefaRotina, pode_reverter: bool) -> str`

- Local: [_render_li](../app/routers/rotinas.py#L77)
- Responsabilidade: Função auxiliar responsável pelo fluxo “render li”.

### `clientes_do_usuario(db: Session, usuario: Usuario)`

- Local: [clientes_do_usuario](../app/routers/rotinas.py#L115)
- Responsabilidade: Função auxiliar responsável pelo fluxo “clientes do usuario”.

### `listar_rotinas(request: Request, cliente_id: Optional[int]=None, db: Session=Depends(get_db), usuario: Usuario=Depends(require_rotinas))`

- Local: [listar_rotinas](../app/routers/rotinas.py#L129)
- Rota: `GET /rotinas`
- Responsabilidade: Endpoint que lista rotinas e devolve a resposta HTTP correspondente.

### `criar_rotina(cliente_id: int=Form(...), funcionario_id: int=Form(...), data: date=Form(...), descricao: str=Form(...), horario_previsto: Optional[str]=Form(None), db: Session=Depends(get_db), usuario: Usuario=Depends(require_rotinas))`

- Local: [criar_rotina](../app/routers/rotinas.py#L216)
- Rota: `POST /rotinas`
- Responsabilidade: Endpoint que cria rotina e devolve a resposta HTTP correspondente.

### `toggle_tarefa(tarefa_id: int, db: Session=Depends(get_db), usuario: Usuario=Depends(require_rotinas))`

- Local: [toggle_tarefa](../app/routers/rotinas.py#L241)
- Rota: `POST /rotinas/{tarefa_id}/toggle`
- Responsabilidade: Endpoint que alterna o estado de tarefa e devolve a resposta HTTP correspondente.

### `excluir_tarefa(tarefa_id: int, db: Session=Depends(get_db), usuario: Usuario=Depends(require_rotinas))`

- Local: [excluir_tarefa](../app/routers/rotinas.py#L269)
- Rota: `POST /rotinas/{tarefa_id}/excluir`
- Responsabilidade: Endpoint que exclui tarefa e devolve a resposta HTTP correspondente.

### `criar_recorrente(cliente_id: int=Form(...), descricao: str=Form(...), fornecedor: Optional[str]=Form(None), valor: Optional[str]=Form(None), dia_vencimento: int=Form(...), dias_antecedencia: int=Form(3), email_destino: Optional[str]=Form(None), db: Session=Depends(get_db), usuario: Usuario=Depends(require_rotinas))`

- Local: [criar_recorrente](../app/routers/rotinas.py#L291)
- Rota: `POST /rotinas/recorrentes`
- Responsabilidade: Endpoint que cria recorrente e devolve a resposta HTTP correspondente.

### `excluir_recorrente(rec_id: int, db: Session=Depends(get_db), usuario: Usuario=Depends(require_rotinas))`

- Local: [excluir_recorrente](../app/routers/rotinas.py#L327)
- Rota: `POST /rotinas/recorrentes/{rec_id}/excluir`
- Responsabilidade: Endpoint que exclui recorrente e devolve a resposta HTTP correspondente.

### `toggle_recorrente(rec_id: int, db: Session=Depends(get_db), usuario: Usuario=Depends(require_rotinas))`

- Local: [toggle_recorrente](../app/routers/rotinas.py#L342)
- Rota: `POST /rotinas/recorrentes/{rec_id}/toggle`
- Responsabilidade: Endpoint que alterna o estado de recorrente e devolve a resposta HTTP correspondente.

## `app/security.py`

Middlewares HTTP defensivos, proxy confiável e limites de requisição.

### `_normalizar_origem(valor: str) -> str`

- Local: [_normalizar_origem](../app/security.py#L30)
- Responsabilidade: Função auxiliar que normaliza origem.

### `secure_cookie_for(request: Request) -> bool`

- Local: [secure_cookie_for](../app/security.py#L45)
- Responsabilidade: Mantém Secure no domínio e permite cookie apenas no host HTTP privado explícito.

### `_is_trusted_proxy(host: str) -> bool`

- Local: [_is_trusted_proxy](../app/security.py#L61)
- Responsabilidade: Função auxiliar responsável pelo fluxo “is trusted proxy”.

### `client_ip(request: Request) -> str`

- Local: [client_ip](../app/security.py#L69)
- Responsabilidade: Função auxiliar responsável pelo fluxo “client ip”.

### `_origem_permitida(request: Request) -> bool`

- Local: [_origem_permitida](../app/security.py#L85)
- Responsabilidade: Função auxiliar responsável pelo fluxo “origem permitida”.

### `__init__(self, app)`

- Local: [MaxBodySizeMiddleware.__init__](../app/security.py#L97)
- Responsabilidade: Função auxiliar responsável pelo fluxo “init”.

### `__call__(self, scope, receive, send)`

- Local: [MaxBodySizeMiddleware.__call__](../app/security.py#L100)
- Responsabilidade: Função auxiliar responsável pelo fluxo “call”.

### `limited_receive()`

- Local: [MaxBodySizeMiddleware.__call__.limited_receive](../app/security.py#L119)
- Responsabilidade: Função auxiliar responsável pelo fluxo “limited receive”.

### `dispatch(self, request: Request, call_next) -> Response`

- Local: [SecurityMiddleware.dispatch](../app/security.py#L148)
- Responsabilidade: Função auxiliar responsável pelo fluxo “dispatch”.

## `app/seed_massivo.py`

### `brl(valor: int | str) -> Decimal`

- Local: [brl](../app/seed_massivo.py#L60)
- Responsabilidade: Função auxiliar responsável pelo fluxo “brl”.

### `liquido(valor: Decimal, bandeira: str) -> Decimal`

- Local: [liquido](../app/seed_massivo.py#L64)
- Responsabilidade: Função auxiliar responsável pelo fluxo “liquido”.

### `dia_util(base: date, offset: int) -> date`

- Local: [dia_util](../app/seed_massivo.py#L69)
- Responsabilidade: Função auxiliar responsável pelo fluxo “dia util”.

### `limpar_massivo(db)`

- Local: [limpar_massivo](../app/seed_massivo.py#L76)
- Responsabilidade: Função auxiliar que limpa massivo.

### `usuario_padrao(db, cliente: ClienteBPO) -> Usuario`

- Local: [usuario_padrao](../app/seed_massivo.py#L103)
- Responsabilidade: Função auxiliar responsável pelo fluxo “usuario padrao”.

### `criar_receitas(db, cliente: ClienteBPO, usuario: Usuario)`

- Local: [criar_receitas](../app/seed_massivo.py#L112)
- Responsabilidade: Função auxiliar que cria receitas.

### `criar_lotes(db, cliente: ClienteBPO)`

- Local: [criar_lotes](../app/seed_massivo.py#L256)
- Responsabilidade: Função auxiliar que cria lotes.

### `criar_despesas(db, cliente: ClienteBPO, usuario: Usuario)`

- Local: [criar_despesas](../app/seed_massivo.py#L300)
- Responsabilidade: Função auxiliar que cria despesas.

### `criar_operacional(db, cliente: ClienteBPO, usuario: Usuario)`

- Local: [criar_operacional](../app/seed_massivo.py#L363)
- Responsabilidade: Função auxiliar que cria operacional.

### `main()`

- Local: [main](../app/seed_massivo.py#L432)
- Responsabilidade: Função auxiliar responsável pelo fluxo “main”.

## `app/services/alertas_service.py`

### `_proximo_vencimento(dia: int, referencia: date) -> date`

- Local: [_proximo_vencimento](../app/services/alertas_service.py#L10)
- Responsabilidade: Retorna a data de vencimento mais próxima a partir da referência.

### `_corpo_email(conta: ContaRecorrente, vencimento: date, hoje: date) -> str`

- Local: [_corpo_email](../app/services/alertas_service.py#L26)
- Responsabilidade: Função auxiliar responsável pelo fluxo “corpo email”.

### `verificar_e_enviar_alertas(db: Session) -> list[str]`

- Local: [verificar_e_enviar_alertas](../app/services/alertas_service.py#L72)
- Responsabilidade: Verifica todas as contas recorrentes ativas e envia e-mail quando a data de hoje está dentro da janela de antecedência do vencimento. Retorna lista de mensagens com o resultado de cada conta.

## `app/services/conciliacao_service.py`

### `ler_arquivo_extrato(caminho: str) -> pd.DataFrame`

- Local: [ler_arquivo_extrato](../app/services/conciliacao_service.py#L30)
- Responsabilidade: Le Excel ou CSV e normaliza colunas esperadas.

### `_extrair_coluna(df: pd.DataFrame, candidatas: list, padrao=None)`

- Local: [_extrair_coluna](../app/services/conciliacao_service.py#L40)
- Responsabilidade: Função auxiliar que extrai coluna.

### `_extrair_cpf_digitos_meio(cpf: str | None) -> str | None`

- Local: [_extrair_cpf_digitos_meio](../app/services/conciliacao_service.py#L47)
- Responsabilidade: Extrai os 6 dígitos do meio do CPF (posições 3–8 dos 11 dígitos).

### `_decimal_seguro(valor) -> Decimal`

- Local: [_decimal_seguro](../app/services/conciliacao_service.py#L57)
- Responsabilidade: Função auxiliar responsável pelo fluxo “decimal seguro”.

### `_norm_col(nome: str) -> str`

- Local: [_norm_col](../app/services/conciliacao_service.py#L61)
- Responsabilidade: Remove acentos, lowercase, substitui não-alfanuméricos por underscore.

### `_norm_texto(valor: str | None) -> str`

- Local: [_norm_texto](../app/services/conciliacao_service.py#L69)
- Responsabilidade: Função auxiliar responsável pelo fluxo “norm texto”.

### `_nome_bate(nome_atendimento: str | None, texto_extrato: str | None) -> bool`

- Local: [_nome_bate](../app/services/conciliacao_service.py#L78)
- Responsabilidade: Função auxiliar responsável pelo fluxo “nome bate”.

### `_procedimento_bate(atendimento: Atendimento, texto_extrato: str | None) -> bool`

- Local: [_procedimento_bate](../app/services/conciliacao_service.py#L86)
- Responsabilidade: Função auxiliar responsável pelo fluxo “procedimento bate”.

### `_contar_criterios(valor_ok: bool, data_ok: bool, nome_ok: bool, procedimento_ok: bool) -> int`

- Local: [_contar_criterios](../app/services/conciliacao_service.py#L100)
- Responsabilidade: Função auxiliar responsável pelo fluxo “contar criterios”.

### `limpar_divergencias_anteriores(db: Session, cliente_id: int, tipo: str)`

- Local: [limpar_divergencias_anteriores](../app/services/conciliacao_service.py#L104)
- Responsabilidade: Remove divergencias nao resolvidas antes de reprocessar o extrato.

### `limpar_movimentacoes_anteriores(db: Session, cliente_id: int, tipo: str)`

- Local: [limpar_movimentacoes_anteriores](../app/services/conciliacao_service.py#L114)
- Responsabilidade: Remove apenas movimentacoes importadas livres do mesmo tipo para o cliente.

### `_criar_movimentacao(db: Session, cliente_id: int, tipo: str, data_movimento, valor, origem_arquivo: str, digitos_cartao: str | None=None, descricao: str | None=None, sentido: str='recebimento')`

- Local: [_criar_movimentacao](../app/services/conciliacao_service.py#L131)
- Responsabilidade: Função auxiliar que cria movimentacao.

### `importar_lancamentos(db: Session, cliente_id: int, df: pd.DataFrame, *, substituir_pendentes: bool=True) -> int`

- Local: [importar_lancamentos](../app/services/conciliacao_service.py#L162)
- Responsabilidade: Importa Excel/CSV; permite inclusão sem substituir os lançamentos existentes.

### `_col(*names)`

- Local: [importar_lancamentos._col](../app/services/conciliacao_service.py#L167)
- Responsabilidade: Função auxiliar responsável pelo fluxo “col”.

### `_v(col, row=row)`

- Local: [importar_lancamentos._v](../app/services/conciliacao_service.py#L242)
- Responsabilidade: Função auxiliar responsável pelo fluxo “v”.

### `parse_ofx(caminho: str) -> pd.DataFrame`

- Local: [parse_ofx](../app/services/conciliacao_service.py#L333)
- Responsabilidade: Lê o OFX e preserva identificação da conta e saldo informado pelo banco.

### `_tag(t)`

- Local: [parse_ofx._tag](../app/services/conciliacao_service.py#L347)
- Responsabilidade: Função auxiliar responsável pelo fluxo “tag”.

### `_tag_global(tag)`

- Local: [parse_ofx._tag_global](../app/services/conciliacao_service.py#L371)
- Responsabilidade: Função auxiliar responsável pelo fluxo “tag global”.

### `score_sugestao(movimentacao: MovimentacaoBancaria, atendimento: Atendimento)`

- Local: [score_sugestao](../app/services/conciliacao_service.py#L399)
- Responsabilidade: Função auxiliar responsável pelo fluxo “score sugestao”.

### `buscar_sugestao(movimentacao: MovimentacaoBancaria, receitas: list)`

- Local: [buscar_sugestao](../app/services/conciliacao_service.py#L411)
- Responsabilidade: Retorna o melhor Atendimento candidato para a movimentacao, ou None.

### `_selecionar_taxa_por_parcelas(taxas: list[TaxaCartaoCliente], parcelas: int) -> TaxaCartaoCliente | None`

- Local: [_selecionar_taxa_por_parcelas](../app/services/conciliacao_service.py#L475)
- Responsabilidade: Aplica a prioridade de faixas personalizadas e padrões sobre uma lista de taxas.

### `_taxa_cartao_para_parcelas(db: Session, cliente_id: int, bandeira: str | None, parcelas: int) -> TaxaCartaoCliente | None`

- Local: [_taxa_cartao_para_parcelas](../app/services/conciliacao_service.py#L511)
- Responsabilidade: Carrega as taxas ativas da bandeira e seleciona a faixa das parcelas.

### `conciliar_cartao(db: Session, cliente_id: int, df: pd.DataFrame, origem_arquivo: str) -> Tuple[List[dict], List[dict]]`

- Local: [conciliar_cartao](../app/services/conciliacao_service.py#L533)
- Responsabilidade: Função auxiliar que concilia cartao.

### `conciliar_pix_ted(db: Session, cliente_id: int, df: pd.DataFrame, origem_arquivo: str) -> Tuple[List[dict], List[dict]]`

- Local: [conciliar_pix_ted](../app/services/conciliacao_service.py#L648)
- Responsabilidade: Função auxiliar que concilia pix ted.

### `limpar_movimentacoes_banco_livres(db: Session, cliente_id: int)`

- Local: [limpar_movimentacoes_banco_livres](../app/services/conciliacao_service.py#L726)
- Responsabilidade: Remove apenas movimentacoes bancarias ainda sem vinculo de conciliacao.

### `importar_movimentacoes_bancarias(db: Session, cliente_id: int, df: pd.DataFrame, origem_arquivo: str, conta_bancaria_id: int | None=None) -> dict`

- Local: [importar_movimentacoes_bancarias](../app/services/conciliacao_service.py#L743)
- Responsabilidade: Importa o extrato da conta corrente como movimentacoes bancarias livres. Creditos ficam disponiveis para Pix/TED ou para vincular com lotes de cartao. Debitos ficam disponiveis para contas a pagar.

### `gerar_transferencias_cartao(db: Session, cliente_id: int) -> int`

- Local: [gerar_transferencias_cartao](../app/services/conciliacao_service.py#L823)
- Responsabilidade: Agrupa Atendimentos conciliados por cartão em TransferenciaCartao por (data_credito, bandeira_cartao). Cria ou atualiza os registros. Retorna o número de novos lotes criados.

### `buscar_sugestao_venda(venda: 'VendaCartao', atendimentos: list) -> dict | None`

- Local: [buscar_sugestao_venda](../app/services/conciliacao_service.py#L887)
- Responsabilidade: Retorna o melhor Atendimento para uma VendaCartao, ou None.

### `importar_vendas_cartao(db: Session, cliente_id: int, df: pd.DataFrame, origem_arquivo: str) -> int`

- Local: [importar_vendas_cartao](../app/services/conciliacao_service.py#L945)
- Responsabilidade: Importa extrato da maquininha como VendaCartao individuais. Colunas esperadas: data_venda, data_pagamento, bandeira, ultimos_digitos, nome_portador, valor_bruto, taxa_percentual, valor_liquido, parcelas.

### `_col(*names)`

- Local: [importar_vendas_cartao._col](../app/services/conciliacao_service.py#L959)
- Responsabilidade: Função auxiliar responsável pelo fluxo “col”.

### `_v(col)`

- Local: [importar_vendas_cartao._v](../app/services/conciliacao_service.py#L1000)
- Responsabilidade: Função auxiliar responsável pelo fluxo “v”.

### `fechar_lote_dia(db: Session, cliente_id: int, data_pagamento, bandeira: str | None) -> TransferenciaCartao`

- Local: [fechar_lote_dia](../app/services/conciliacao_service.py#L1068)
- Responsabilidade: Agrupa as VendaCartao pendentes de um dia/bandeira em um TransferenciaCartao (lote). Retorna o lote criado ou atualizado.

### `importar_extrato_conta_corrente(db: Session, cliente_id: int, df: pd.DataFrame, origem_arquivo: str) -> dict`

- Local: [importar_extrato_conta_corrente](../app/services/conciliacao_service.py#L1131)
- Responsabilidade: Importa extrato da conta corrente como ExtratoLinhaBancaria. A conciliacao fica pendente para confirmacao individual ou em lote.

## `app/services/email_service.py`

### `enviar_email(destinatario: str, assunto: str, corpo_html: str) -> None`

- Local: [enviar_email](../app/services/email_service.py#L9)
- Responsabilidade: Envia e-mail via SMTP com TLS. Lança exceção se SMTP não estiver configurado.

## `app/services/fechamento_service.py`

### `calcular_fechamento(db: Session, cliente_id: int, data: date, saldo_conta: Decimal) -> dict`

- Local: [calcular_fechamento](../app/services/fechamento_service.py#L12)
- Responsabilidade: Calcula totais do dia e retorna um dicionário com os valores e texto para o cliente. Não salva no banco — apenas calcula.

### `gerar_texto_cliente(cliente: ClienteBPO, data: date, dados: dict, observacao: str='') -> str`

- Local: [gerar_texto_cliente](../app/services/fechamento_service.py#L55)
- Responsabilidade: Gera o texto formatado para enviar ao cliente via WhatsApp/e-mail.

### `fmt(valor)`

- Local: [gerar_texto_cliente.fmt](../app/services/fechamento_service.py#L58)
- Responsabilidade: Função auxiliar responsável pelo fluxo “fmt”.

### `salvar_fechamento(db: Session, cliente_id: int, data: date, dados: dict, observacao: str, gerado_por_id: int) -> FechamentoDiario`

- Local: [salvar_fechamento](../app/services/fechamento_service.py#L84)
- Responsabilidade: Persiste o fechamento no banco. Substitui se já existir para o mesmo dia.

## `app/services/log_service.py`

### `registrar(db: Session, acao: str, modulo: str, usuario_id: int | None=None, usuario_nome: str='', cliente_id: int | None=None, cliente_nome: str | None=None, detalhes: str | None=None, ip: str | None=None) -> None`

- Local: [registrar](../app/services/log_service.py#L10)
- Responsabilidade: Função auxiliar que registra .

## `app/services/recebimento_service.py`

### `prever_recebimento(data_atendimento: date, dias: int, forma: str | None, antecipa: bool) -> date`

- Local: [prever_recebimento](../app/services/recebimento_service.py#L4)
- Responsabilidade: Crédito antecipado vence em D+2 úteis (segunda a sexta), em todas as parcelas.

## `app/utils.py`

### `cliente_ativo(request: Request, cliente_id: Optional[int]) -> Optional[int]`

- Local: [cliente_ativo](../app/utils.py#L23)
- Responsabilidade: Retorna cliente_id do param URL; se None, lê do cookie 'cliente_ativo'.

### `salvar_upload_temporario(arquivo: UploadFile, extensoes_permitidas: set[str], max_bytes: int=MAX_UPLOAD_BYTES) -> tuple[str, str, str]`

- Local: [salvar_upload_temporario](../app/utils.py#L32)
- Responsabilidade: Valida extensao/tamanho e salva o upload em arquivo temporario.

### `_validar_assinatura(ext: str, inicio: bytes) -> None`

- Local: [_validar_assinatura](../app/utils.py#L85)
- Responsabilidade: Função auxiliar que valida assinatura.

## `docs/generate_manual_pdf.py`

### `__init__(self, tag: str, attrs=None, parent=None)`

- Local: [Node.__init__](../docs/generate_manual_pdf.py#L33)
- Responsabilidade: Função auxiliar responsável pelo fluxo “init”.

### `text(self) -> str`

- Local: [Node.text](../docs/generate_manual_pdf.py#L39)
- Responsabilidade: Função auxiliar responsável pelo fluxo “text”.

### `__init__(self)`

- Local: [TreeParser.__init__](../docs/generate_manual_pdf.py#L47)
- Responsabilidade: Função auxiliar responsável pelo fluxo “init”.

### `handle_starttag(self, tag, attrs)`

- Local: [TreeParser.handle_starttag](../docs/generate_manual_pdf.py#L52)
- Responsabilidade: Função auxiliar responsável pelo fluxo “handle starttag”.

### `handle_startendtag(self, tag, attrs)`

- Local: [TreeParser.handle_startendtag](../docs/generate_manual_pdf.py#L58)
- Responsabilidade: Função auxiliar responsável pelo fluxo “handle startendtag”.

### `handle_endtag(self, tag)`

- Local: [TreeParser.handle_endtag](../docs/generate_manual_pdf.py#L61)
- Responsabilidade: Função auxiliar responsável pelo fluxo “handle endtag”.

### `handle_data(self, data)`

- Local: [TreeParser.handle_data](../docs/generate_manual_pdf.py#L69)
- Responsabilidade: Função auxiliar responsável pelo fluxo “handle data”.

### `find_all(node: Node, tag: str) -> list[Node]`

- Local: [find_all](../docs/generate_manual_pdf.py#L81)
- Responsabilidade: Função auxiliar responsável pelo fluxo “find all”.

### `direct_nodes(node: Node, tags: set[str]) -> list[Node]`

- Local: [direct_nodes](../docs/generate_manual_pdf.py#L91)
- Responsabilidade: Função auxiliar responsável pelo fluxo “direct nodes”.

### `safe_text(text: str) -> str`

- Local: [safe_text](../docs/generate_manual_pdf.py#L95)
- Responsabilidade: Função auxiliar responsável pelo fluxo “safe text”.

### `__init__(self, filename)`

- Local: [ManualDoc.__init__](../docs/generate_manual_pdf.py#L117)
- Responsabilidade: Função auxiliar responsável pelo fluxo “init”.

### `draw_page(self, canvas, doc)`

- Local: [ManualDoc.draw_page](../docs/generate_manual_pdf.py#L124)
- Responsabilidade: Função auxiliar responsável pelo fluxo “draw page”.

### `make_table(node: Node)`

- Local: [make_table](../docs/generate_manual_pdf.py#L143)
- Responsabilidade: Função auxiliar responsável pelo fluxo “make table”.

### `list_flow(node: Node)`

- Local: [list_flow](../docs/generate_manual_pdf.py#L169)
- Responsabilidade: Função auxiliar responsável pelo fluxo “list flow”.

### `section_story(section: Node)`

- Local: [section_story](../docs/generate_manual_pdf.py#L178)
- Responsabilidade: Função auxiliar responsável pelo fluxo “section story”.

### `build()`

- Local: [build](../docs/generate_manual_pdf.py#L231)
- Responsabilidade: Função auxiliar responsável pelo fluxo “build”.

## `scripts/audit_connections.py`

Audita conexao, schema, FKs, ORM/criptografia e telas GET principais.

### `aguardar_aplicacao(base_url: str, timeout_seconds: int=30) -> None`

- Local: [aguardar_aplicacao](../scripts/audit_connections.py#L22)
- Responsabilidade: Aguarda o Uvicorn aceitar conexões antes das verificações de rota.

## `scripts/backup_crypto.py`

Cifra/decifra backups em streaming com uma chave exclusiva.

### `_backup_key() -> bytes`

- Local: [_backup_key](../scripts/backup_crypto.py#L23)
- Responsabilidade: Função auxiliar responsável pelo fluxo “backup key”.

### `_temporary_target(target: Path)`

- Local: [_temporary_target](../scripts/backup_crypto.py#L32)
- Responsabilidade: Função auxiliar responsável pelo fluxo “temporary target”.

### `encrypt(source: Path, target: Path) -> None`

- Local: [encrypt](../scripts/backup_crypto.py#L42)
- Responsabilidade: Função auxiliar que cifra .

### `decrypt(source: Path, target: Path) -> None`

- Local: [decrypt](../scripts/backup_crypto.py#L62)
- Responsabilidade: Função auxiliar que decifra .

## `scripts/generate_function_reference.py`

Gera uma referência navegável de todas as funções Python mantidas no projeto.

### `python_files() -> list[Path]`

- Local: [python_files](../scripts/generate_function_reference.py#L66)
- Responsabilidade: Retorna os arquivos Python versionáveis, ignorando ambientes e dados locais.

### `route_of(node: ast.FunctionDef | ast.AsyncFunctionDef, prefix: str='') -> str | None`

- Local: [route_of](../scripts/generate_function_reference.py#L82)
- Responsabilidade: Extrai método e caminho de um decorator FastAPI, quando houver.

### `router_prefix(tree: ast.Module) -> str`

- Local: [router_prefix](../scripts/generate_function_reference.py#L96)
- Responsabilidade: Lê o prefixo declarado em `router = APIRouter(prefix=...)`.

### `signature_of(node: ast.FunctionDef | ast.AsyncFunctionDef) -> str`

- Local: [signature_of](../scripts/generate_function_reference.py#L109)
- Responsabilidade: Reconstrói uma assinatura curta sem copiar o corpo da função.

### `humanize(identifier: str) -> str`

- Local: [humanize](../scripts/generate_function_reference.py#L118)
- Responsabilidade: Converte um identificador snake_case em texto legível.

### `inferred_description(node: ast.FunctionDef | ast.AsyncFunctionDef, route: str | None) -> str`

- Local: [inferred_description](../scripts/generate_function_reference.py#L123)
- Responsabilidade: Produz uma descrição previsível quando a função ainda não possui docstring.

### `functions_in(path: Path) -> tuple[ast.Module, list[tuple[ast.FunctionDef | ast.AsyncFunctionDef, str]]]`

- Local: [functions_in](../scripts/generate_function_reference.py#L142)
- Responsabilidade: Lista funções e métodos com o nome qualificado da classe quando aplicável.

### `__init__(self) -> None`

- Local: [functions_in.FunctionVisitor.__init__](../scripts/generate_function_reference.py#L150)
- Responsabilidade: Função auxiliar responsável pelo fluxo “init”.

### `visit_ClassDef(self, node: ast.ClassDef) -> None`

- Local: [functions_in.FunctionVisitor.visit_ClassDef](../scripts/generate_function_reference.py#L153)
- Responsabilidade: Função auxiliar responsável pelo fluxo “visit ClassDef”.

### `_visit_function(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None`

- Local: [functions_in.FunctionVisitor._visit_function](../scripts/generate_function_reference.py#L158)
- Responsabilidade: Função auxiliar responsável pelo fluxo “visit function”.

### `generate() -> str`

- Local: [generate](../scripts/generate_function_reference.py#L172)
- Responsabilidade: Monta o Markdown completo e determinístico da referência.

### `main() -> int`

- Local: [main](../scripts/generate_function_reference.py#L210)
- Responsabilidade: Gera o arquivo ou valida se a versão commitada está atualizada.

## `scripts/setup_local_env.py`

Cria um .env local consistente sem exibir segredos no terminal.

### `_key() -> str`

- Local: [_key](../scripts/setup_local_env.py#L15)
- Responsabilidade: Função auxiliar responsável pelo fluxo “key”.

## `scripts/verify_maquininha_flow.py`

Valida adicionar, editar e desativar maquininha sem deixar dados de teste.

### `aguardar_aplicacao(base_url: str, timeout_seconds: int=30) -> None`

- Local: [aguardar_aplicacao](../scripts/verify_maquininha_flow.py#L18)
- Responsabilidade: Aguarda o servidor aceitar conexões antes de iniciar o fluxo mutável.

## `seed.py`

Script de seed com dados de exemplo. Execute da raiz do projeto: docker-compose exec web python seed.py Ou fora do Docker (com banco acessivel): python seed.py

### `limpar()`

- Local: [limpar](../seed.py#L55)
- Responsabilidade: Remove dados existentes para recomeçar do zero.

### `criar_usuarios()`

- Local: [criar_usuarios](../seed.py#L73)
- Responsabilidade: Função auxiliar que cria usuarios.

### `criar_clientes(usuarios)`

- Local: [criar_clientes](../seed.py#L110)
- Responsabilidade: Função auxiliar que cria clientes.

### `criar_rotinas_hoje(clientes)`

- Local: [criar_rotinas_hoje](../seed.py#L196)
- Responsabilidade: Função auxiliar que cria rotinas hoje.

### `criar_contas_pagar_exemplo(clientes)`

- Local: [criar_contas_pagar_exemplo](../seed.py#L227)
- Responsabilidade: Função auxiliar que cria contas pagar exemplo.

### `criar_cadastros_financeiros_exemplo(clientes)`

- Local: [criar_cadastros_financeiros_exemplo](../seed.py#L302)
- Responsabilidade: Função auxiliar que cria cadastros financeiros exemplo.

### `criar_fechamentos_exemplo(clientes, usuarios)`

- Local: [criar_fechamentos_exemplo](../seed.py#L374)
- Responsabilidade: Função auxiliar que cria fechamentos exemplo.

### `criar_conciliacao_exemplo(clientes, usuarios)`

- Local: [criar_conciliacao_exemplo](../seed.py#L400)
- Responsabilidade: Cria um cenario visual rico para a tela de conciliacao.

## `seed_bioma.py`

Seed de dados BIOMA (cliente_id=9) — 3 ciclos de teste completos Cobre o fluxo completo do sistema: Lançamentos → Conc. Cartão → Conc. Banco (lotes) → Fechamento Lançamentos → Conc. Banco (PIX/TED) → Fechamento Saídas banco → Conc. Banco (saídas) → Fechamento (despesas) Ciclo 1 — 02-06/Jun Visa + PIX/TED Ciclo 2 — 09-13/Jun Mastercard + PIX/TED Ciclo 3 — 16-20/Jun Elo + PIX/TED

### `liq(bruto: Decimal, bandeira: str) -> Decimal`

- Local: [liq](../seed_bioma.py#L33)
- Responsabilidade: Função auxiliar responsável pelo fluxo “liq”.

### `at_cartao(data, paciente, cpf, valor, dig, bandeira, medico, servico, data_prev)`

- Local: [at_cartao](../seed_bioma.py#L38)
- Responsabilidade: Função auxiliar responsável pelo fluxo “at cartao”.

### `at_pix(data, paciente, cpf, valor, medico, servico, forma=FormaPagamento.pix)`

- Local: [at_pix](../seed_bioma.py#L63)
- Responsabilidade: Função auxiliar responsável pelo fluxo “at pix”.

### `venda(data_venda, data_pag, bandeira, valor_bruto, dig, descricao='Consulta')`

- Local: [venda](../seed_bioma.py#L84)
- Responsabilidade: Função auxiliar responsável pelo fluxo “venda”.

### `mov_rec(data, valor, descricao, cpf_meio=None)`

- Local: [mov_rec](../seed_bioma.py#L102)
- Responsabilidade: Função auxiliar responsável pelo fluxo “mov rec”.

### `mov_pag(data, valor, descricao)`

- Local: [mov_pag](../seed_bioma.py#L116)
- Responsabilidade: Função auxiliar responsável pelo fluxo “mov pag”.

### `main()`

- Local: [main](../seed_bioma.py#L129)
- Responsabilidade: Função auxiliar responsável pelo fluxo “main”.

## `seed_conciliacao_cartao.py`

Seed: dados de teste para Conciliação Cartão + Conciliação Banco. Cria para PRESTI (id=1) e REF DOR (id=2): - VendaCartao pendentes → para testar a tela de conciliação cartão - VendaCartao já fechadas em TransferenciaCartao (lotes) - MovimentacaoBancaria créditos do banco que batem com os lotes → para testar o match automático na conciliação banco

### `liquido(bruto: Decimal, bandeira: str) -> Decimal`

- Local: [liquido](../seed_conciliacao_cartao.py#L55)
- Responsabilidade: Função auxiliar responsável pelo fluxo “liquido”.

### `add_venda(cliente_id, data_venda, data_pagamento, portador, digitos, bandeira, bruto, status=StatusVendaCartao.pendente, lote_id=None, origem='seed_teste.csv')`

- Local: [add_venda](../seed_conciliacao_cartao.py#L59)
- Responsabilidade: Função auxiliar responsável pelo fluxo “add venda”.

### `add_lote(cliente_id, data, bandeira, vendas)`

- Local: [add_lote](../seed_conciliacao_cartao.py#L82)
- Responsabilidade: Função auxiliar responsável pelo fluxo “add lote”.

### `add_credito_banco(cliente_id, data, valor, descricao, lote_id=None)`

- Local: [add_credito_banco](../seed_conciliacao_cartao.py#L102)
- Responsabilidade: Função auxiliar responsável pelo fluxo “add credito banco”.

## `seed_exemplos_conciliacao.py`

Seed: exemplos completos para testar a Conciliação de Cartão. Cria Atendimentos (lançamentos) com forma_pagamento=cartao_credito que correspondem às VendaCartao pendentes já existentes. Cenários cobertos por cliente: PRESTI (id=1) — 6 vendas pendentes: • 4 sugestao_pronta (verde) — valor exato + dígitos + data próxima • 1 revisar (amarelo) — diferença de R$2,00 no valor • 1 sem sugestão — para testar busca manual / criar lançamento REF DOR (id=2) — 3 vendas pendentes: • 2 sugestao_pronta (verde) • 1 revisar (amarelo) — diferença de R$2,00 Execute: docker exec bpo-financeiro-web-1 python seed_exemplos_conciliacao.py

### `liquido(bruto: Decimal, taxa_pct: Decimal) -> Decimal`

- Local: [liquido](../seed_exemplos_conciliacao.py#L45)
- Responsabilidade: Função auxiliar responsável pelo fluxo “liquido”.

### `add_at(cliente_id, data_atend, nome, bandeira, digitos, valor, data_prev, taxa=None, obs=None)`

- Local: [add_at](../seed_exemplos_conciliacao.py#L52)
- Responsabilidade: Função auxiliar responsável pelo fluxo “add at”.

## `tests/test_edicao_receber.py`

### `dados(monkeypatch)`

- Local: [dados](../tests/test_edicao_receber.py#L18)
- Responsabilidade: Função auxiliar responsável pelo fluxo “dados”.

### `editar(dados, **kwargs)`

- Local: [editar](../tests/test_edicao_receber.py#L36)
- Responsabilidade: Função auxiliar que edita .

### `test_editar_todos_campos_e_rateio(dados)`

- Local: [test_editar_todos_campos_e_rateio](../tests/test_edicao_receber.py#L45)
- Responsabilidade: Função auxiliar responsável pelo fluxo “test editar todos campos e rateio”.

### `test_edicao_invalida_preserva_dados(dados, kwargs)`

- Local: [test_edicao_invalida_preserva_dados](../tests/test_edicao_receber.py#L82)
- Responsabilidade: Função auxiliar responsável pelo fluxo “test edicao invalida preserva dados”.

### `test_rateio_rejeita_centro_de_outro_cliente(dados)`

- Local: [test_rateio_rejeita_centro_de_outro_cliente](../tests/test_edicao_receber.py#L89)
- Responsabilidade: Função auxiliar responsável pelo fluxo “test rateio rejeita centro de outro cliente”.

### `test_remover_rateio_e_trocar_cartao_por_boleto(dados)`

- Local: [test_remover_rateio_e_trocar_cartao_por_boleto](../tests/test_edicao_receber.py#L99)
- Responsabilidade: Função auxiliar responsável pelo fluxo “test remover rateio e trocar cartao por boleto”.

### `test_conciliado_e_outro_cliente_nao_sao_editados(dados)`

- Local: [test_conciliado_e_outro_cliente_nao_sao_editados](../tests/test_edicao_receber.py#L112)
- Responsabilidade: Função auxiliar responsável pelo fluxo “test conciliado e outro cliente nao sao editados”.

### `test_formulario_expoe_campos_e_selecoes(dados)`

- Local: [test_formulario_expoe_campos_e_selecoes](../tests/test_edicao_receber.py#L124)
- Responsabilidade: Função auxiliar responsável pelo fluxo “test formulario expoe campos e selecoes”.

## `tests/test_field_classification.py`

### `test_basic_registration_fields_are_plaintext() -> None`

- Local: [test_basic_registration_fields_are_plaintext](../tests/test_field_classification.py#L13)
- Responsabilidade: Função auxiliar responsável pelo fluxo “test basic registration fields are plaintext”.

### `test_clinical_banking_and_financial_fields_remain_encrypted() -> None`

- Local: [test_clinical_banking_and_financial_fields_remain_encrypted](../tests/test_field_classification.py#L32)
- Responsabilidade: Função auxiliar responsável pelo fluxo “test clinical banking and financial fields remain encrypted”.

## `tests/test_lotes_financeiros.py`

### `db(monkeypatch)`

- Local: [db](../tests/test_lotes_financeiros.py#L24)
- Responsabilidade: Função auxiliar responsável pelo fluxo “db”.

### `conta(db, **kwargs)`

- Local: [conta](../tests/test_lotes_financeiros.py#L41)
- Responsabilidade: Função auxiliar responsável pelo fluxo “conta”.

### `aplicar(db, ids, **kwargs)`

- Local: [aplicar](../tests/test_lotes_financeiros.py#L48)
- Responsabilidade: Função auxiliar que aplica .

### `test_edicao_lote_categoria_centro_e_status(db)`

- Local: [test_edicao_lote_categoria_centro_e_status](../tests/test_lotes_financeiros.py#L55)
- Responsabilidade: Função auxiliar responsável pelo fluxo “test edicao lote categoria centro e status”.

### `test_lote_pula_conta_paga_e_aplica_no_restante(db)`

- Local: [test_lote_pula_conta_paga_e_aplica_no_restante](../tests/test_lotes_financeiros.py#L70)
- Responsabilidade: Função auxiliar responsável pelo fluxo “test lote pula conta paga e aplica no restante”.

### `test_lote_rejeita_centro_de_outro_cliente_e_baixa_manual(db)`

- Local: [test_lote_rejeita_centro_de_outro_cliente_e_baixa_manual](../tests/test_lotes_financeiros.py#L80)
- Responsabilidade: Função auxiliar responsável pelo fluxo “test lote rejeita centro de outro cliente e baixa manual”.

### `test_lote_rejeita_selecao_fora_do_acesso(db, monkeypatch)`

- Local: [test_lote_rejeita_selecao_fora_do_acesso](../tests/test_lotes_financeiros.py#L91)
- Responsabilidade: Função auxiliar responsável pelo fluxo “test lote rejeita selecao fora do acesso”.

### `test_excluir_lote_contas(db)`

- Local: [test_excluir_lote_contas](../tests/test_lotes_financeiros.py#L100)
- Responsabilidade: Função auxiliar responsável pelo fluxo “test excluir lote contas”.

### `test_importacao_adiciona_sem_apagar_pendentes(db)`

- Local: [test_importacao_adiciona_sem_apagar_pendentes](../tests/test_lotes_financeiros.py#L106)
- Responsabilidade: Função auxiliar responsável pelo fluxo “test importacao adiciona sem apagar pendentes”.

### `test_exclusao_receber_bloqueia_conciliado_e_exclui_pendente(db)`

- Local: [test_exclusao_receber_bloqueia_conciliado_e_exclui_pendente](../tests/test_lotes_financeiros.py#L117)
- Responsabilidade: Função auxiliar responsável pelo fluxo “test exclusao receber bloqueia conciliado e exclui pendente”.

### `test_exclusao_receber_bloqueia_vinculo_mesmo_pendente(db)`

- Local: [test_exclusao_receber_bloqueia_vinculo_mesmo_pendente](../tests/test_lotes_financeiros.py#L128)
- Responsabilidade: Função auxiliar responsável pelo fluxo “test exclusao receber bloqueia vinculo mesmo pendente”.

### `test_exclusao_lote_preserva_pagamento_parcial(db)`

- Local: [test_exclusao_lote_preserva_pagamento_parcial](../tests/test_lotes_financeiros.py#L138)
- Responsabilidade: Função auxiliar responsável pelo fluxo “test exclusao lote preserva pagamento parcial”.

### `test_exclusao_lote_pula_conta_com_conciliacao_bancaria(db)`

- Local: [test_exclusao_lote_pula_conta_com_conciliacao_bancaria](../tests/test_lotes_financeiros.py#L147)
- Responsabilidade: Função auxiliar responsável pelo fluxo “test exclusao lote pula conta com conciliacao bancaria”.

### `test_modelo_disponivel_importa_parcelas(db)`

- Local: [test_modelo_disponivel_importa_parcelas](../tests/test_lotes_financeiros.py#L156)
- Responsabilidade: Função auxiliar responsável pelo fluxo “test modelo disponivel importa parcelas”.

### `test_filtros_em_aberto_vencidas_e_a_vencer(db, monkeypatch)`

- Local: [test_filtros_em_aberto_vencidas_e_a_vencer](../tests/test_lotes_financeiros.py#L162)
- Responsabilidade: Função auxiliar responsável pelo fluxo “test filtros em aberto vencidas e a vencer”.

### `test_telas_renderizam_selecao_e_acoes(db, modulo, path, funcao)`

- Local: [test_telas_renderizam_selecao_e_acoes](../tests/test_lotes_financeiros.py#L180)
- Responsabilidade: Função auxiliar responsável pelo fluxo “test telas renderizam selecao e acoes”.

### `recorrencia(db)`

- Local: [recorrencia](../tests/test_lotes_financeiros.py#L193)
- Responsabilidade: Função auxiliar responsável pelo fluxo “recorrencia”.

### `excluir_recorrente(db, item, escopo='somente', cliente_id=1)`

- Local: [excluir_recorrente](../tests/test_lotes_financeiros.py#L202)
- Responsabilidade: Função auxiliar que exclui recorrente.

### `test_excluir_primeiro_preserva_e_reagrupa_recorrencia(db)`

- Local: [test_excluir_primeiro_preserva_e_reagrupa_recorrencia](../tests/test_lotes_financeiros.py#L210)
- Responsabilidade: Função auxiliar responsável pelo fluxo “test excluir primeiro preserva e reagrupa recorrencia”.

### `test_excluir_ocorrencia_intermediaria_preserva_demais(db)`

- Local: [test_excluir_ocorrencia_intermediaria_preserva_demais](../tests/test_lotes_financeiros.py#L220)
- Responsabilidade: Função auxiliar responsável pelo fluxo “test excluir ocorrencia intermediaria preserva demais”.

### `test_excluir_toda_recorrencia_a_partir_de_qualquer_ocorrencia(db)`

- Local: [test_excluir_toda_recorrencia_a_partir_de_qualquer_ocorrencia](../tests/test_lotes_financeiros.py#L228)
- Responsabilidade: Função auxiliar responsável pelo fluxo “test excluir toda recorrencia a partir de qualquer ocorrencia”.

### `test_excluir_recorrencia_pula_pagos_e_exclui_restante(db)`

- Local: [test_excluir_recorrencia_pula_pagos_e_exclui_restante](../tests/test_lotes_financeiros.py#L235)
- Responsabilidade: Função auxiliar responsável pelo fluxo “test excluir recorrencia pula pagos e exclui restante”.

### `test_excluir_recorrencia_toda_paga_nao_exclui_nada(db)`

- Local: [test_excluir_recorrencia_toda_paga_nao_exclui_nada](../tests/test_lotes_financeiros.py#L246)
- Responsabilidade: Função auxiliar responsável pelo fluxo “test excluir recorrencia toda paga nao exclui nada”.

### `test_exclusao_lote_de_recorrentes_preserva_grupo_restante(db)`

- Local: [test_exclusao_lote_de_recorrentes_preserva_grupo_restante](../tests/test_lotes_financeiros.py#L255)
- Responsabilidade: Função auxiliar responsável pelo fluxo “test exclusao lote de recorrentes preserva grupo restante”.

### `test_exclusao_recorrencia_rejeita_cliente_incorreto_e_escopo_invalido(db)`

- Local: [test_exclusao_recorrencia_rejeita_cliente_incorreto_e_escopo_invalido](../tests/test_lotes_financeiros.py#L264)
- Responsabilidade: Função auxiliar responsável pelo fluxo “test exclusao recorrencia rejeita cliente incorreto e escopo invalido”.

### `test_tela_oferece_exclusao_individual_e_recorrencia(db)`

- Local: [test_tela_oferece_exclusao_individual_e_recorrencia](../tests/test_lotes_financeiros.py#L274)
- Responsabilidade: Função auxiliar responsável pelo fluxo “test tela oferece exclusao individual e recorrencia”.

### `editar_valor(db, item, escopo='somente', **kwargs)`

- Local: [editar_valor](../tests/test_lotes_financeiros.py#L284)
- Responsabilidade: Função auxiliar que edita valor.

### `test_editar_valor_somente_ocorrencia(db)`

- Local: [test_editar_valor_somente_ocorrencia](../tests/test_lotes_financeiros.py#L293)
- Responsabilidade: Função auxiliar responsável pelo fluxo “test editar valor somente ocorrencia”.

### `test_editar_valor_proximos_preserva_anteriores_datas_e_outros_campos(db)`

- Local: [test_editar_valor_proximos_preserva_anteriores_datas_e_outros_campos](../tests/test_lotes_financeiros.py#L299)
- Responsabilidade: Função auxiliar responsável pelo fluxo “test editar valor proximos preserva anteriores datas e outros campos”.

### `test_editar_proximos_pula_pagamento_parcial_e_aplica_no_restante(db)`

- Local: [test_editar_proximos_pula_pagamento_parcial_e_aplica_no_restante](../tests/test_lotes_financeiros.py#L314)
- Responsabilidade: Função auxiliar responsável pelo fluxo “test editar proximos pula pagamento parcial e aplica no restante”.

### `test_editar_somente_bloqueia_lancamento_com_pagamento_parcial(db)`

- Local: [test_editar_somente_bloqueia_lancamento_com_pagamento_parcial](../tests/test_lotes_financeiros.py#L326)
- Responsabilidade: Função auxiliar responsável pelo fluxo “test editar somente bloqueia lancamento com pagamento parcial”.

### `test_editar_valor_recalcula_rateios_sem_perder_centavos(db)`

- Local: [test_editar_valor_recalcula_rateios_sem_perder_centavos](../tests/test_lotes_financeiros.py#L335)
- Responsabilidade: Função auxiliar responsável pelo fluxo “test editar valor recalcula rateios sem perder centavos”.

### `test_editar_valor_rejeita_escopo_invalido(db)`

- Local: [test_editar_valor_rejeita_escopo_invalido](../tests/test_lotes_financeiros.py#L351)
- Responsabilidade: Função auxiliar responsável pelo fluxo “test editar valor rejeita escopo invalido”.

### `test_recorrencia_copia_dados_rateios_e_anexo(db, monkeypatch, tmp_path, intervalo, dias, esperadas)`

- Local: [test_recorrencia_copia_dados_rateios_e_anexo](../tests/test_lotes_financeiros.py#L364)
- Responsabilidade: Função auxiliar responsável pelo fluxo “test recorrencia copia dados rateios e anexo”.

### `upload(*args)`

- Local: [test_recorrencia_copia_dados_rateios_e_anexo.upload](../tests/test_lotes_financeiros.py#L373)
- Responsabilidade: Função auxiliar responsável pelo fluxo “upload”.

### `rateios(item)`

- Local: [test_recorrencia_copia_dados_rateios_e_anexo.rateios](../tests/test_lotes_financeiros.py#L393)
- Responsabilidade: Função auxiliar responsável pelo fluxo “rateios”.

### `test_edicao_rateio_invalido_nao_altera_conta(db)`

- Local: [test_edicao_rateio_invalido_nao_altera_conta](../tests/test_lotes_financeiros.py#L413)
- Responsabilidade: Função auxiliar responsável pelo fluxo “test edicao rateio invalido nao altera conta”.

### `test_formulario_edicao_exibe_rateios(db)`

- Local: [test_formulario_edicao_exibe_rateios](../tests/test_lotes_financeiros.py#L425)
- Responsabilidade: Função auxiliar responsável pelo fluxo “test formulario edicao exibe rateios”.

## `tests/test_recebimento.py`

### `test_antecipacao_dois_dias_uteis(dia, esperado, intervalo)`

- Local: [test_antecipacao_dois_dias_uteis](../tests/test_recebimento.py#L10)
- Responsabilidade: Função auxiliar responsável pelo fluxo “test antecipacao dois dias uteis”.

### `test_credito_sem_antecipacao_preserva_prazo()`

- Local: [test_credito_sem_antecipacao_preserva_prazo](../tests/test_recebimento.py#L14)
- Responsabilidade: Função auxiliar responsável pelo fluxo “test credito sem antecipacao preserva prazo”.

### `test_outros_meios_preservam_prazo(forma)`

- Local: [test_outros_meios_preservam_prazo](../tests/test_recebimento.py#L19)
- Responsabilidade: Função auxiliar responsável pelo fluxo “test outros meios preservam prazo”.

## `tests/test_security.py`

### `_request(*, path: str='/', client: tuple[str, int]=('127.0.0.1', 50000), headers: list[tuple[bytes, bytes]] | None=None) -> Request`

- Local: [_request](../tests/test_security.py#L25)
- Responsabilidade: Função auxiliar responsável pelo fluxo “request”.

### `test_password_hash_and_policy()`

- Local: [test_password_hash_and_policy](../tests/test_security.py#L46)
- Responsabilidade: Função auxiliar responsável pelo fluxo “test password hash and policy”.

### `test_jwt_has_lifecycle_claims_and_does_not_accept_url_token()`

- Local: [test_jwt_has_lifecycle_claims_and_does_not_accept_url_token](../tests/test_security.py#L61)
- Responsabilidade: Função auxiliar responsável pelo fluxo “test jwt has lifecycle claims and does not accept url token”.

### `test_bearer_header_takes_precedence_over_cookie()`

- Local: [test_bearer_header_takes_precedence_over_cookie](../tests/test_security.py#L73)
- Responsabilidade: Função auxiliar responsável pelo fluxo “test bearer header takes precedence over cookie”.

### `test_permission_matrix_is_centralized()`

- Local: [test_permission_matrix_is_centralized](../tests/test_security.py#L83)
- Responsabilidade: Função auxiliar responsável pelo fluxo “test permission matrix is centralized”.

### `test_proxy_headers_are_only_trusted_from_configured_network()`

- Local: [test_proxy_headers_are_only_trusted_from_configured_network](../tests/test_security.py#L92)
- Responsabilidade: Função auxiliar responsável pelo fluxo “test proxy headers are only trusted from configured network”.

### `test_origin_allowlist_is_exact()`

- Local: [test_origin_allowlist_is_exact](../tests/test_security.py#L105)
- Responsabilidade: Função auxiliar responsável pelo fluxo “test origin allowlist is exact”.

### `test_secure_cookie_is_disabled_only_for_explicit_private_host(monkeypatch)`

- Local: [test_secure_cookie_is_disabled_only_for_explicit_private_host](../tests/test_security.py#L114)
- Responsabilidade: Função auxiliar responsável pelo fluxo “test secure cookie is disabled only for explicit private host”.

### `test_rotina_partial_escapes_user_controlled_html()`

- Local: [test_rotina_partial_escapes_user_controlled_html](../tests/test_security.py#L145)
- Responsabilidade: Função auxiliar responsável pelo fluxo “test rotina partial escapes user controlled html”.

### `test_public_endpoints_and_security_headers()`

- Local: [test_public_endpoints_and_security_headers](../tests/test_security.py#L161)
- Responsabilidade: Função auxiliar responsável pelo fluxo “test public endpoints and security headers”.

### `test_login_rate_limit_is_per_account_and_message_is_generic()`

- Local: [test_login_rate_limit_is_per_account_and_message_is_generic](../tests/test_security.py#L178)
- Responsabilidade: Função auxiliar responsável pelo fluxo “test login rate limit is per account and message is generic”.

## `tests/test_taxas_cartao.py`

Testes da seleção automática de taxa por faixa de parcelamento.

### `taxa(id, faixa, inicial=None, final=None, maquininha_id=None)`

- Local: [taxa](../tests/test_taxas_cartao.py#L7)
- Responsabilidade: Cria um objeto mínimo com os atributos usados pela regra.

### `test_faixas_padrao()`

- Local: [test_faixas_padrao](../tests/test_taxas_cartao.py#L18)
- Responsabilidade: Função auxiliar responsável pelo fluxo “test faixas padrao”.

### `test_personalizada_tem_prioridade()`

- Local: [test_personalizada_tem_prioridade](../tests/test_taxas_cartao.py#L29)
- Responsabilidade: Função auxiliar responsável pelo fluxo “test personalizada tem prioridade”.

### `test_faixa_personalizada_mais_especifica_vence()`

- Local: [test_faixa_personalizada_mais_especifica_vence](../tests/test_taxas_cartao.py#L37)
- Responsabilidade: Função auxiliar responsável pelo fluxo “test faixa personalizada mais especifica vence”.

### `test_sem_faixa_compativel()`

- Local: [test_sem_faixa_compativel](../tests/test_taxas_cartao.py#L45)
- Responsabilidade: Função auxiliar responsável pelo fluxo “test sem faixa compativel”.

---

Total documentado: **502 funções e métodos**.
