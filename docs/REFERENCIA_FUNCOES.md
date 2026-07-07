# Referência de funções

> Arquivo gerado por `python scripts/generate_function_reference.py`.
> Não edite manualmente; melhore nomes/docstrings no código e gere novamente.

Esta referência ajuda o desenvolvedor a localizar responsabilidades. Ela complementa
o código e não substitui a leitura das regras de negócio e validações de acesso.

## `app/auth.py`

### `hash_senha(senha: str) -> str`

- Local: [hash_senha](../app/auth.py#L29)
- Responsabilidade: Gera um hash bcrypt irreversível para armazenamento da senha.

### `verificar_senha(senha_plana: str, senha_hash: str) -> bool`

- Local: [verificar_senha](../app/auth.py#L34)
- Responsabilidade: Compara uma senha informada com o hash bcrypt persistido.

### `criar_token(data: dict) -> str`

- Local: [criar_token](../app/auth.py#L39)
- Responsabilidade: Cria um JWT assinado com expiração configurada para a sessão web.

### `decodificar_token(token: str) -> Optional[dict]`

- Local: [decodificar_token](../app/auth.py#L47)
- Responsabilidade: Valida assinatura e expiração do JWT, retornando `None` se inválido.

### `login_bloqueado(chave: str) -> bool`

- Local: [login_bloqueado](../app/auth.py#L55)
- Responsabilidade: Informa se IP/e-mail excedeu o limite de tentativas na janela atual.

### `registrar_tentativa_login(chave: str) -> None`

- Local: [registrar_tentativa_login](../app/auth.py#L66)
- Responsabilidade: Registra uma falha de autenticação para controle de força bruta.

### `limpar_tentativas_login(chave: str) -> None`

- Local: [limpar_tentativas_login](../app/auth.py#L77)
- Responsabilidade: Remove falhas acumuladas após uma autenticação bem-sucedida.

### `get_token_do_cookie(request: Request) -> Optional[str]`

- Local: [get_token_do_cookie](../app/auth.py#L86)
- Responsabilidade: Obtém o token JWT do cookie HttpOnly da requisição.

### `get_usuario_atual(request: Request, db: Session=Depends(get_db)) -> Usuario`

- Local: [get_usuario_atual](../app/auth.py#L91)
- Responsabilidade: Lê o JWT do cookie. Se inválido ou ausente, redireciona para /login. Use como Depends() em qualquer rota protegida.

### `requer_coordenador(usuario: Usuario=Depends(get_usuario_atual)) -> Usuario`

- Local: [requer_coordenador](../app/auth.py#L134)
- Responsabilidade: Autoriza somente coordenadores e responde 403 para os demais perfis.

### `tem_acesso_geral(usuario: Usuario) -> bool`

- Local: [tem_acesso_geral](../app/auth.py#L142)
- Responsabilidade: Informa se o perfil pode operar todos os clientes da organização.

### `__init__(self, app)`

- Local: [AuthMiddleware.__init__](../app/auth.py#L160)
- Responsabilidade: Função auxiliar responsável pelo fluxo “init”.

### `__call__(self, scope, receive, send)`

- Local: [AuthMiddleware.__call__](../app/auth.py#L163)
- Responsabilidade: Função auxiliar responsável pelo fluxo “call”.

## `app/config.py`

Configurações da aplicação lidas do arquivo .env. Todos os módulos importam daqui — nunca leem os.getenv diretamente.

### `_validar_configuracao_sensivel() -> None`

- Local: [_validar_configuracao_sensivel](../app/config.py#L46)
- Responsabilidade: Interrompe o startup quando segredos ou controles críticos são inseguros.

## `app/database.py`

### `get_db()`

- Local: [get_db](../app/database.py#L40)
- Responsabilidade: Dependência do FastAPI — fornece sessão do banco e garante fechamento.

### `criar_tabelas()`

- Local: [criar_tabelas](../app/database.py#L49)
- Responsabilidade: Cria todas as tabelas no banco se ainda não existirem.

### `migrar_schema()`

- Local: [migrar_schema](../app/database.py#L55)
- Responsabilidade: Adiciona colunas novas em tabelas existentes (idempotente).

## `app/field_encryption.py`

Criptografia autenticada para campos sensiveis persistidos pelo SQLAlchemy.

### `_key() -> bytes`

- Local: [_key](../app/field_encryption.py#L76)
- Responsabilidade: Carrega e valida a chave de 64 bytes, mantendo-a em cache no processo.

### `is_encrypted(value: object) -> bool`

- Local: [is_encrypted](../app/field_encryption.py#L93)
- Responsabilidade: Informa se o valor usa o envelope versionado de criptografia do projeto.

### `encrypt_value(value: object, context: str, deterministic: bool=False) -> str | None`

- Local: [encrypt_value](../app/field_encryption.py#L98)
- Responsabilidade: Cifra um valor com contexto autenticado e retorna texto seguro para persistência.

### `decrypt_value(value: object, context: str) -> str | None`

- Local: [decrypt_value](../app/field_encryption.py#L118)
- Responsabilidade: Valida e decifra um valor; aceita plaintext somente para migração de legado.

### `__init__(self, context: str, *, deterministic: bool=False, **kwargs)`

- Local: [EncryptedText.__init__](../app/field_encryption.py#L145)
- Responsabilidade: Configura o contexto da coluna e se ela precisa permitir comparação exata.

### `process_bind_param(self, value, dialect)`

- Local: [EncryptedText.process_bind_param](../app/field_encryption.py#L151)
- Responsabilidade: Cifra valores automaticamente antes de enviá-los ao banco.

### `process_result_value(self, value, dialect)`

- Local: [EncryptedText.process_result_value](../app/field_encryption.py#L155)
- Responsabilidade: Decifra valores automaticamente ao materializar um objeto ORM.

## `app/jinja.py`

Instância única de Jinja2Templates compartilhada por todos os routers. Registra T (strings) e now como globais — disponíveis em qualquer template sem precisar passar como contexto.

### `strftime(self, fmt: str) -> str`

- Local: [_Today.strftime](../app/jinja.py#L14)
- Responsabilidade: Função auxiliar responsável pelo fluxo “strftime”.

### `__bool__(self) -> bool`

- Local: [_Today.__bool__](../app/jinja.py#L16)
- Responsabilidade: Função auxiliar responsável pelo fluxo “bool”.

### `__str__(self) -> str`

- Local: [_Today.__str__](../app/jinja.py#L18)
- Responsabilidade: Função auxiliar responsável pelo fluxo “str”.

## `app/main.py`

### `startup()`

- Local: [startup](../app/main.py#L51)
- Responsabilidade: Cria tabelas e aplica migrações.

## `app/models.py`

### `valor_pago_total(self)`

- Local: [ContaPagar.valor_pago_total](../app/models.py#L251)
- Responsabilidade: Função auxiliar responsável pelo fluxo “valor pago total”.

### `saldo_pendente(self)`

- Local: [ContaPagar.saldo_pendente](../app/models.py#L255)
- Responsabilidade: Função auxiliar responsável pelo fluxo “saldo pendente”.

## `app/routers/admin.py`

### `clientes_do_usuario(db: Session, usuario: Usuario)`

- Local: [clientes_do_usuario](../app/routers/admin.py#L31)
- Responsabilidade: Função auxiliar responsável pelo fluxo “clientes do usuario”.

### `pode_acessar_cliente(db: Session, usuario: Usuario, cliente_id: int) -> bool`

- Local: [pode_acessar_cliente](../app/routers/admin.py#L40)
- Responsabilidade: Função auxiliar responsável pelo fluxo “pode acessar cliente”.

### `_float_opcional(valor: str | None) -> Optional[float]`

- Local: [_float_opcional](../app/routers/admin.py#L50)
- Responsabilidade: Função auxiliar responsável pelo fluxo “float opcional”.

### `pagina_equipe(usuario: Usuario=Depends(get_usuario_atual))`

- Local: [pagina_equipe](../app/routers/admin.py#L57)
- Rota: `GET /admin/equipe`
- Responsabilidade: Endpoint que renderiza a página de equipe e devolve a resposta HTTP correspondente.

### `pagina_clientes(request: Request, db: Session=Depends(get_db), usuario: Usuario=Depends(get_usuario_atual))`

- Local: [pagina_clientes](../app/routers/admin.py#L64)
- Rota: `GET /admin/clientes`
- Responsabilidade: Endpoint que renderiza a página de clientes e devolve a resposta HTTP correspondente.

### `pagina_funcionarios(request: Request, db: Session=Depends(get_db), usuario: Usuario=Depends(requer_coordenador))`

- Local: [pagina_funcionarios](../app/routers/admin.py#L88)
- Rota: `GET /admin/funcionarios`
- Responsabilidade: Endpoint que renderiza a página de funcionarios e devolve a resposta HTTP correspondente.

### `pagina_anotacoes_clientes(request: Request, db: Session=Depends(get_db), usuario: Usuario=Depends(get_usuario_atual))`

- Local: [pagina_anotacoes_clientes](../app/routers/admin.py#L103)
- Rota: `GET /admin/anotacoes-clientes`
- Responsabilidade: Endpoint que renderiza a página de anotacoes clientes e devolve a resposta HTTP correspondente.

### `pagina_anotacoes_cliente(cliente_id: int, request: Request, db: Session=Depends(get_db), usuario: Usuario=Depends(get_usuario_atual))`

- Local: [pagina_anotacoes_cliente](../app/routers/admin.py#L117)
- Rota: `GET /admin/anotacoes-clientes/{cliente_id}`
- Responsabilidade: Endpoint que renderiza a página de anotacoes cliente e devolve a resposta HTTP correspondente.

### `criar_anotacao_cliente(cliente_id: int, categoria: str=Form('procedimento'), titulo: str=Form(...), conteudo: str=Form(...), db: Session=Depends(get_db), usuario: Usuario=Depends(get_usuario_atual))`

- Local: [criar_anotacao_cliente](../app/routers/admin.py#L141)
- Rota: `POST /admin/anotacoes-clientes/{cliente_id}/nova`
- Responsabilidade: Endpoint que cria anotacao cliente e devolve a resposta HTTP correspondente.

### `editar_anotacao_cliente(anotacao_id: int, categoria: str=Form('procedimento'), titulo: str=Form(...), conteudo: str=Form(...), db: Session=Depends(get_db), usuario: Usuario=Depends(get_usuario_atual))`

- Local: [editar_anotacao_cliente](../app/routers/admin.py#L170)
- Rota: `POST /admin/anotacoes-clientes/anotacao/{anotacao_id}/editar`
- Responsabilidade: Endpoint que edita anotacao cliente e devolve a resposta HTTP correspondente.

### `excluir_anotacao_cliente(anotacao_id: int, db: Session=Depends(get_db), usuario: Usuario=Depends(get_usuario_atual))`

- Local: [excluir_anotacao_cliente](../app/routers/admin.py#L192)
- Rota: `POST /admin/anotacoes-clientes/anotacao/{anotacao_id}/excluir`
- Responsabilidade: Endpoint que exclui anotacao cliente e devolve a resposta HTTP correspondente.

### `criar_usuario(nome: str=Form(...), email: str=Form(...), senha: str=Form(...), perfil: str=Form('funcionario'), db: Session=Depends(get_db), _: Usuario=Depends(requer_coordenador))`

- Local: [criar_usuario](../app/routers/admin.py#L210)
- Rota: `POST /admin/equipe/usuario`
- Responsabilidade: Endpoint que cria usuario e devolve a resposta HTTP correspondente.

### `editar_usuario(usuario_id: int, nome: str=Form(...), email: str=Form(...), perfil: str=Form(...), senha: Optional[str]=Form(None), db: Session=Depends(get_db), coordenador: Usuario=Depends(requer_coordenador))`

- Local: [editar_usuario](../app/routers/admin.py#L241)
- Rota: `POST /admin/funcionarios/usuario/{usuario_id}/editar`
- Responsabilidade: Endpoint que edita usuario e devolve a resposta HTTP correspondente.

### `excluir_usuario(usuario_id: int, db: Session=Depends(get_db), coordenador: Usuario=Depends(requer_coordenador))`

- Local: [excluir_usuario](../app/routers/admin.py#L284)
- Rota: `POST /admin/funcionarios/usuario/{usuario_id}/excluir`
- Responsabilidade: Endpoint que exclui usuario e devolve a resposta HTTP correspondente.

### `toggle_usuario(usuario_id: int, db: Session=Depends(get_db), coordenador: Usuario=Depends(requer_coordenador))`

- Local: [toggle_usuario](../app/routers/admin.py#L324)
- Rota: `POST /admin/equipe/usuario/{usuario_id}/toggle`
- Responsabilidade: Endpoint que alterna o estado de usuario e devolve a resposta HTTP correspondente.

### `criar_cliente(nome: str=Form(...), razao_social: Optional[str]=Form(None), cnpj: Optional[str]=Form(None), especialidade: Optional[str]=Form(None), tem_maquininha: str=Form('nao'), rede_maquininha: Optional[str]=Form(None), antecipa: str=Form('nao'), bandeira: List[str]=Form(default=[]), taxa_percentual: List[str]=Form(default=[]), funcionario_id: Optional[int]=Form(None), db: Session=Depends(get_db), usuario: Usuario=Depends(get_usuario_atual))`

- Local: [criar_cliente](../app/routers/admin.py#L344)
- Rota: `POST /admin/equipe/cliente`
- Responsabilidade: Endpoint que cria cliente e devolve a resposta HTTP correspondente.

### `atribuir_cliente(cliente_id: int, funcionario_id: Optional[int]=Form(None), db: Session=Depends(get_db), _: Usuario=Depends(requer_coordenador))`

- Local: [atribuir_cliente](../app/routers/admin.py#L393)
- Rota: `POST /admin/equipe/cliente/{cliente_id}/atribuir`
- Responsabilidade: Endpoint que executa o fluxo atribuir cliente e devolve a resposta HTTP correspondente.

### `atualizar_cliente(cliente_id: int, razao_social: Optional[str]=Form(None), cnpj: Optional[str]=Form(None), especialidade: Optional[str]=Form(None), tem_maquininha: str=Form('nao'), rede_maquininha: Optional[str]=Form(None), antecipa: str=Form('nao'), db: Session=Depends(get_db), usuario: Usuario=Depends(get_usuario_atual))`

- Local: [atualizar_cliente](../app/routers/admin.py#L407)
- Rota: `POST /admin/clientes/cliente/{cliente_id}/atualizar`
- Responsabilidade: Endpoint que atualiza cliente e devolve a resposta HTTP correspondente.

### `pagina_editar_cliente(cliente_id: int, request: Request, db: Session=Depends(get_db), usuario: Usuario=Depends(get_usuario_atual))`

- Local: [pagina_editar_cliente](../app/routers/admin.py#L432)
- Rota: `GET /admin/clientes/cliente/{cliente_id}/editar`
- Responsabilidade: Endpoint que renderiza a página de editar cliente e devolve a resposta HTTP correspondente.

### `editar_cliente_completo(cliente_id: int, nome: str=Form(...), razao_social: Optional[str]=Form(None), cnpj: Optional[str]=Form(None), especialidade: Optional[str]=Form(None), regime_tributario: Optional[str]=Form(None), banco: Optional[str]=Form(None), agencia: Optional[str]=Form(None), conta: Optional[str]=Form(None), tem_maquininha: str=Form('nao'), rede_maquininha: Optional[str]=Form(None), antecipa: str=Form('nao'), funcionario_id: Optional[int]=Form(None), db: Session=Depends(get_db), usuario: Usuario=Depends(get_usuario_atual))`

- Local: [editar_cliente_completo](../app/routers/admin.py#L460)
- Rota: `POST /admin/clientes/cliente/{cliente_id}/editar`
- Responsabilidade: Endpoint que edita cliente completo e devolve a resposta HTTP correspondente.

### `excluir_cliente(cliente_id: int, db: Session=Depends(get_db), usuario: Usuario=Depends(requer_coordenador))`

- Local: [excluir_cliente](../app/routers/admin.py#L522)
- Rota: `POST /admin/clientes/cliente/{cliente_id}/excluir`
- Responsabilidade: Endpoint que exclui cliente e devolve a resposta HTTP correspondente.

### `pagina_taxas_cartao(request: Request, cliente_id: Optional[int]=None, maquininha_id: Optional[int]=None, db: Session=Depends(get_db), usuario: Usuario=Depends(get_usuario_atual))`

- Local: [pagina_taxas_cartao](../app/routers/admin.py#L557)
- Rota: `GET /admin/taxas-cartao`
- Responsabilidade: Endpoint que renderiza a página de taxas cartao e devolve a resposta HTTP correspondente.

### `criar_taxa(cliente_id: int=Form(...), maquininha_id: Optional[int]=Form(None), bandeira: str=Form(...), faixa_parcelamento: str=Form('avista_credito'), taxa_percentual: float=Form(...), db: Session=Depends(get_db), usuario: Usuario=Depends(get_usuario_atual))`

- Local: [criar_taxa](../app/routers/admin.py#L610)
- Rota: `POST /admin/taxas-cartao`
- Responsabilidade: Endpoint que cria taxa e devolve a resposta HTTP correspondente.

### `excluir_taxa(taxa_id: int, cliente_id: int=Form(...), maquininha_id: Optional[int]=Form(None), db: Session=Depends(get_db), _: Usuario=Depends(requer_coordenador))`

- Local: [excluir_taxa](../app/routers/admin.py#L652)
- Rota: `POST /admin/taxas-cartao/{taxa_id}/excluir`
- Responsabilidade: Endpoint que exclui taxa e devolve a resposta HTTP correspondente.

### `adicionar_maquininha(cliente_id: int, rede: str=Form(...), apelido: Optional[str]=Form(None), antecipa: str=Form('nao'), db: Session=Depends(get_db), usuario: Usuario=Depends(get_usuario_atual))`

- Local: [adicionar_maquininha](../app/routers/admin.py#L674)
- Rota: `POST /admin/clientes/cliente/{cliente_id}/maquininha/adicionar`
- Responsabilidade: Endpoint que adiciona maquininha e devolve a resposta HTTP correspondente.

### `editar_maquininha(maquininha_id: int, rede: str=Form(...), apelido: Optional[str]=Form(None), antecipa: str=Form('nao'), db: Session=Depends(get_db), usuario: Usuario=Depends(get_usuario_atual))`

- Local: [editar_maquininha](../app/routers/admin.py#L700)
- Rota: `POST /admin/maquininha/{maquininha_id}/editar`
- Responsabilidade: Endpoint que edita maquininha e devolve a resposta HTTP correspondente.

### `toggle_antecipa_cliente(cliente_id: int=Form(...), db: Session=Depends(get_db), usuario: Usuario=Depends(get_usuario_atual))`

- Local: [toggle_antecipa_cliente](../app/routers/admin.py#L730)
- Rota: `POST /admin/taxas-cartao/toggle-antecipa`
- Responsabilidade: Endpoint que alterna o estado de antecipa cliente e devolve a resposta HTTP correspondente.

### `criar_taxa_antecipacao(cliente_id: int=Form(...), bandeira: str=Form(...), descricao: str=Form(...), taxa_percentual: float=Form(...), db: Session=Depends(get_db), usuario: Usuario=Depends(get_usuario_atual))`

- Local: [criar_taxa_antecipacao](../app/routers/admin.py#L749)
- Rota: `POST /admin/taxas-antecipacao`
- Responsabilidade: Endpoint que cria taxa antecipacao e devolve a resposta HTTP correspondente.

### `selecionar_taxa_antecipacao(taxa_id: int, cliente_id: int=Form(...), db: Session=Depends(get_db), usuario: Usuario=Depends(get_usuario_atual))`

- Local: [selecionar_taxa_antecipacao](../app/routers/admin.py#L777)
- Rota: `POST /admin/taxas-antecipacao/{taxa_id}/selecionar`
- Responsabilidade: Endpoint que seleciona taxa antecipacao e devolve a resposta HTTP correspondente.

### `toggle_ativo_antecipacao(taxa_id: int, cliente_id: int=Form(...), db: Session=Depends(get_db), usuario: Usuario=Depends(get_usuario_atual))`

- Local: [toggle_ativo_antecipacao](../app/routers/admin.py#L802)
- Rota: `POST /admin/taxas-antecipacao/{taxa_id}/toggle-ativo`
- Responsabilidade: Endpoint que alterna o estado de ativo antecipacao e devolve a resposta HTTP correspondente.

### `excluir_taxa_antecipacao(taxa_id: int, cliente_id: int=Form(...), db: Session=Depends(get_db), _: Usuario=Depends(requer_coordenador))`

- Local: [excluir_taxa_antecipacao](../app/routers/admin.py#L823)
- Rota: `POST /admin/taxas-antecipacao/{taxa_id}/excluir`
- Responsabilidade: Endpoint que exclui taxa antecipacao e devolve a resposta HTTP correspondente.

### `pagina_centros_custo(request: Request, cliente_id: int, db: Session=Depends(get_db), usuario: Usuario=Depends(get_usuario_atual))`

- Local: [pagina_centros_custo](../app/routers/admin.py#L840)
- Rota: `GET /admin/centros-custo`
- Responsabilidade: Endpoint que renderiza a página de centros custo e devolve a resposta HTTP correspondente.

### `criar_centro_custo(cliente_id: int=Form(...), codigo: str=Form(...), nome: str=Form(...), is_medico: bool=Form(False), especialidade: Optional[str]=Form(None), db: Session=Depends(get_db), usuario: Usuario=Depends(get_usuario_atual))`

- Local: [criar_centro_custo](../app/routers/admin.py#L862)
- Rota: `POST /admin/centros-custo`
- Responsabilidade: Endpoint que cria centro custo e devolve a resposta HTTP correspondente.

### `excluir_centro_custo(cc_id: int, db: Session=Depends(get_db), usuario: Usuario=Depends(get_usuario_atual))`

- Local: [excluir_centro_custo](../app/routers/admin.py#L886)
- Rota: `POST /admin/centros-custo/{cc_id}/excluir`
- Responsabilidade: Endpoint que exclui centro custo e devolve a resposta HTTP correspondente.

### `editar_centro_custo(cc_id: int, is_medico: bool=Form(False), especialidade: Optional[str]=Form(None), db: Session=Depends(get_db), usuario: Usuario=Depends(get_usuario_atual))`

- Local: [editar_centro_custo](../app/routers/admin.py#L900)
- Rota: `POST /admin/centros-custo/{cc_id}/editar`
- Responsabilidade: Endpoint que edita centro custo e devolve a resposta HTTP correspondente.

### `remover_maquininha(maquininha_id: int, db: Session=Depends(get_db), usuario: Usuario=Depends(get_usuario_atual))`

- Local: [remover_maquininha](../app/routers/admin.py#L917)
- Rota: `POST /admin/maquininha/{maquininha_id}/remover`
- Responsabilidade: Endpoint que executa o fluxo remover maquininha e devolve a resposta HTTP correspondente.

## `app/routers/auth.py`

### `pagina_login(request: Request)`

- Local: [pagina_login](../app/routers/auth.py#L23)
- Rota: `GET /login`
- Responsabilidade: Endpoint que renderiza a página de login e devolve a resposta HTTP correspondente.

### `fazer_login(request: Request, email: str=Form(...), senha: str=Form(...), db: Session=Depends(get_db))`

- Local: [fazer_login](../app/routers/auth.py#L28)
- Rota: `POST /login`
- Responsabilidade: Endpoint que executa login e devolve a resposta HTTP correspondente.

### `logout(request: Request, db: Session=Depends(get_db), usuario: Usuario=Depends(get_usuario_atual))`

- Local: [logout](../app/routers/auth.py#L75)
- Rota: `POST /logout`
- Responsabilidade: Endpoint que executa o fluxo logout e devolve a resposta HTTP correspondente.

## `app/routers/cliente_ativo.py`

### `selecionar_cliente(request: Request, cliente_id: Optional[str]=Form(None))`

- Local: [selecionar_cliente](../app/routers/cliente_ativo.py#L13)
- Rota: `POST /cliente/selecionar`
- Responsabilidade: Endpoint que seleciona cliente e devolve a resposta HTTP correspondente.

## `app/routers/conciliacao.py`

### `clientes_do_usuario(db: Session, usuario: Usuario)`

- Local: [clientes_do_usuario](../app/routers/conciliacao.py#L50)
- Responsabilidade: Função auxiliar responsável pelo fluxo “clientes do usuario”.

### `_carregar_vendas_a_conciliar(db: Session, cliente_id: int)`

- Local: [_carregar_vendas_a_conciliar](../app/routers/conciliacao.py#L59)
- Responsabilidade: Vendas pendentes (sem atendimento vinculado).

### `_carregar_vendas_conciliadas(db: Session, cliente_id: int)`

- Local: [_carregar_vendas_conciliadas](../app/routers/conciliacao.py#L72)
- Responsabilidade: Vendas já conciliadas com atendimento mas ainda não fechadas em lote.

### `_carregar_atendimentos_pendentes(db: Session, cliente_id: int)`

- Local: [_carregar_atendimentos_pendentes](../app/routers/conciliacao.py#L85)
- Responsabilidade: Função auxiliar que carrega atendimentos pendentes.

### `_buscar_atendimentos(db: Session, cliente_id: int, venda: VendaCartao, termo: str | None)`

- Local: [_buscar_atendimentos](../app/routers/conciliacao.py#L101)
- Responsabilidade: Função auxiliar que busca atendimentos.

### `_montar_painel(db, cliente_id, vendas, atendimentos, busca_venda_id=None, busca_termo=None)`

- Local: [_montar_painel](../app/routers/conciliacao.py#L120)
- Responsabilidade: Função auxiliar que monta painel.

### `_agrupar_conciliadas(vendas_conciliadas: list) -> list`

- Local: [_agrupar_conciliadas](../app/routers/conciliacao.py#L156)
- Responsabilidade: Função auxiliar responsável pelo fluxo “agrupar conciliadas”.

### `_carregar_lotes_recentes(db: Session, cliente_id: int)`

- Local: [_carregar_lotes_recentes](../app/routers/conciliacao.py#L177)
- Responsabilidade: Função auxiliar que carrega lotes recentes.

### `_ctx(db, usuario, cliente_id, busca_venda_id=None, busca_termo=None)`

- Local: [_ctx](../app/routers/conciliacao.py#L187)
- Responsabilidade: Função auxiliar responsável pelo fluxo “ctx”.

### `pagina_conciliacao_cartao(request: Request, cliente_id: Optional[int]=None, buscar_venda: Optional[int]=Query(default=None), termo: Optional[str]=Query(default=None), db: Session=Depends(get_db), usuario: Usuario=Depends(get_usuario_atual))`

- Local: [pagina_conciliacao_cartao](../app/routers/conciliacao.py#L210)
- Rota: `GET /conciliacao`
- Responsabilidade: Endpoint que renderiza a página de conciliacao cartao e devolve a resposta HTTP correspondente.

### `importar_extrato_maquininha(request: Request, cliente_id: int=Form(...), arquivo: UploadFile=File(...), db: Session=Depends(get_db), usuario: Usuario=Depends(get_usuario_atual))`

- Local: [importar_extrato_maquininha](../app/routers/conciliacao.py#L232)
- Rota: `POST /conciliacao/importar`
- Responsabilidade: Endpoint que importa extrato maquininha e devolve a resposta HTTP correspondente.

### `conciliar_todos_prontos(cliente_id: int=Form(...), db: Session=Depends(get_db), usuario: Usuario=Depends(get_usuario_atual))`

- Local: [conciliar_todos_prontos](../app/routers/conciliacao.py#L278)
- Rota: `POST /conciliacao/conciliar-todos-prontos`
- Responsabilidade: Endpoint que concilia todos prontos e devolve a resposta HTTP correspondente.

### `_aplicar_conciliacao(db: Session, venda: VendaCartao, at: Atendimento)`

- Local: [_aplicar_conciliacao](../app/routers/conciliacao.py#L294)
- Responsabilidade: Função auxiliar que aplica conciliacao.

### `_conciliar_vendas_prontas(db: Session, cliente_id: int, usuario: Usuario | None=None) -> int`

- Local: [_conciliar_vendas_prontas](../app/routers/conciliacao.py#L307)
- Responsabilidade: Função auxiliar que concilia vendas prontas.

### `_conciliar_pix_ted_prontos(db: Session, cliente_id: int, usuario: Usuario | None=None) -> int`

- Local: [_conciliar_pix_ted_prontos](../app/routers/conciliacao.py#L331)
- Responsabilidade: Função auxiliar que concilia pix ted prontos.

### `conciliar_venda(venda_id: int, cliente_id: int=Form(...), atendimento_id: int=Form(...), origem: str=Form('sugestao'), db: Session=Depends(get_db), usuario: Usuario=Depends(get_usuario_atual))`

- Local: [conciliar_venda](../app/routers/conciliacao.py#L389)
- Rota: `POST /conciliacao/venda/{venda_id}/conciliar`
- Responsabilidade: Endpoint que concilia venda e devolve a resposta HTTP correspondente.

### `editar_venda(venda_id: int, cliente_id: int=Form(...), atendimento_id: Optional[int]=Form(default=None), valor_bruto: str=Form(...), taxa_percentual: str=Form(''), valor_liquido: str=Form(...), at_valor_servico: str=Form(...), at_taxa_cartao: str=Form(''), at_valor_liquido: str=Form(...), db: Session=Depends(get_db), usuario: Usuario=Depends(get_usuario_atual))`

- Local: [editar_venda](../app/routers/conciliacao.py#L416)
- Rota: `POST /conciliacao/venda/{venda_id}/editar`
- Responsabilidade: Endpoint que edita venda e devolve a resposta HTTP correspondente.

### `reabrir_lote(lote_id: int, cliente_id: int=Form(...), db: Session=Depends(get_db), usuario: Usuario=Depends(get_usuario_atual))`

- Local: [reabrir_lote](../app/routers/conciliacao.py#L469)
- Rota: `POST /conciliacao/lote/{lote_id}/reabrir`
- Responsabilidade: Endpoint que executa o fluxo reabrir lote e devolve a resposta HTTP correspondente.

### `desvincular_venda(venda_id: int, cliente_id: int=Form(...), db: Session=Depends(get_db), usuario: Usuario=Depends(get_usuario_atual))`

- Local: [desvincular_venda](../app/routers/conciliacao.py#L502)
- Rota: `POST /conciliacao/venda/{venda_id}/desvincular`
- Responsabilidade: Endpoint que executa o fluxo desvincular venda e devolve a resposta HTTP correspondente.

### `criar_e_conciliar_venda(venda_id: int, cliente_id: int=Form(...), data_atendimento: str=Form(...), nome_paciente: str=Form(''), cpf_paciente: str=Form(''), medico: str=Form(''), especialidade: str=Form(''), tipo_servico: str=Form(''), descricao_servico: str=Form(''), observacao: str=Form(''), db: Session=Depends(get_db), usuario: Usuario=Depends(get_usuario_atual))`

- Local: [criar_e_conciliar_venda](../app/routers/conciliacao.py#L525)
- Rota: `POST /conciliacao/venda/{venda_id}/criar-e-conciliar`
- Responsabilidade: Endpoint que cria e conciliar venda e devolve a resposta HTTP correspondente.

### `cancelar_venda(venda_id: int, cliente_id: int=Form(...), db: Session=Depends(get_db), usuario: Usuario=Depends(get_usuario_atual))`

- Local: [cancelar_venda](../app/routers/conciliacao.py#L586)
- Rota: `POST /conciliacao/venda/{venda_id}/cancelar`
- Responsabilidade: Endpoint que executa o fluxo cancelar venda e devolve a resposta HTTP correspondente.

### `fechar_lote(cliente_id: int=Form(...), data_pagamento: str=Form(...), bandeira: str=Form(''), db: Session=Depends(get_db), usuario: Usuario=Depends(get_usuario_atual))`

- Local: [fechar_lote](../app/routers/conciliacao.py#L602)
- Rota: `POST /conciliacao/fechar-lote`
- Responsabilidade: Endpoint que fecha lote e devolve a resposta HTTP correspondente.

### `_reabrir_lote_duplicado_removido(lote_id: int, cliente_id: int=Form(...), db: Session=Depends(get_db), usuario: Usuario=Depends(get_usuario_atual))`

- Local: [_reabrir_lote_duplicado_removido](../app/routers/conciliacao.py#L631)
- Responsabilidade: Função auxiliar responsável pelo fluxo “reabrir lote duplicado removido”.

### `_carregar_lancamentos(db: Session, cliente_id: int)`

- Local: [_carregar_lancamentos](../app/routers/conciliacao.py#L659)
- Responsabilidade: Função auxiliar que carrega lancamentos.

### `_decimal_form(valor: str) -> Decimal | None`

- Local: [_decimal_form](../app/routers/conciliacao.py#L674)
- Responsabilidade: Função auxiliar responsável pelo fluxo “decimal form”.

### `_calcular_intervalos_lancamento(forma_pagamento: str, parcela_total: int, recorrencia: str | None)`

- Local: [_calcular_intervalos_lancamento](../app/routers/conciliacao.py#L681)
- Responsabilidade: Função auxiliar que calcula intervalos lancamento.

### `_taxa_cartao_cliente(db: Session, cliente_id: int, bandeira: str | None) -> Decimal | None`

- Local: [_taxa_cartao_cliente](../app/routers/conciliacao.py#L692)
- Responsabilidade: Função auxiliar responsável pelo fluxo “taxa cartao cliente”.

### `_rateios_lancamento_manual(raw: str, centros: dict[int, CentroCusto]) -> list[dict]`

- Local: [_rateios_lancamento_manual](../app/routers/conciliacao.py#L713)
- Responsabilidade: Função auxiliar responsável pelo fluxo “rateios lancamento manual”.

### `pagina_lancamentos(request: Request, cliente_id: Optional[int]=None, flash: Optional[str]=None, db: Session=Depends(get_db), usuario: Usuario=Depends(get_usuario_atual))`

- Local: [pagina_lancamentos](../app/routers/conciliacao.py#L741)
- Rota: `GET /conciliacao/lancamentos`
- Responsabilidade: Endpoint que renderiza a página de lancamentos e devolve a resposta HTTP correspondente.

### `importar_lancamentos_conciliacao(request: Request, cliente_id: int=Form(...), arquivo: UploadFile=File(...), db: Session=Depends(get_db), usuario: Usuario=Depends(get_usuario_atual))`

- Local: [importar_lancamentos_conciliacao](../app/routers/conciliacao.py#L768)
- Rota: `POST /conciliacao/lancamentos/importar`
- Responsabilidade: Endpoint que importa lancamentos conciliacao e devolve a resposta HTTP correspondente.

### `criar_lancamento_manual_conciliacao(request: Request, cliente_id: int=Form(...), data_atendimento: date_type=Form(...), nome_paciente: str=Form(''), cpf_paciente: str=Form(''), centro_custo_id: str=Form(''), rateios_json: str=Form('[]'), especialidade: str=Form(''), descricao_servico: str=Form(''), valor_servico: str=Form(...), forma_pagamento: str=Form(''), condicao_pagamento: str=Form('avista'), parcela_total: int=Form(1), recorrencia: str=Form(''), ultimos_digitos_cartao: str=Form(''), bandeira_cartao: str=Form(''), percentual_medico: str=Form(''), observacao: str=Form(''), db: Session=Depends(get_db), usuario: Usuario=Depends(get_usuario_atual))`

- Local: [criar_lancamento_manual_conciliacao](../app/routers/conciliacao.py#L823)
- Rota: `POST /conciliacao/lancamentos/manual`
- Responsabilidade: Endpoint que cria lancamento manual conciliacao e devolve a resposta HTTP correspondente.

## `app/routers/conciliacao_banco.py`

### `_chave_centro_custo(cc: CentroCusto) -> str`

- Local: [_chave_centro_custo](../app/routers/conciliacao_banco.py#L57)
- Responsabilidade: Função auxiliar responsável pelo fluxo “chave centro custo”.

### `_montar_rateios_banco(db: Session, cliente_id: int, valor_total: Decimal, rateios_json: str) -> list[dict]`

- Local: [_montar_rateios_banco](../app/routers/conciliacao_banco.py#L61)
- Responsabilidade: Função auxiliar que monta rateios banco.

### `clientes_do_usuario(db: Session, usuario: Usuario)`

- Local: [clientes_do_usuario](../app/routers/conciliacao_banco.py#L93)
- Responsabilidade: Função auxiliar responsável pelo fluxo “clientes do usuario”.

### `_total_pago_conta(db: Session, conta_id: int) -> Decimal`

- Local: [_total_pago_conta](../app/routers/conciliacao_banco.py#L102)
- Responsabilidade: Função auxiliar responsável pelo fluxo “total pago conta”.

### `_registrar_pagamento_conta(db: Session, conta: ContaPagar, valor: Decimal, data_pagamento: date, usuario_id: int | None, movimentacao_id: int | None=None, observacao: str | None=None) -> bool`

- Local: [_registrar_pagamento_conta](../app/routers/conciliacao_banco.py#L109)
- Responsabilidade: Função auxiliar que registra pagamento conta.

### `_carregar_movimentacoes(db: Session, cliente_id: int)`

- Local: [_carregar_movimentacoes](../app/routers/conciliacao_banco.py#L141)
- Responsabilidade: Retorna pix_ted pendentes que NÃO estão vinculados a lote de cartão.

### `_carregar_lancamentos_pendentes(db: Session, cliente_id: int)`

- Local: [_carregar_lancamentos_pendentes](../app/routers/conciliacao_banco.py#L162)
- Responsabilidade: Função auxiliar que carrega lancamentos pendentes.

### `_buscar_no_sistema(db: Session, cliente_id: int, mov: MovimentacaoBancaria, termo: str | None)`

- Local: [_buscar_no_sistema](../app/routers/conciliacao_banco.py#L179)
- Responsabilidade: Função auxiliar que busca no sistema.

### `_montar_painel(db: Session, cliente_id: int, lancamentos: list, movimentacoes: list, busca_mov_id: Optional[int]=None, busca_termo: Optional[str]=None)`

- Local: [_montar_painel](../app/routers/conciliacao_banco.py#L206)
- Responsabilidade: Função auxiliar que monta painel.

### `_aplicar_conciliacao(db: Session, mov: MovimentacaoBancaria, at: Atendimento)`

- Local: [_aplicar_conciliacao](../app/routers/conciliacao_banco.py#L252)
- Responsabilidade: Função auxiliar que aplica conciliacao.

### `_conciliar_pix_ted_prontos(db: Session, cliente_id: int, usuario: Usuario | None=None) -> int`

- Local: [_conciliar_pix_ted_prontos](../app/routers/conciliacao_banco.py#L261)
- Responsabilidade: Função auxiliar que concilia pix ted prontos.

### `_auto_match_lotes(db: Session, cliente_id: int, usuario: Usuario | None=None) -> int`

- Local: [_auto_match_lotes](../app/routers/conciliacao_banco.py#L285)
- Responsabilidade: Função auxiliar responsável pelo fluxo “auto match lotes”.

### `_carregar_saidas_banco(db: Session, cliente_id: int)`

- Local: [_carregar_saidas_banco](../app/routers/conciliacao_banco.py#L322)
- Responsabilidade: Saídas bancárias ainda não vinculadas a uma conta a pagar.

### `_carregar_contas_agendadas(db: Session, cliente_id: int)`

- Local: [_carregar_contas_agendadas](../app/routers/conciliacao_banco.py#L342)
- Responsabilidade: Contas a pagar com status agendado aguardando conciliação bancária.

### `_carregar_lotes_cartao(db: Session, cliente_id: int)`

- Local: [_carregar_lotes_cartao](../app/routers/conciliacao_banco.py#L356)
- Responsabilidade: Função auxiliar que carrega lotes cartao.

### `_carregar_creditos_banco_para_lote(db: Session, cliente_id: int)`

- Local: [_carregar_creditos_banco_para_lote](../app/routers/conciliacao_banco.py#L365)
- Responsabilidade: MovimentacaoBancaria pix_ted ainda não vinculadas a lote de cartão (disponíveis para match).

### `_carregar_pix_conciliados(db: Session, cliente_id: int)`

- Local: [_carregar_pix_conciliados](../app/routers/conciliacao_banco.py#L387)
- Responsabilidade: PIX/TED já conciliados com atendimento — para exibir com opção de desvincular.

### `_resumo_periodo_movimentacoes(movimentacoes: list) -> str`

- Local: [_resumo_periodo_movimentacoes](../app/routers/conciliacao_banco.py#L406)
- Responsabilidade: Função auxiliar responsável pelo fluxo “resumo periodo movimentacoes”.

### `_opcoes_mes_movimentacoes(movimentacoes: list) -> list[dict]`

- Local: [_opcoes_mes_movimentacoes](../app/routers/conciliacao_banco.py#L419)
- Responsabilidade: Função auxiliar responsável pelo fluxo “opcoes mes movimentacoes”.

### `_carregar_saidas_conciliadas(db: Session, cliente_id: int)`

- Local: [_carregar_saidas_conciliadas](../app/routers/conciliacao_banco.py#L436)
- Responsabilidade: Saídas bancárias já conciliadas com conta a pagar — para exibir com opção de desvincular.

### `_carregar_arquivados(db: Session, cliente_id: int)`

- Local: [_carregar_arquivados](../app/routers/conciliacao_banco.py#L453)
- Responsabilidade: Função auxiliar que carrega arquivados.

### `_conta_bancaria_do_ofx(db: Session, cliente_id: int, df) -> ContaBancaria`

- Local: [_conta_bancaria_do_ofx](../app/routers/conciliacao_banco.py#L484)
- Responsabilidade: Função auxiliar responsável pelo fluxo “conta bancaria do ofx”.

### `_resumo_saldos_bancarios(db: Session, cliente_id: int | None) -> list[dict]`

- Local: [_resumo_saldos_bancarios](../app/routers/conciliacao_banco.py#L510)
- Responsabilidade: Função auxiliar responsável pelo fluxo “resumo saldos bancarios”.

### `_movimentacoes_do_extrato(db: Session, cliente_id: int | None)`

- Local: [_movimentacoes_do_extrato](../app/routers/conciliacao_banco.py#L540)
- Responsabilidade: Função auxiliar responsável pelo fluxo “movimentacoes do extrato”.

### `_ctx_padrao(db, usuario, cliente_id, busca_mov_id=None, busca_termo=None, mes_conciliado=None)`

- Local: [_ctx_padrao](../app/routers/conciliacao_banco.py#L550)
- Responsabilidade: Função auxiliar responsável pelo fluxo “ctx padrao”.

### `pagina_banco(request: Request, cliente_id: Optional[int]=None, buscar_mov: Optional[int]=Query(default=None), termo: Optional[str]=Query(default=None), lote_fechado: Optional[int]=Query(default=None), mes_conciliado: Optional[str]=Query(default=None), arquivados: bool=Query(default=False), manual_criado: Optional[str]=Query(default=None), db: Session=Depends(get_db), usuario: Usuario=Depends(get_usuario_atual))`

- Local: [pagina_banco](../app/routers/conciliacao_banco.py#L603)
- Rota: `GET /conciliacao/banco`
- Responsabilidade: Endpoint que renderiza a página de banco e devolve a resposta HTTP correspondente.

### `criar_receita_manual_banco(request: Request, cliente_id: int=Form(...), descricao: str=Form(...), nome_pagador: str=Form(''), valor: Decimal=Form(...), data_recebimento: date=Form(...), forma_pagamento: str=Form('pix'), observacao: str=Form(''), rateios_json: str=Form('[]'), db: Session=Depends(get_db), usuario: Usuario=Depends(get_usuario_atual))`

- Local: [criar_receita_manual_banco](../app/routers/conciliacao_banco.py#L659)
- Rota: `POST /conciliacao/banco/manual/receita`
- Responsabilidade: Endpoint que cria receita manual banco e devolve a resposta HTTP correspondente.

### `criar_movimentacao_manual_banco(request: Request, cliente_id: int=Form(...), conta_bancaria_id: Optional[int]=Form(None), banco: str=Form(''), conta_numero: str=Form(''), sentido: str=Form(...), data_movimento: date=Form(...), valor: Decimal=Form(...), descricao: str=Form(...), db: Session=Depends(get_db), usuario: Usuario=Depends(get_usuario_atual))`

- Local: [criar_movimentacao_manual_banco](../app/routers/conciliacao_banco.py#L718)
- Rota: `POST /conciliacao/banco/manual/movimentacao`
- Responsabilidade: Endpoint que cria movimentacao manual banco e devolve a resposta HTTP correspondente.

### `criar_despesa_manual_banco(request: Request, cliente_id: int=Form(...), descricao: str=Form(...), fornecedor: str=Form(''), valor: Decimal=Form(...), vencimento: date=Form(...), observacao: str=Form(''), rateios_json: str=Form('[]'), db: Session=Depends(get_db), usuario: Usuario=Depends(get_usuario_atual))`

- Local: [criar_despesa_manual_banco](../app/routers/conciliacao_banco.py#L790)
- Rota: `POST /conciliacao/banco/manual/despesa`
- Responsabilidade: Endpoint que cria despesa manual banco e devolve a resposta HTTP correspondente.

### `criar_pagamento_parcial_banco(request: Request, cliente_id: int=Form(...), conta_id: int=Form(...), valor: Decimal=Form(...), data_pagamento: date=Form(...), observacao: str=Form(''), db: Session=Depends(get_db), usuario: Usuario=Depends(get_usuario_atual))`

- Local: [criar_pagamento_parcial_banco](../app/routers/conciliacao_banco.py#L842)
- Rota: `POST /conciliacao/banco/manual/pagamento-parcial`
- Responsabilidade: Endpoint que cria pagamento parcial banco e devolve a resposta HTTP correspondente.

### `importar_lancamentos_banco(request: Request, cliente_id: int=Form(...), arquivo: UploadFile=File(...), db: Session=Depends(get_db), usuario: Usuario=Depends(get_usuario_atual))`

- Local: [importar_lancamentos_banco](../app/routers/conciliacao_banco.py#L882)
- Rota: `POST /conciliacao/banco/importar-lancamentos`
- Responsabilidade: Endpoint que importa lancamentos banco e devolve a resposta HTTP correspondente.

### `importar_extrato_banco(request: Request, cliente_id: int=Form(...), arquivo: UploadFile=File(...), db: Session=Depends(get_db), usuario: Usuario=Depends(get_usuario_atual))`

- Local: [importar_extrato_banco](../app/routers/conciliacao_banco.py#L925)
- Rota: `POST /conciliacao/banco/importar-extrato`
- Responsabilidade: Endpoint que importa extrato banco e devolve a resposta HTTP correspondente.

### `conciliar_todos_prontos(cliente_id: int=Form(...), db: Session=Depends(get_db), usuario: Usuario=Depends(get_usuario_atual))`

- Local: [conciliar_todos_prontos](../app/routers/conciliacao_banco.py#L981)
- Rota: `POST /conciliacao/banco/conciliar-todos-prontos`
- Responsabilidade: Endpoint que concilia todos prontos e devolve a resposta HTTP correspondente.

### `conciliar_movimentacao(mov_id: int, cliente_id: int=Form(...), atendimento_id: int=Form(...), origem: str=Form('sugestao'), db: Session=Depends(get_db), usuario: Usuario=Depends(get_usuario_atual))`

- Local: [conciliar_movimentacao](../app/routers/conciliacao_banco.py#L996)
- Rota: `POST /conciliacao/banco/movimentacao/{mov_id}/conciliar`
- Responsabilidade: Endpoint que concilia movimentacao e devolve a resposta HTTP correspondente.

### `revisar_movimentacao(mov_id: int, cliente_id: int=Form(...), db: Session=Depends(get_db), usuario: Usuario=Depends(get_usuario_atual))`

- Local: [revisar_movimentacao](../app/routers/conciliacao_banco.py#L1019)
- Rota: `POST /conciliacao/banco/movimentacao/{mov_id}/revisar`
- Responsabilidade: Endpoint que executa o fluxo revisar movimentacao e devolve a resposta HTTP correspondente.

### `arquivar_movimentacao(mov_id: int, cliente_id: int=Form(...), db: Session=Depends(get_db), usuario: Usuario=Depends(get_usuario_atual))`

- Local: [arquivar_movimentacao](../app/routers/conciliacao_banco.py#L1037)
- Rota: `POST /conciliacao/banco/movimentacao/{mov_id}/arquivar`
- Responsabilidade: Endpoint que arquiva movimentacao e devolve a resposta HTTP correspondente.

### `restaurar_movimentacao(mov_id: int, cliente_id: int=Form(...), db: Session=Depends(get_db), usuario: Usuario=Depends(get_usuario_atual))`

- Local: [restaurar_movimentacao](../app/routers/conciliacao_banco.py#L1055)
- Rota: `POST /conciliacao/banco/movimentacao/{mov_id}/restaurar`
- Responsabilidade: Endpoint que restaura movimentacao e devolve a resposta HTTP correspondente.

### `arquivar_lancamento_sistema(atendimento_id: int, cliente_id: int=Form(...), db: Session=Depends(get_db), usuario: Usuario=Depends(get_usuario_atual))`

- Local: [arquivar_lancamento_sistema](../app/routers/conciliacao_banco.py#L1070)
- Rota: `POST /conciliacao/banco/lancamento/{atendimento_id}/arquivar`
- Responsabilidade: Endpoint que arquiva lancamento sistema e devolve a resposta HTTP correspondente.

### `restaurar_lancamento_sistema(atendimento_id: int, cliente_id: int=Form(...), db: Session=Depends(get_db), usuario: Usuario=Depends(get_usuario_atual))`

- Local: [restaurar_lancamento_sistema](../app/routers/conciliacao_banco.py#L1088)
- Rota: `POST /conciliacao/banco/lancamento/{atendimento_id}/restaurar`
- Responsabilidade: Endpoint que restaura lancamento sistema e devolve a resposta HTTP correspondente.

### `arquivar_conta_sistema(conta_id: int, cliente_id: int=Form(...), db: Session=Depends(get_db), usuario: Usuario=Depends(get_usuario_atual))`

- Local: [arquivar_conta_sistema](../app/routers/conciliacao_banco.py#L1103)
- Rota: `POST /conciliacao/banco/conta/{conta_id}/arquivar`
- Responsabilidade: Endpoint que arquiva conta sistema e devolve a resposta HTTP correspondente.

### `restaurar_conta_sistema(conta_id: int, cliente_id: int=Form(...), db: Session=Depends(get_db), usuario: Usuario=Depends(get_usuario_atual))`

- Local: [restaurar_conta_sistema](../app/routers/conciliacao_banco.py#L1121)
- Rota: `POST /conciliacao/banco/conta/{conta_id}/restaurar`
- Responsabilidade: Endpoint que restaura conta sistema e devolve a resposta HTTP correspondente.

### `desvincular_movimentacao_pix(mov_id: int, cliente_id: int=Form(...), db: Session=Depends(get_db), usuario: Usuario=Depends(get_usuario_atual))`

- Local: [desvincular_movimentacao_pix](../app/routers/conciliacao_banco.py#L1136)
- Rota: `POST /conciliacao/banco/movimentacao/{mov_id}/desvincular`
- Responsabilidade: Endpoint que executa o fluxo desvincular movimentacao pix e devolve a resposta HTTP correspondente.

### `criar_e_conciliar(mov_id: int, cliente_id: int=Form(...), data_atendimento: str=Form(...), nome_paciente: str=Form(''), cpf_paciente: str=Form(''), medico: str=Form(''), especialidade: str=Form(''), tipo_servico: str=Form(''), descricao_servico: str=Form(''), observacao: str=Form(''), db: Session=Depends(get_db), usuario: Usuario=Depends(get_usuario_atual))`

- Local: [criar_e_conciliar](../app/routers/conciliacao_banco.py#L1163)
- Rota: `POST /conciliacao/banco/movimentacao/{mov_id}/criar-e-conciliar`
- Responsabilidade: Endpoint que cria e conciliar e devolve a resposta HTTP correspondente.

### `importar_conta_corrente(request: Request, cliente_id: int=Form(...), arquivo: UploadFile=File(...), db: Session=Depends(get_db), usuario: Usuario=Depends(get_usuario_atual))`

- Local: [importar_conta_corrente](../app/routers/conciliacao_banco.py#L1224)
- Rota: `POST /conciliacao/banco/conta-corrente/importar`
- Responsabilidade: Endpoint que importa conta corrente e devolve a resposta HTTP correspondente.

### `conciliar_lote_com_banco(lote_id: int, cliente_id: int=Form(...), mov_id: int=Form(...), db: Session=Depends(get_db), usuario: Usuario=Depends(get_usuario_atual))`

- Local: [conciliar_lote_com_banco](../app/routers/conciliacao_banco.py#L1266)
- Rota: `POST /conciliacao/banco/lote/{lote_id}/conciliar`
- Responsabilidade: Endpoint que concilia lote com banco e devolve a resposta HTTP correspondente.

### `auto_match_lotes(cliente_id: int=Form(...), db: Session=Depends(get_db), usuario: Usuario=Depends(get_usuario_atual))`

- Local: [auto_match_lotes](../app/routers/conciliacao_banco.py#L1291)
- Rota: `POST /conciliacao/banco/lote/auto-match`
- Responsabilidade: Auto-concilia lotes pendentes com MovimentacaoBancaria de valor exato.

### `desvincular_lote(lote_id: int, cliente_id: int=Form(...), db: Session=Depends(get_db), usuario: Usuario=Depends(get_usuario_atual))`

- Local: [desvincular_lote](../app/routers/conciliacao_banco.py#L1306)
- Rota: `POST /conciliacao/banco/lote/{lote_id}/desvincular`
- Responsabilidade: Endpoint que executa o fluxo desvincular lote e devolve a resposta HTTP correspondente.

### `conciliar_saida_com_conta(mov_id: int, cliente_id: int=Form(...), conta_id: int=Form(...), db: Session=Depends(get_db), usuario: Usuario=Depends(get_usuario_atual))`

- Local: [conciliar_saida_com_conta](../app/routers/conciliacao_banco.py#L1333)
- Rota: `POST /conciliacao/banco/saida/{mov_id}/conciliar`
- Responsabilidade: Endpoint que concilia saida com conta e devolve a resposta HTTP correspondente.

### `desvincular_saida(mov_id: int, cliente_id: int=Form(...), db: Session=Depends(get_db), usuario: Usuario=Depends(get_usuario_atual))`

- Local: [desvincular_saida](../app/routers/conciliacao_banco.py#L1362)
- Rota: `POST /conciliacao/banco/saida/{mov_id}/desvincular`
- Responsabilidade: Endpoint que executa o fluxo desvincular saida e devolve a resposta HTTP correspondente.

### `auto_match_saidas(cliente_id: int=Form(...), db: Session=Depends(get_db), usuario: Usuario=Depends(get_usuario_atual))`

- Local: [auto_match_saidas](../app/routers/conciliacao_banco.py#L1396)
- Rota: `POST /conciliacao/banco/saida/auto-match`
- Responsabilidade: Concilia em lote, por acao do usuario, saidas com contas de valor exato.

## `app/routers/contas_pagar.py`

### `clientes_do_usuario(db: Session, usuario: Usuario)`

- Local: [clientes_do_usuario](../app/routers/contas_pagar.py#L29)
- Responsabilidade: Função auxiliar responsável pelo fluxo “clientes do usuario”.

### `_ids_clientes_do_usuario(db: Session, usuario: Usuario) -> list[int]`

- Local: [_ids_clientes_do_usuario](../app/routers/contas_pagar.py#L38)
- Responsabilidade: Função auxiliar responsável pelo fluxo “ids clientes do usuario”.

### `_key_centro_custo(cc: CentroCusto) -> str`

- Local: [_key_centro_custo](../app/routers/contas_pagar.py#L42)
- Responsabilidade: Função auxiliar responsável pelo fluxo “key centro custo”.

### `_centros_custo_por_cliente(db: Session, cliente_ids: list[int]) -> dict[int, list[dict]]`

- Local: [_centros_custo_por_cliente](../app/routers/contas_pagar.py#L47)
- Responsabilidade: Função auxiliar responsável pelo fluxo “centros custo por cliente”.

### `_categoria_nome_com_centros(centros_por_cliente: dict[int, list[dict]]) -> dict[str, str]`

- Local: [_categoria_nome_com_centros](../app/routers/contas_pagar.py#L66)
- Responsabilidade: Função auxiliar responsável pelo fluxo “categoria nome com centros”.

### `_categoria_dre_valida(db: Session, cliente_id: int, categoria_dre: Optional[str]) -> str | None`

- Local: [_categoria_dre_valida](../app/routers/contas_pagar.py#L75)
- Responsabilidade: Função auxiliar responsável pelo fluxo “categoria dre valida”.

### `_decimal_rateio(valor: str) -> Decimal | None`

- Local: [_decimal_rateio](../app/routers/contas_pagar.py#L88)
- Responsabilidade: Função auxiliar responsável pelo fluxo “decimal rateio”.

### `_centro_por_key(db: Session, cliente_id: int, key: str) -> CentroCusto | None`

- Local: [_centro_por_key](../app/routers/contas_pagar.py#L95)
- Responsabilidade: Função auxiliar responsável pelo fluxo “centro por key”.

### `_montar_rateios_conta(db: Session, cliente_id: int, valor_total: Decimal, categorias: List[str], percentuais: List[str]) -> list[dict]`

- Local: [_montar_rateios_conta](../app/routers/contas_pagar.py#L106)
- Responsabilidade: Função auxiliar que monta rateios conta.

### `listar_contas(request: Request, cliente_id: Optional[int]=None, flash: Optional[str]=None, db: Session=Depends(get_db), usuario: Usuario=Depends(get_usuario_atual))`

- Local: [listar_contas](../app/routers/contas_pagar.py#L140)
- Rota: `GET /contas-pagar`
- Responsabilidade: Endpoint que lista contas e devolve a resposta HTTP correspondente.

### `baixar_documento_conta(conta_id: int, db: Session=Depends(get_db), usuario: Usuario=Depends(get_usuario_atual))`

- Local: [baixar_documento_conta](../app/routers/contas_pagar.py#L176)
- Rota: `GET /contas-pagar/{conta_id}/documento`
- Responsabilidade: Endpoint que executa o fluxo baixar documento conta e devolve a resposta HTTP correspondente.

### `criar_conta(cliente_id: int=Form(...), descricao: str=Form(...), fornecedor: Optional[str]=Form(None), tipo: str=Form('pontual'), valor: Decimal=Form(...), vencimento: date=Form(...), categoria_dre: Optional[str]=Form(None), rateio_centro_custo_key: List[str]=Form(default=[]), rateio_percentual: List[str]=Form(default=[]), especialidade: Optional[str]=Form(None), observacao: Optional[str]=Form(None), documento: Optional[UploadFile]=File(None), db: Session=Depends(get_db), usuario: Usuario=Depends(get_usuario_atual))`

- Local: [criar_conta](../app/routers/contas_pagar.py#L200)
- Rota: `POST /contas-pagar`
- Responsabilidade: Endpoint que cria conta e devolve a resposta HTTP correspondente.

### `importar_contas(request: Request, cliente_id: int=Form(...), arquivo: UploadFile=File(...), db: Session=Depends(get_db), usuario: Usuario=Depends(get_usuario_atual))`

- Local: [importar_contas](../app/routers/contas_pagar.py#L277)
- Rota: `POST /contas-pagar/importar`
- Responsabilidade: Endpoint que importa contas e devolve a resposta HTTP correspondente.

### `_norm(nome: str) -> str`

- Local: [importar_contas._norm](../app/routers/contas_pagar.py#L288)
- Responsabilidade: Função auxiliar responsável pelo fluxo “norm”.

### `_col(df, opcoes)`

- Local: [importar_contas._col](../app/routers/contas_pagar.py#L293)
- Responsabilidade: Função auxiliar responsável pelo fluxo “col”.

### `agendar_pagamento(conta_id: int, db: Session=Depends(get_db), usuario: Usuario=Depends(get_usuario_atual))`

- Local: [agendar_pagamento](../app/routers/contas_pagar.py#L407)
- Rota: `POST /contas-pagar/{conta_id}/agendar`
- Responsabilidade: Endpoint que executa o fluxo agendar pagamento e devolve a resposta HTTP correspondente.

### `cancelar_conta(conta_id: int, db: Session=Depends(get_db), usuario: Usuario=Depends(get_usuario_atual))`

- Local: [cancelar_conta](../app/routers/contas_pagar.py#L432)
- Rota: `POST /contas-pagar/{conta_id}/cancelar`
- Responsabilidade: Endpoint que executa o fluxo cancelar conta e devolve a resposta HTTP correspondente.

## `app/routers/contas_pagar_conciliacao.py`

### `clientes_do_usuario(db: Session, usuario: Usuario)`

- Local: [clientes_do_usuario](../app/routers/contas_pagar_conciliacao.py#L32)
- Responsabilidade: Função auxiliar responsável pelo fluxo “clientes do usuario”.

### `_contas_pendentes(db: Session, cliente_id: int)`

- Local: [_contas_pendentes](../app/routers/contas_pagar_conciliacao.py#L41)
- Responsabilidade: Função auxiliar responsável pelo fluxo “contas pendentes”.

### `_sugestao_conta(valor_banco: Decimal, data_banco, contas: list)`

- Local: [_sugestao_conta](../app/routers/contas_pagar_conciliacao.py#L53)
- Responsabilidade: Função auxiliar responsável pelo fluxo “sugestao conta”.

### `pagina_conciliacao_cartao_pagar(request: Request, cliente_id: Optional[int]=None, buscar_mov: Optional[int]=Query(default=None), termo: Optional[str]=Query(default=None), db: Session=Depends(get_db), usuario: Usuario=Depends(get_usuario_atual))`

- Local: [pagina_conciliacao_cartao_pagar](../app/routers/contas_pagar_conciliacao.py#L73)
- Rota: `GET /contas-pagar/conciliacao-cartao`
- Responsabilidade: Endpoint que renderiza a página de conciliacao cartao pagar e devolve a resposta HTTP correspondente.

### `importar_cartao_pagar(request: Request, cliente_id: int=Form(...), arquivo: UploadFile=File(...), db: Session=Depends(get_db), usuario: Usuario=Depends(get_usuario_atual))`

- Local: [importar_cartao_pagar](../app/routers/contas_pagar_conciliacao.py#L143)
- Rota: `POST /contas-pagar/conciliacao-cartao/processar`
- Responsabilidade: Endpoint que importa cartao pagar e devolve a resposta HTTP correspondente.

### `_col(names)`

- Local: [importar_cartao_pagar._col](../app/routers/contas_pagar_conciliacao.py#L170)
- Responsabilidade: Função auxiliar responsável pelo fluxo “col”.

### `conciliar_cartao_pagar(mov_id: int, cliente_id: int=Form(...), conta_pagar_id: int=Form(...), db: Session=Depends(get_db), usuario: Usuario=Depends(get_usuario_atual))`

- Local: [conciliar_cartao_pagar](../app/routers/contas_pagar_conciliacao.py#L237)
- Rota: `POST /contas-pagar/conciliacao-cartao/mov/{mov_id}/conciliar`
- Responsabilidade: Endpoint que concilia cartao pagar e devolve a resposta HTTP correspondente.

### `ignorar_cartao_pagar(mov_id: int, cliente_id: int=Form(...), db: Session=Depends(get_db), usuario: Usuario=Depends(get_usuario_atual))`

- Local: [ignorar_cartao_pagar](../app/routers/contas_pagar_conciliacao.py#L267)
- Rota: `POST /contas-pagar/conciliacao-cartao/mov/{mov_id}/ignorar`
- Responsabilidade: Endpoint que ignora cartao pagar e devolve a resposta HTTP correspondente.

### `pagina_conciliacao_banco_pagar(request: Request, cliente_id: Optional[int]=None, buscar_linha: Optional[int]=Query(default=None), termo: Optional[str]=Query(default=None), db: Session=Depends(get_db), usuario: Usuario=Depends(get_usuario_atual))`

- Local: [pagina_conciliacao_banco_pagar](../app/routers/contas_pagar_conciliacao.py#L289)
- Rota: `GET /contas-pagar/conciliacao-banco`
- Responsabilidade: Endpoint que renderiza a página de conciliacao banco pagar e devolve a resposta HTTP correspondente.

### `importar_banco_pagar(request: Request, cliente_id: int=Form(...), arquivo: UploadFile=File(...), col_data: str=Form('data'), col_descricao: str=Form('descricao'), col_valor: str=Form('valor'), col_tipo: str=Form('tipo'), db: Session=Depends(get_db), usuario: Usuario=Depends(get_usuario_atual))`

- Local: [importar_banco_pagar](../app/routers/contas_pagar_conciliacao.py#L356)
- Rota: `POST /contas-pagar/conciliacao-banco/importar`
- Responsabilidade: Endpoint que importa banco pagar e devolve a resposta HTTP correspondente.

### `_col(names)`

- Local: [importar_banco_pagar._col](../app/routers/contas_pagar_conciliacao.py#L387)
- Responsabilidade: Função auxiliar responsável pelo fluxo “col”.

### `conciliar_linha_banco_pagar(linha_id: int, cliente_id: int=Form(...), conta_pagar_id: int=Form(...), db: Session=Depends(get_db), usuario: Usuario=Depends(get_usuario_atual))`

- Local: [conciliar_linha_banco_pagar](../app/routers/contas_pagar_conciliacao.py#L445)
- Rota: `POST /contas-pagar/conciliacao-banco/linha/{linha_id}/conciliar`
- Responsabilidade: Endpoint que concilia linha banco pagar e devolve a resposta HTTP correspondente.

### `ignorar_linha_banco_pagar(linha_id: int, cliente_id: int=Form(...), db: Session=Depends(get_db), usuario: Usuario=Depends(get_usuario_atual))`

- Local: [ignorar_linha_banco_pagar](../app/routers/contas_pagar_conciliacao.py#L475)
- Rota: `POST /contas-pagar/conciliacao-banco/linha/{linha_id}/ignorar`
- Responsabilidade: Endpoint que ignora linha banco pagar e devolve a resposta HTTP correspondente.

## `app/routers/dashboard.py`

### `dashboard(request: Request, db: Session=Depends(get_db), usuario: Usuario=Depends(get_usuario_atual))`

- Local: [dashboard](../app/routers/dashboard.py#L20)
- Rota: `GET /`
- Responsabilidade: Endpoint que executa o fluxo dashboard e devolve a resposta HTTP correspondente.

### `_alertas_recorrentes(db: Session, hoje: date, ids_clientes: list) -> list`

- Local: [_alertas_recorrentes](../app/routers/dashboard.py#L47)
- Responsabilidade: Retorna contas recorrentes cujo vencimento está dentro da janela de aviso.

### `_dashboard_coordenador(db: Session, hoje: date, cliente_ativo_id: int | None=None) -> dict`

- Local: [_dashboard_coordenador](../app/routers/dashboard.py#L72)
- Responsabilidade: Função auxiliar responsável pelo fluxo “dashboard coordenador”.

### `_dashboard_funcionario(db: Session, hoje: date, usuario: Usuario, cliente_ativo_id: int | None=None) -> dict`

- Local: [_dashboard_funcionario](../app/routers/dashboard.py#L179)
- Responsabilidade: Função auxiliar responsável pelo fluxo “dashboard funcionario”.

## `app/routers/fechamento.py`

### `clientes_do_usuario(db: Session, usuario: Usuario)`

- Local: [clientes_do_usuario](../app/routers/fechamento.py#L45)
- Responsabilidade: Função auxiliar responsável pelo fluxo “clientes do usuario”.

### `formatar_brl(valor: Decimal) -> str`

- Local: [formatar_brl](../app/routers/fechamento.py#L54)
- Responsabilidade: Função auxiliar que formata brl.

### `_parse_data_aprovacao(data: Optional[str]) -> tuple[date, str]`

- Local: [_parse_data_aprovacao](../app/routers/fechamento.py#L58)
- Responsabilidade: Função auxiliar responsável pelo fluxo “parse data aprovacao”.

### `_parse_saldo(saldo: Optional[str]) -> Decimal`

- Local: [_parse_saldo](../app/routers/fechamento.py#L68)
- Responsabilidade: Função auxiliar responsável pelo fluxo “parse saldo”.

### `_contas_para_aprovacao(db: Session, cliente_id: int, data_obj: date) -> list[ContaPagar]`

- Local: [_contas_para_aprovacao](../app/routers/fechamento.py#L77)
- Responsabilidade: Função auxiliar responsável pelo fluxo “contas para aprovacao”.

### `_p(texto) -> str`

- Local: [_p](../app/routers/fechamento.py#L90)
- Responsabilidade: Função auxiliar responsável pelo fluxo “p”.

### `_gerar_pdf_aprovacao(cliente: ClienteBPO, contas: list[ContaPagar], data_obj: date, saldo_conta: Decimal, total_despesas: Decimal, saldo_final: Decimal, usuario: Usuario) -> bytes`

- Local: [_gerar_pdf_aprovacao](../app/routers/fechamento.py#L94)
- Responsabilidade: Função auxiliar que gera pdf aprovacao.

### `pagina_fechamento(request: Request, cliente_id: Optional[int]=None, data: Optional[str]=None, saldo: Optional[str]=None, db: Session=Depends(get_db), usuario: Usuario=Depends(get_usuario_atual))`

- Local: [pagina_fechamento](../app/routers/fechamento.py#L263)
- Rota: `GET /fechamento`
- Responsabilidade: Endpoint que renderiza a página de fechamento e devolve a resposta HTTP correspondente.

### `pdf_aprovacao(request: Request, cliente_id: int, data: Optional[str]=None, saldo: Optional[str]=None, db: Session=Depends(get_db), usuario: Usuario=Depends(get_usuario_atual))`

- Local: [pdf_aprovacao](../app/routers/fechamento.py#L337)
- Rota: `GET /fechamento/aprovacao.pdf`
- Responsabilidade: Endpoint que executa o fluxo pdf aprovacao e devolve a resposta HTTP correspondente.

### `fechamento_mensal(request: Request, cliente_id: Optional[int]=None, data_inicio: Optional[str]=None, data_fim: Optional[str]=None, db: Session=Depends(get_db), usuario: Usuario=Depends(get_usuario_atual))`

- Local: [fechamento_mensal](../app/routers/fechamento.py#L381)
- Rota: `GET /fechamento/mensal`
- Responsabilidade: Endpoint que executa o fluxo fechamento mensal e devolve a resposta HTTP correspondente.

## `app/routers/gestao.py`

### `clientes_do_usuario(db: Session, usuario: Usuario)`

- Local: [clientes_do_usuario](../app/routers/gestao.py#L23)
- Responsabilidade: Função auxiliar responsável pelo fluxo “clientes do usuario”.

### `_brl(v) -> str`

- Local: [_brl](../app/routers/gestao.py#L32)
- Responsabilidade: Função auxiliar responsável pelo fluxo “brl”.

### `_pct(valor, base) -> Decimal`

- Local: [_pct](../app/routers/gestao.py#L36)
- Responsabilidade: Função auxiliar responsável pelo fluxo “pct”.

### `_retroceder_mes(mes: int, ano: int, quantidade: int=1) -> tuple[int, int]`

- Local: [_retroceder_mes](../app/routers/gestao.py#L44)
- Responsabilidade: Função auxiliar responsável pelo fluxo “retroceder mes”.

### `_meses_no_intervalo(inicio: date, fim: date) -> list[tuple[int, int]]`

- Local: [_meses_no_intervalo](../app/routers/gestao.py#L54)
- Responsabilidade: Função auxiliar responsável pelo fluxo “meses no intervalo”.

### `_resolver_periodo(periodo: str, mes: int, ano: int, hoje: date) -> tuple[date, date, str]`

- Local: [_resolver_periodo](../app/routers/gestao.py#L68)
- Responsabilidade: Função auxiliar que resolve periodo.

### `_key_centro_custo(cc: CentroCusto | None) -> str | None`

- Local: [_key_centro_custo](../app/routers/gestao.py#L83)
- Responsabilidade: Função auxiliar responsável pelo fluxo “key centro custo”.

### `_grupos_dre_cliente(db: Session, cliente_id: int | None) -> list[dict]`

- Local: [_grupos_dre_cliente](../app/routers/gestao.py#L90)
- Responsabilidade: Função auxiliar responsável pelo fluxo “grupos dre cliente”.

### `_carregar_dre_periodo(db: Session, cliente_id: int, mes: int, ano: int, inicio: date | None=None, fim: date | None=None) -> dict`

- Local: [_carregar_dre_periodo](../app/routers/gestao.py#L132)
- Responsabilidade: Função auxiliar que carrega dre periodo.

### `_saldo_atual(db: Session, cliente_id: int, fim: date) -> dict | None`

- Local: [_saldo_atual](../app/routers/gestao.py#L320)
- Responsabilidade: Função auxiliar responsável pelo fluxo “saldo atual”.

### `_proximos_vencimentos(db: Session, cliente_id: int, hoje: date) -> dict`

- Local: [_proximos_vencimentos](../app/routers/gestao.py#L338)
- Responsabilidade: Função auxiliar responsável pelo fluxo “proximos vencimentos”.

### `resumo(lista)`

- Local: [_proximos_vencimentos.resumo](../app/routers/gestao.py#L359)
- Responsabilidade: Função auxiliar responsável pelo fluxo “resumo”.

### `_insights_dre(dre_atual: dict, comparativo: dict, vencimentos: dict | None=None) -> list[dict]`

- Local: [_insights_dre](../app/routers/gestao.py#L374)
- Responsabilidade: Função auxiliar responsável pelo fluxo “insights dre”.

### `gestao_receitas(request: Request, cliente_id: Optional[int]=None, mes: Optional[int]=None, ano: Optional[int]=None, db: Session=Depends(get_db), usuario: Usuario=Depends(get_usuario_atual))`

- Local: [gestao_receitas](../app/routers/gestao.py#L443)
- Rota: `GET /gestao/receitas`
- Responsabilidade: Endpoint que executa o fluxo gestao receitas e devolve a resposta HTTP correspondente.

### `gestao_despesas(request: Request, cliente_id: Optional[int]=None, mes: Optional[int]=None, ano: Optional[int]=None, db: Session=Depends(get_db), usuario: Usuario=Depends(get_usuario_atual))`

- Local: [gestao_despesas](../app/routers/gestao.py#L495)
- Rota: `GET /gestao/despesas`
- Responsabilidade: Endpoint que executa o fluxo gestao despesas e devolve a resposta HTTP correspondente.

### `gestao_orcamento(request: Request, cliente_id: Optional[int]=None, mes: Optional[int]=None, ano: Optional[int]=None, db: Session=Depends(get_db), usuario: Usuario=Depends(get_usuario_atual))`

- Local: [gestao_orcamento](../app/routers/gestao.py#L545)
- Rota: `GET /gestao/orcamento`
- Responsabilidade: Endpoint que executa o fluxo gestao orcamento e devolve a resposta HTTP correspondente.

### `salvar_orcamento(request: Request, cliente_id: int=Form(...), mes: int=Form(...), ano: int=Form(...), db: Session=Depends(get_db), usuario: Usuario=Depends(get_usuario_atual))`

- Local: [salvar_orcamento](../app/routers/gestao.py#L622)
- Rota: `POST /gestao/orcamento`
- Responsabilidade: Endpoint que salva orcamento e devolve a resposta HTTP correspondente.

### `gestao_dre_apresentacao(request: Request, cliente_id: int, mes: Optional[int]=None, ano: Optional[int]=None, periodo: str='mes', db: Session=Depends(get_db), usuario: Usuario=Depends(get_usuario_atual))`

- Local: [gestao_dre_apresentacao](../app/routers/gestao.py#L677)
- Rota: `GET /gestao/dre/apresentacao`
- Responsabilidade: Endpoint que executa o fluxo gestao dre apresentacao e devolve a resposta HTTP correspondente.

### `gestao_dre(request: Request, cliente_id: Optional[int]=None, mes: Optional[int]=None, ano: Optional[int]=None, periodo: str='mes', visao: str='simples', db: Session=Depends(get_db), usuario: Usuario=Depends(get_usuario_atual))`

- Local: [gestao_dre](../app/routers/gestao.py#L738)
- Rota: `GET /gestao/dre`
- Responsabilidade: Endpoint que executa o fluxo gestao dre e devolve a resposta HTTP correspondente.

## `app/routers/lancamentos.py`

### `formatar_brl(valor) -> str`

- Local: [formatar_brl](../app/routers/lancamentos.py#L21)
- Responsabilidade: Função auxiliar que formata brl.

### `clientes_do_usuario(db: Session, usuario: Usuario)`

- Local: [clientes_do_usuario](../app/routers/lancamentos.py#L27)
- Responsabilidade: Função auxiliar responsável pelo fluxo “clientes do usuario”.

### `_calcular_intervalos(forma_pagamento: str, parcela_total: int, recorrencia: Optional[str])`

- Local: [_calcular_intervalos](../app/routers/lancamentos.py#L36)
- Responsabilidade: Função auxiliar que calcula intervalos.

### `_str(lst: List[str], i: int) -> str`

- Local: [_str](../app/routers/lancamentos.py#L50)
- Responsabilidade: Função auxiliar responsável pelo fluxo “str”.

### `_decimal(lst: List[str], i: int) -> Optional[Decimal]`

- Local: [_decimal](../app/routers/lancamentos.py#L54)
- Responsabilidade: Função auxiliar responsável pelo fluxo “decimal”.

### `_parse_rateios_json(raw: str, centros_validos: dict[int, CentroCusto], valor: Decimal) -> list[dict]`

- Local: [_parse_rateios_json](../app/routers/lancamentos.py#L62)
- Responsabilidade: Função auxiliar responsável pelo fluxo “parse rateios json”.

### `_int(lst: List[str], i: int, default: int=1) -> int`

- Local: [_int](../app/routers/lancamentos.py#L99)
- Responsabilidade: Função auxiliar responsável pelo fluxo “int”.

### `_taxa_cartao(db: Session, cliente_id: int, bandeira: str) -> Optional[Decimal]`

- Local: [_taxa_cartao](../app/routers/lancamentos.py#L107)
- Responsabilidade: Função auxiliar responsável pelo fluxo “taxa cartao”.

### `listar_lancamentos(request: Request, cliente_id: Optional[int]=None, data_inicio: Optional[str]=None, data_fim: Optional[str]=None, flash: Optional[str]=None, db: Session=Depends(get_db), usuario: Usuario=Depends(get_usuario_atual))`

- Local: [listar_lancamentos](../app/routers/lancamentos.py#L131)
- Rota: `GET /lancamentos`
- Responsabilidade: Endpoint que lista lancamentos e devolve a resposta HTTP correspondente.

### `criar_lancamentos(request: Request, cliente_id: int=Form(...), data_atendimento: date=Form(...), nome_paciente: List[str]=Form(default=[]), cpf_paciente: List[str]=Form(default=[]), centro_custo_id: List[str]=Form(default=[]), rateios_json: List[str]=Form(default=[]), especialidade: List[str]=Form(default=[]), descricao_servico: List[str]=Form(default=[]), valor_servico: List[str]=Form(default=[]), forma_pagamento: List[str]=Form(default=[]), condicao_pagamento: List[str]=Form(default=[]), parcela_total: List[str]=Form(default=[]), recorrencia: List[str]=Form(default=[]), ultimos_digitos_cartao: List[str]=Form(default=[]), bandeira_cartao: List[str]=Form(default=[]), percentual_medico: List[str]=Form(default=[]), observacao: List[str]=Form(default=[]), db: Session=Depends(get_db), usuario: Usuario=Depends(get_usuario_atual))`

- Local: [criar_lancamentos](../app/routers/lancamentos.py#L191)
- Rota: `POST /lancamentos`
- Responsabilidade: Endpoint que cria lancamentos e devolve a resposta HTTP correspondente.

### `form_editar_lancamento(at_id: int, request: Request, db: Session=Depends(get_db), usuario: Usuario=Depends(get_usuario_atual))`

- Local: [form_editar_lancamento](../app/routers/lancamentos.py#L340)
- Rota: `GET /lancamentos/{at_id}/editar`
- Responsabilidade: Endpoint que executa o fluxo form editar lancamento e devolve a resposta HTTP correspondente.

### `salvar_edicao_lancamento(at_id: int, request: Request, data_atendimento: date=Form(...), nome_paciente: str=Form(''), cpf_paciente: str=Form(''), centro_custo_id: str=Form(''), especialidade: str=Form(''), descricao_servico: str=Form(''), valor_servico: str=Form(...), forma_pagamento: str=Form(''), condicao_pagamento: str=Form('avista'), parcela_numero: int=Form(1), parcela_total: int=Form(1), ultimos_digitos_cartao: str=Form(''), bandeira_cartao: str=Form(''), percentual_medico: str=Form(''), observacao: str=Form(''), db: Session=Depends(get_db), usuario: Usuario=Depends(get_usuario_atual))`

- Local: [salvar_edicao_lancamento](../app/routers/lancamentos.py#L367)
- Rota: `POST /lancamentos/{at_id}/editar`
- Responsabilidade: Endpoint que salva edicao lancamento e devolve a resposta HTTP correspondente.

### `excluir_lancamento(at_id: int, request: Request, cliente_id: int=Form(...), db: Session=Depends(get_db), usuario: Usuario=Depends(get_usuario_atual))`

- Local: [excluir_lancamento](../app/routers/lancamentos.py#L465)
- Rota: `POST /lancamentos/{at_id}/excluir`
- Responsabilidade: Endpoint que exclui lancamento e devolve a resposta HTTP correspondente.

## `app/routers/logs.py`

### `pagina_logs(request: Request, modulo: Optional[str]=Query(None), usuario_id: Optional[str]=Query(None), data_inicio: Optional[str]=Query(None), data_fim: Optional[str]=Query(None), db: Session=Depends(get_db), usuario: Usuario=Depends(requer_coordenador))`

- Local: [pagina_logs](../app/routers/logs.py#L19)
- Rota: `GET /logs`
- Responsabilidade: Endpoint que renderiza a página de logs e devolve a resposta HTTP correspondente.

## `app/routers/rotinas.py`

### `_render_li(tarefa: TarefaRotina, pode_reverter: bool) -> str`

- Local: [_render_li](../app/routers/rotinas.py#L75)
- Responsabilidade: Função auxiliar responsável pelo fluxo “render li”.

### `clientes_do_usuario(db: Session, usuario: Usuario)`

- Local: [clientes_do_usuario](../app/routers/rotinas.py#L111)
- Responsabilidade: Função auxiliar responsável pelo fluxo “clientes do usuario”.

### `listar_rotinas(request: Request, cliente_id: Optional[int]=None, db: Session=Depends(get_db), usuario: Usuario=Depends(get_usuario_atual))`

- Local: [listar_rotinas](../app/routers/rotinas.py#L125)
- Rota: `GET /rotinas`
- Responsabilidade: Endpoint que lista rotinas e devolve a resposta HTTP correspondente.

### `criar_rotina(cliente_id: int=Form(...), funcionario_id: int=Form(...), data: date=Form(...), descricao: str=Form(...), horario_previsto: Optional[str]=Form(None), db: Session=Depends(get_db), usuario: Usuario=Depends(get_usuario_atual))`

- Local: [criar_rotina](../app/routers/rotinas.py#L212)
- Rota: `POST /rotinas`
- Responsabilidade: Endpoint que cria rotina e devolve a resposta HTTP correspondente.

### `toggle_tarefa(tarefa_id: int, db: Session=Depends(get_db), usuario: Usuario=Depends(get_usuario_atual))`

- Local: [toggle_tarefa](../app/routers/rotinas.py#L237)
- Rota: `POST /rotinas/{tarefa_id}/toggle`
- Responsabilidade: Endpoint que alterna o estado de tarefa e devolve a resposta HTTP correspondente.

### `excluir_tarefa(tarefa_id: int, db: Session=Depends(get_db), usuario: Usuario=Depends(get_usuario_atual))`

- Local: [excluir_tarefa](../app/routers/rotinas.py#L265)
- Rota: `POST /rotinas/{tarefa_id}/excluir`
- Responsabilidade: Endpoint que exclui tarefa e devolve a resposta HTTP correspondente.

### `criar_recorrente(cliente_id: int=Form(...), descricao: str=Form(...), fornecedor: Optional[str]=Form(None), valor: Optional[str]=Form(None), dia_vencimento: int=Form(...), dias_antecedencia: int=Form(3), email_destino: Optional[str]=Form(None), db: Session=Depends(get_db), usuario: Usuario=Depends(get_usuario_atual))`

- Local: [criar_recorrente](../app/routers/rotinas.py#L287)
- Rota: `POST /rotinas/recorrentes`
- Responsabilidade: Endpoint que cria recorrente e devolve a resposta HTTP correspondente.

### `excluir_recorrente(rec_id: int, db: Session=Depends(get_db), usuario: Usuario=Depends(get_usuario_atual))`

- Local: [excluir_recorrente](../app/routers/rotinas.py#L323)
- Rota: `POST /rotinas/recorrentes/{rec_id}/excluir`
- Responsabilidade: Endpoint que exclui recorrente e devolve a resposta HTTP correspondente.

### `toggle_recorrente(rec_id: int, db: Session=Depends(get_db), usuario: Usuario=Depends(get_usuario_atual))`

- Local: [toggle_recorrente](../app/routers/rotinas.py#L338)
- Rota: `POST /rotinas/recorrentes/{rec_id}/toggle`
- Responsabilidade: Endpoint que alterna o estado de recorrente e devolve a resposta HTTP correspondente.

## `app/security.py`

### `dispatch(self, request: Request, call_next) -> Response`

- Local: [SecurityHeadersMiddleware.dispatch](../app/security.py#L30)
- Responsabilidade: Valida a origem de mutações e aplica headers defensivos à resposta.

### `_origem_permitida(request: Request) -> bool`

- Local: [_origem_permitida](../app/security.py#L58)
- Responsabilidade: Compara Origin/Referer com a lista explícita de origens autorizadas.

### `_normalizar_origem(valor: str) -> str`

- Local: [_normalizar_origem](../app/security.py#L72)
- Responsabilidade: Reduz uma URL a esquema, hostname e porta para comparação segura.

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

- Local: [ler_arquivo_extrato](../app/services/conciliacao_service.py#L28)
- Responsabilidade: Le Excel ou CSV e normaliza colunas esperadas.

### `_extrair_coluna(df: pd.DataFrame, candidatas: list, padrao=None)`

- Local: [_extrair_coluna](../app/services/conciliacao_service.py#L38)
- Responsabilidade: Função auxiliar que extrai coluna.

### `_extrair_cpf_digitos_meio(cpf: str | None) -> str | None`

- Local: [_extrair_cpf_digitos_meio](../app/services/conciliacao_service.py#L45)
- Responsabilidade: Extrai os 6 dígitos do meio do CPF (posições 3–8 dos 11 dígitos).

### `_decimal_seguro(valor) -> Decimal`

- Local: [_decimal_seguro](../app/services/conciliacao_service.py#L55)
- Responsabilidade: Função auxiliar responsável pelo fluxo “decimal seguro”.

### `_norm_col(nome: str) -> str`

- Local: [_norm_col](../app/services/conciliacao_service.py#L59)
- Responsabilidade: Remove acentos, lowercase, substitui não-alfanuméricos por underscore.

### `_norm_texto(valor: str | None) -> str`

- Local: [_norm_texto](../app/services/conciliacao_service.py#L67)
- Responsabilidade: Função auxiliar responsável pelo fluxo “norm texto”.

### `_nome_bate(nome_atendimento: str | None, texto_extrato: str | None) -> bool`

- Local: [_nome_bate](../app/services/conciliacao_service.py#L76)
- Responsabilidade: Função auxiliar responsável pelo fluxo “nome bate”.

### `_procedimento_bate(atendimento: Atendimento, texto_extrato: str | None) -> bool`

- Local: [_procedimento_bate](../app/services/conciliacao_service.py#L84)
- Responsabilidade: Função auxiliar responsável pelo fluxo “procedimento bate”.

### `_contar_criterios(valor_ok: bool, data_ok: bool, nome_ok: bool, procedimento_ok: bool) -> int`

- Local: [_contar_criterios](../app/services/conciliacao_service.py#L98)
- Responsabilidade: Função auxiliar responsável pelo fluxo “contar criterios”.

### `limpar_divergencias_anteriores(db: Session, cliente_id: int, tipo: str)`

- Local: [limpar_divergencias_anteriores](../app/services/conciliacao_service.py#L102)
- Responsabilidade: Remove divergencias nao resolvidas antes de reprocessar o extrato.

### `limpar_movimentacoes_anteriores(db: Session, cliente_id: int, tipo: str)`

- Local: [limpar_movimentacoes_anteriores](../app/services/conciliacao_service.py#L112)
- Responsabilidade: Remove apenas movimentacoes importadas livres do mesmo tipo para o cliente.

### `_criar_movimentacao(db: Session, cliente_id: int, tipo: str, data_movimento, valor, origem_arquivo: str, digitos_cartao: str | None=None, descricao: str | None=None, sentido: str='recebimento')`

- Local: [_criar_movimentacao](../app/services/conciliacao_service.py#L129)
- Responsabilidade: Função auxiliar que cria movimentacao.

### `importar_lancamentos(db: Session, cliente_id: int, df: pd.DataFrame) -> int`

- Local: [importar_lancamentos](../app/services/conciliacao_service.py#L160)
- Responsabilidade: Importa lançamentos do Excel/CSV. Deleta os pendentes e recria.

### `_col(*names)`

- Local: [importar_lancamentos._col](../app/services/conciliacao_service.py#L165)
- Responsabilidade: Função auxiliar responsável pelo fluxo “col”.

### `_v(col, row=row)`

- Local: [importar_lancamentos._v](../app/services/conciliacao_service.py#L227)
- Responsabilidade: Função auxiliar responsável pelo fluxo “v”.

### `parse_ofx(caminho: str) -> pd.DataFrame`

- Local: [parse_ofx](../app/services/conciliacao_service.py#L312)
- Responsabilidade: Lê o OFX e preserva identificação da conta e saldo informado pelo banco.

### `_tag(t)`

- Local: [parse_ofx._tag](../app/services/conciliacao_service.py#L326)
- Responsabilidade: Função auxiliar responsável pelo fluxo “tag”.

### `_tag_global(tag)`

- Local: [parse_ofx._tag_global](../app/services/conciliacao_service.py#L350)
- Responsabilidade: Função auxiliar responsável pelo fluxo “tag global”.

### `score_sugestao(movimentacao: MovimentacaoBancaria, atendimento: Atendimento)`

- Local: [score_sugestao](../app/services/conciliacao_service.py#L378)
- Responsabilidade: Função auxiliar responsável pelo fluxo “score sugestao”.

### `buscar_sugestao(movimentacao: MovimentacaoBancaria, receitas: list)`

- Local: [buscar_sugestao](../app/services/conciliacao_service.py#L390)
- Responsabilidade: Retorna o melhor Atendimento candidato para a movimentacao, ou None.

### `conciliar_cartao(db: Session, cliente_id: int, df: pd.DataFrame, origem_arquivo: str) -> Tuple[List[dict], List[dict]]`

- Local: [conciliar_cartao](../app/services/conciliacao_service.py#L454)
- Responsabilidade: Função auxiliar que concilia cartao.

### `conciliar_pix_ted(db: Session, cliente_id: int, df: pd.DataFrame, origem_arquivo: str) -> Tuple[List[dict], List[dict]]`

- Local: [conciliar_pix_ted](../app/services/conciliacao_service.py#L576)
- Responsabilidade: Função auxiliar que concilia pix ted.

### `limpar_movimentacoes_banco_livres(db: Session, cliente_id: int)`

- Local: [limpar_movimentacoes_banco_livres](../app/services/conciliacao_service.py#L654)
- Responsabilidade: Remove apenas movimentacoes bancarias ainda sem vinculo de conciliacao.

### `importar_movimentacoes_bancarias(db: Session, cliente_id: int, df: pd.DataFrame, origem_arquivo: str, conta_bancaria_id: int | None=None) -> dict`

- Local: [importar_movimentacoes_bancarias](../app/services/conciliacao_service.py#L671)
- Responsabilidade: Importa o extrato da conta corrente como movimentacoes bancarias livres. Creditos ficam disponiveis para Pix/TED ou para vincular com lotes de cartao. Debitos ficam disponiveis para contas a pagar.

### `gerar_transferencias_cartao(db: Session, cliente_id: int) -> int`

- Local: [gerar_transferencias_cartao](../app/services/conciliacao_service.py#L751)
- Responsabilidade: Agrupa Atendimentos conciliados por cartão em TransferenciaCartao por (data_credito, bandeira_cartao). Cria ou atualiza os registros. Retorna o número de novos lotes criados.

### `buscar_sugestao_venda(venda: 'VendaCartao', atendimentos: list) -> dict | None`

- Local: [buscar_sugestao_venda](../app/services/conciliacao_service.py#L815)
- Responsabilidade: Retorna o melhor Atendimento para uma VendaCartao, ou None.

### `importar_vendas_cartao(db: Session, cliente_id: int, df: pd.DataFrame, origem_arquivo: str) -> int`

- Local: [importar_vendas_cartao](../app/services/conciliacao_service.py#L873)
- Responsabilidade: Importa extrato da maquininha como VendaCartao individuais. Colunas esperadas: data_venda, data_pagamento, bandeira, ultimos_digitos, nome_portador, valor_bruto, taxa_percentual, valor_liquido, parcelas.

### `_col(*names)`

- Local: [importar_vendas_cartao._col](../app/services/conciliacao_service.py#L887)
- Responsabilidade: Função auxiliar responsável pelo fluxo “col”.

### `_v(col)`

- Local: [importar_vendas_cartao._v](../app/services/conciliacao_service.py#L928)
- Responsabilidade: Função auxiliar responsável pelo fluxo “v”.

### `fechar_lote_dia(db: Session, cliente_id: int, data_pagamento, bandeira: str | None) -> TransferenciaCartao`

- Local: [fechar_lote_dia](../app/services/conciliacao_service.py#L988)
- Responsabilidade: Agrupa as VendaCartao pendentes de um dia/bandeira em um TransferenciaCartao (lote). Retorna o lote criado ou atualizado.

### `importar_extrato_conta_corrente(db: Session, cliente_id: int, df: pd.DataFrame, origem_arquivo: str) -> dict`

- Local: [importar_extrato_conta_corrente](../app/services/conciliacao_service.py#L1051)
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

- Local: [registrar](../app/services/log_service.py#L6)
- Responsabilidade: Função auxiliar que registra .

## `app/utils.py`

### `cliente_ativo(request: Request, cliente_id: Optional[int]) -> Optional[int]`

- Local: [cliente_ativo](../app/utils.py#L23)
- Responsabilidade: Retorna cliente_id do param URL; se None, lê do cookie 'cliente_ativo'.

### `salvar_upload_temporario(arquivo: UploadFile, extensoes_permitidas: set[str], max_bytes: int=MAX_UPLOAD_BYTES) -> tuple[str, str, str]`

- Local: [salvar_upload_temporario](../app/utils.py#L34)
- Responsabilidade: Valida extensao/tamanho e salva o upload em arquivo temporario.

### `_validar_assinatura(ext: str, inicio: bytes) -> None`

- Local: [_validar_assinatura](../app/utils.py#L87)
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

Cifra/decifra backups locais com a chave de campos da aplicacao.

### `encrypt(source: Path, target: Path) -> None`

- Local: [encrypt](../scripts/backup_crypto.py#L18)
- Responsabilidade: Função auxiliar que cifra .

### `decrypt(source: Path, target: Path) -> None`

- Local: [decrypt](../scripts/backup_crypto.py#L24)
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

## `seed.py`

Script de seed com dados de exemplo. Execute da raiz do projeto: docker-compose exec web python seed.py Ou fora do Docker (com banco acessivel): python seed.py

### `limpar()`

- Local: [limpar](../seed.py#L49)
- Responsabilidade: Remove dados existentes para recomeçar do zero.

### `criar_usuarios()`

- Local: [criar_usuarios](../seed.py#L67)
- Responsabilidade: Função auxiliar que cria usuarios.

### `criar_clientes(usuarios)`

- Local: [criar_clientes](../seed.py#L104)
- Responsabilidade: Função auxiliar que cria clientes.

### `criar_rotinas_hoje(clientes)`

- Local: [criar_rotinas_hoje](../seed.py#L190)
- Responsabilidade: Função auxiliar que cria rotinas hoje.

### `criar_contas_pagar_exemplo(clientes)`

- Local: [criar_contas_pagar_exemplo](../seed.py#L221)
- Responsabilidade: Função auxiliar que cria contas pagar exemplo.

### `criar_cadastros_financeiros_exemplo(clientes)`

- Local: [criar_cadastros_financeiros_exemplo](../seed.py#L296)
- Responsabilidade: Função auxiliar que cria cadastros financeiros exemplo.

### `criar_fechamentos_exemplo(clientes, usuarios)`

- Local: [criar_fechamentos_exemplo](../seed.py#L368)
- Responsabilidade: Função auxiliar que cria fechamentos exemplo.

### `criar_conciliacao_exemplo(clientes, usuarios)`

- Local: [criar_conciliacao_exemplo](../seed.py#L394)
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

- Local: [liquido](../seed_conciliacao_cartao.py#L57)
- Responsabilidade: Função auxiliar responsável pelo fluxo “liquido”.

### `add_venda(cliente_id, data_venda, data_pagamento, portador, digitos, bandeira, bruto, status=StatusVendaCartao.pendente, lote_id=None, origem='seed_teste.csv')`

- Local: [add_venda](../seed_conciliacao_cartao.py#L61)
- Responsabilidade: Função auxiliar responsável pelo fluxo “add venda”.

### `add_lote(cliente_id, data, bandeira, vendas)`

- Local: [add_lote](../seed_conciliacao_cartao.py#L84)
- Responsabilidade: Função auxiliar responsável pelo fluxo “add lote”.

### `add_credito_banco(cliente_id, data, valor, descricao, lote_id=None)`

- Local: [add_credito_banco](../seed_conciliacao_cartao.py#L104)
- Responsabilidade: Função auxiliar responsável pelo fluxo “add credito banco”.

## `seed_exemplos_conciliacao.py`

Seed: exemplos completos para testar a Conciliação de Cartão. Cria Atendimentos (lançamentos) com forma_pagamento=cartao_credito que correspondem às VendaCartao pendentes já existentes. Cenários cobertos por cliente: PRESTI (id=1) — 6 vendas pendentes: • 4 sugestao_pronta (verde) — valor exato + dígitos + data próxima • 1 revisar (amarelo) — diferença de R$2,00 no valor • 1 sem sugestão — para testar busca manual / criar lançamento REF DOR (id=2) — 3 vendas pendentes: • 2 sugestao_pronta (verde) • 1 revisar (amarelo) — diferença de R$2,00 Execute: docker exec bpo-financeiro-web-1 python seed_exemplos_conciliacao.py

### `liquido(bruto: Decimal, taxa_pct: Decimal) -> Decimal`

- Local: [liquido](../seed_exemplos_conciliacao.py#L47)
- Responsabilidade: Função auxiliar responsável pelo fluxo “liquido”.

### `add_at(cliente_id, data_atend, nome, bandeira, digitos, valor, data_prev, taxa=None, obs=None)`

- Local: [add_at](../seed_exemplos_conciliacao.py#L54)
- Responsabilidade: Função auxiliar responsável pelo fluxo “add at”.

---

Total documentado: **345 funções e métodos**.
