from typing import List, Optional

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from app.jinja import templates
from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from app.auth import get_usuario_atual, hash_senha, requer_coordenador, tem_acesso_geral
from app.database import get_db
from app.models import (
    AnotacaoCliente, Atendimento, CentroCusto, ClienteBPO, ContaPagar, FechamentoDiario,
    GrupoEmpresarial, LogAuditoria, MaquininhaCliente, PagamentoParcialContaPagar,
    TarefaRotina, Usuario, PerfilUsuario, TaxaCartaoCliente,
    TaxaAntecipacaoCliente,
)
from app.services.log_service import registrar as _log

router = APIRouter(prefix="/admin")

PERFIS_USUARIO = {perfil.value for perfil in PerfilUsuario}
CATEGORIAS_ANOTACAO = {
    "procedimento": "Procedimento",
    "financeiro": "Financeiro",
    "documentacao": "Documentação",
    "preferencia": "Preferência do cliente",
    "alerta": "Alerta importante",
    "geral": "Observação geral",
}


def clientes_do_usuario(db: Session, usuario: Usuario):
    if tem_acesso_geral(usuario):
        return db.query(ClienteBPO).filter(ClienteBPO.ativo == True).order_by(ClienteBPO.nome).all()
    return db.query(ClienteBPO).outerjoin(
        GrupoEmpresarial, ClienteBPO.grupo_empresarial_id == GrupoEmpresarial.id
    ).filter(
        ClienteBPO.ativo == True,
        or_(
            ClienteBPO.funcionario_id == usuario.id,
            and_(ClienteBPO.funcionario_id.is_(None), GrupoEmpresarial.funcionario_id == usuario.id),
        ),
    ).order_by(ClienteBPO.nome).all()


def pode_acessar_cliente(db: Session, usuario: Usuario, cliente_id: int) -> bool:
    if tem_acesso_geral(usuario):
        return True
    return db.query(ClienteBPO.id).outerjoin(
        GrupoEmpresarial, ClienteBPO.grupo_empresarial_id == GrupoEmpresarial.id
    ).filter(
        ClienteBPO.id == cliente_id,
        ClienteBPO.ativo == True,
        or_(
            ClienteBPO.funcionario_id == usuario.id,
            and_(ClienteBPO.funcionario_id.is_(None), GrupoEmpresarial.funcionario_id == usuario.id),
        ),
    ).first() is not None


def _url_retorno_maquininha(
    cliente_id: int,
    origem: str | None,
    maquininha_id: int | None = None,
) -> str:
    """Monta apenas destinos internos conhecidos após gerenciar uma maquininha."""
    if origem == "taxas":
        url = f"/admin/taxas-cartao?cliente_id={cliente_id}"
        if maquininha_id:
            url += f"&maquininha_id={maquininha_id}"
        return url
    if origem == "editar":
        return f"/admin/clientes/cliente/{cliente_id}/editar?sucesso=1"
    return "/admin/clientes"


def _float_opcional(valor: str | None) -> Optional[float]:
    if valor is None or str(valor).strip() == "":
        return None
    return float(str(valor).replace(",", "."))


@router.get("/equipe", response_class=HTMLResponse)
async def pagina_equipe(
    usuario: Usuario = Depends(get_usuario_atual),
):
    return RedirectResponse(url="/admin/clientes", status_code=303)


@router.get("/clientes", response_class=HTMLResponse)
async def pagina_clientes(
    request: Request,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_usuario_atual),
):
    clientes = clientes_do_usuario(db, usuario)
    funcionarios = db.query(Usuario).filter(
        Usuario.perfil == PerfilUsuario.funcionario,
        Usuario.ativo == True,
    ).order_by(Usuario.nome).all()
    grupos = db.query(GrupoEmpresarial).filter(
        GrupoEmpresarial.ativo == True,
    ).order_by(GrupoEmpresarial.nome).all()

    return templates.TemplateResponse("admin/clientes.html", {
        "request": request,
        "usuario": usuario,
        "clientes": clientes,
        "funcionarios": funcionarios,
        "grupos": grupos,
        "bandeiras": BANDEIRAS,
        "redes_maquininha": REDES_MAQUININHA,
        "pode_coordenar": usuario.perfil == PerfilUsuario.coordenador,
        "pode_criar_cliente": tem_acesso_geral(usuario),
    })


@router.get("/grupos", response_class=HTMLResponse)
async def pagina_grupos(
    request: Request,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_usuario_atual),
):
    if not tem_acesso_geral(usuario):
        return RedirectResponse(url="/admin/clientes", status_code=303)

    grupos = db.query(GrupoEmpresarial).filter(
        GrupoEmpresarial.ativo == True,
    ).order_by(GrupoEmpresarial.nome).all()
    funcionarios = db.query(Usuario).filter(
        Usuario.perfil == PerfilUsuario.funcionario,
        Usuario.ativo == True,
    ).order_by(Usuario.nome).all()

    return templates.TemplateResponse("admin/grupos.html", {
        "request": request,
        "usuario": usuario,
        "grupos": grupos,
        "funcionarios": funcionarios,
        "pode_coordenar": usuario.perfil == PerfilUsuario.coordenador,
    })


@router.post("/grupos")
async def criar_grupo(
    nome: str = Form(...),
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_usuario_atual),
):
    if not tem_acesso_geral(usuario):
        return RedirectResponse(url="/admin/clientes", status_code=303)

    nome = nome.strip()
    if not nome:
        return RedirectResponse(url="/admin/grupos?erro=nome_obrigatorio", status_code=303)

    grupo = GrupoEmpresarial(nome=nome, ativo=True)
    db.add(grupo)
    db.commit()
    _log(db, "Grupo empresarial criado", "admin", usuario_id=usuario.id, usuario_nome=usuario.nome, detalhes=nome)
    return RedirectResponse(url="/admin/grupos?sucesso=1", status_code=303)


@router.post("/grupos/{grupo_id}/renomear")
async def renomear_grupo(
    grupo_id: int,
    nome: str = Form(...),
    funcionario_id: Optional[int] = Form(None),
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_usuario_atual),
):
    if not tem_acesso_geral(usuario):
        return RedirectResponse(url="/admin/clientes", status_code=303)

    grupo = db.query(GrupoEmpresarial).filter(GrupoEmpresarial.id == grupo_id).first()
    nome = nome.strip()
    if grupo and nome:
        grupo.nome = nome
        if usuario.perfil == PerfilUsuario.coordenador:
            responsavel = None
            if funcionario_id:
                responsavel = db.query(Usuario).filter(
                    Usuario.id == funcionario_id,
                    Usuario.ativo == True,
                ).first()
            grupo.funcionario_id = responsavel.id if responsavel else None
        db.commit()
        _log(db, "Grupo empresarial renomeado", "admin", usuario_id=usuario.id, usuario_nome=usuario.nome, detalhes=nome)
    return RedirectResponse(url="/admin/grupos?sucesso=1", status_code=303)


@router.post("/grupos/{grupo_id}/excluir")
async def excluir_grupo(
    grupo_id: int,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_usuario_atual),
):
    if not tem_acesso_geral(usuario):
        return RedirectResponse(url="/admin/clientes", status_code=303)

    grupo = db.query(GrupoEmpresarial).filter(GrupoEmpresarial.id == grupo_id).first()
    if grupo:
        nome = grupo.nome
        db.delete(grupo)
        db.commit()
        _log(db, "Grupo empresarial excluído", "admin", usuario_id=usuario.id, usuario_nome=usuario.nome, detalhes=nome)
    return RedirectResponse(url="/admin/grupos?sucesso=1", status_code=303)


@router.get("/funcionarios", response_class=HTMLResponse)
async def pagina_funcionarios(
    request: Request,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(requer_coordenador),
):
    usuarios = db.query(Usuario).order_by(Usuario.nome).all()

    return templates.TemplateResponse("admin/funcionarios.html", {
        "request": request,
        "usuario": usuario,
        "usuarios": usuarios,
    })


@router.get("/anotacoes-clientes", response_class=HTMLResponse)
async def pagina_anotacoes_clientes(
    request: Request,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_usuario_atual),
):
    clientes = clientes_do_usuario(db, usuario)
    return templates.TemplateResponse("admin/anotacoes_clientes.html", {
        "request": request,
        "usuario": usuario,
        "clientes": clientes,
    })


@router.get("/anotacoes-clientes/{cliente_id}", response_class=HTMLResponse)
async def pagina_anotacoes_cliente(
    cliente_id: int,
    request: Request,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_usuario_atual),
):
    if not pode_acessar_cliente(db, usuario, cliente_id):
        return RedirectResponse(url="/admin/anotacoes-clientes?erro=sem_acesso", status_code=303)
    cliente = db.query(ClienteBPO).filter(ClienteBPO.id == cliente_id).first()
    if not cliente:
        return RedirectResponse(url="/admin/anotacoes-clientes?erro=cliente_nao_encontrado", status_code=303)
    anotacoes = db.query(AnotacaoCliente).filter(
        AnotacaoCliente.cliente_id == cliente_id
    ).order_by(AnotacaoCliente.criado_em.desc(), AnotacaoCliente.id.desc()).all()
    return templates.TemplateResponse("admin/anotacoes_cliente_detalhe.html", {
        "request": request,
        "usuario": usuario,
        "cliente": cliente,
        "anotacoes": anotacoes,
        "categorias": CATEGORIAS_ANOTACAO,
    })


@router.post("/anotacoes-clientes/{cliente_id}/nova")
async def criar_anotacao_cliente(
    cliente_id: int,
    categoria: str = Form("procedimento"),
    titulo: str = Form(...),
    conteudo: str = Form(...),
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_usuario_atual),
):
    if not pode_acessar_cliente(db, usuario, cliente_id):
        return RedirectResponse(url="/admin/anotacoes-clientes?erro=sem_acesso", status_code=303)
    titulo, conteudo = titulo.strip(), conteudo.strip()
    if not titulo or not conteudo:
        return RedirectResponse(url=f"/admin/anotacoes-clientes/{cliente_id}?erro=campos_obrigatorios", status_code=303)
    if categoria not in CATEGORIAS_ANOTACAO:
        categoria = "geral"
    db.add(AnotacaoCliente(
        cliente_id=cliente_id,
        autor_id=usuario.id,
        categoria=categoria,
        titulo=titulo,
        conteudo=conteudo,
    ))
    db.commit()
    _log(db, "Anotação de cliente criada", "admin", usuario_id=usuario.id,
         usuario_nome=usuario.nome, cliente_id=cliente_id, detalhes=titulo)
    return RedirectResponse(url=f"/admin/anotacoes-clientes/{cliente_id}?sucesso=criada", status_code=303)


@router.post("/anotacoes-clientes/anotacao/{anotacao_id}/editar")
async def editar_anotacao_cliente(
    anotacao_id: int,
    categoria: str = Form("procedimento"),
    titulo: str = Form(...),
    conteudo: str = Form(...),
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_usuario_atual),
):
    anotacao = db.query(AnotacaoCliente).filter(AnotacaoCliente.id == anotacao_id).first()
    if not anotacao or not pode_acessar_cliente(db, usuario, anotacao.cliente_id):
        return RedirectResponse(url="/admin/anotacoes-clientes?erro=sem_acesso", status_code=303)
    titulo, conteudo = titulo.strip(), conteudo.strip()
    if not titulo or not conteudo:
        return RedirectResponse(url=f"/admin/anotacoes-clientes/{anotacao.cliente_id}?erro=campos_obrigatorios", status_code=303)
    anotacao.categoria = categoria if categoria in CATEGORIAS_ANOTACAO else "geral"
    anotacao.titulo = titulo
    anotacao.conteudo = conteudo
    db.commit()
    return RedirectResponse(url=f"/admin/anotacoes-clientes/{anotacao.cliente_id}?sucesso=editada", status_code=303)


@router.post("/anotacoes-clientes/anotacao/{anotacao_id}/excluir")
async def excluir_anotacao_cliente(
    anotacao_id: int,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_usuario_atual),
):
    anotacao = db.query(AnotacaoCliente).filter(AnotacaoCliente.id == anotacao_id).first()
    if not anotacao or not pode_acessar_cliente(db, usuario, anotacao.cliente_id):
        return RedirectResponse(url="/admin/anotacoes-clientes?erro=sem_acesso", status_code=303)
    cliente_id = anotacao.cliente_id
    if anotacao.autor_id != usuario.id and usuario.perfil != PerfilUsuario.coordenador:
        return RedirectResponse(url=f"/admin/anotacoes-clientes/{cliente_id}?erro=exclusao_restrita", status_code=303)
    db.delete(anotacao)
    db.commit()
    return RedirectResponse(url=f"/admin/anotacoes-clientes/{cliente_id}?sucesso=excluida", status_code=303)


@router.post("/equipe/usuario")
@router.post("/funcionarios/usuario")
async def criar_usuario(
    nome: str = Form(...),
    email: str = Form(...),
    senha: str = Form(...),
    perfil: str = Form("funcionario"),
    db: Session = Depends(get_db),
    _: Usuario = Depends(requer_coordenador),
):
    nome = nome.strip()
    email = email.strip().lower()
    if perfil not in PERFIS_USUARIO:
        return RedirectResponse(url="/admin/funcionarios?erro=perfil_invalido", status_code=303)

    existente = db.query(Usuario).filter(Usuario.email == email).first()
    if existente:
        return RedirectResponse(url="/admin/funcionarios?erro=email_duplicado", status_code=303)

    novo = Usuario(
        nome=nome,
        email=email,
        senha_hash=hash_senha(senha),
        perfil=perfil,
        ativo=True,
    )
    db.add(novo)
    db.commit()
    _log(db, "Usuário criado", "admin", usuario_nome=novo.nome, detalhes=f"{novo.email} — perfil: {perfil}")
    return RedirectResponse(url="/admin/funcionarios", status_code=303)


@router.post("/funcionarios/usuario/{usuario_id}/editar")
async def editar_usuario(
    usuario_id: int,
    nome: str = Form(...),
    email: str = Form(...),
    perfil: str = Form(...),
    senha: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    coordenador: Usuario = Depends(requer_coordenador),
):
    alvo = db.query(Usuario).filter(Usuario.id == usuario_id).first()
    if not alvo:
        return RedirectResponse(url="/admin/funcionarios?erro=usuario_nao_encontrado", status_code=303)

    nome = nome.strip()
    email = email.strip().lower()
    senha = (senha or "").strip()
    if not nome or not email or perfil not in PERFIS_USUARIO:
        return RedirectResponse(url="/admin/funcionarios?erro=dados_invalidos", status_code=303)
    if senha and len(senha) < 6:
        return RedirectResponse(url=f"/admin/funcionarios?erro=senha_curta&editar={usuario_id}", status_code=303)
    if usuario_id == coordenador.id and perfil != PerfilUsuario.coordenador.value:
        return RedirectResponse(url="/admin/funcionarios?erro=perfil_proprio", status_code=303)

    duplicado = db.query(Usuario).filter(
        Usuario.email == email,
        Usuario.id != usuario_id,
    ).first()
    if duplicado:
        return RedirectResponse(url=f"/admin/funcionarios?erro=email_duplicado&editar={usuario_id}", status_code=303)

    alvo.nome = nome
    alvo.email = email
    alvo.perfil = perfil
    if senha:
        alvo.senha_hash = hash_senha(senha)
    db.commit()
    _log(db, "Usuário editado", "admin", usuario_id=coordenador.id,
         usuario_nome=coordenador.nome,
         detalhes=f"{alvo.nome} — {alvo.email} — perfil: {perfil}")
    return RedirectResponse(url="/admin/funcionarios?sucesso=editado", status_code=303)


@router.post("/funcionarios/usuario/{usuario_id}/excluir")
async def excluir_usuario(
    usuario_id: int,
    db: Session = Depends(get_db),
    coordenador: Usuario = Depends(requer_coordenador),
):
    if usuario_id == coordenador.id:
        return RedirectResponse(url="/admin/funcionarios?erro=excluir_proprio", status_code=303)

    alvo = db.query(Usuario).filter(Usuario.id == usuario_id).first()
    if not alvo:
        return RedirectResponse(url="/admin/funcionarios?erro=usuario_nao_encontrado", status_code=303)

    nome_alvo, email_alvo = alvo.nome, alvo.email
    # Preserva o histórico financeiro, removendo somente o vínculo com a conta.
    db.query(ClienteBPO).filter(ClienteBPO.funcionario_id == usuario_id).update(
        {ClienteBPO.funcionario_id: None}, synchronize_session=False)
    db.query(Atendimento).filter(Atendimento.lancado_por_id == usuario_id).update(
        {Atendimento.lancado_por_id: None}, synchronize_session=False)
    db.query(ContaPagar).filter(ContaPagar.lancado_por_id == usuario_id).update(
        {ContaPagar.lancado_por_id: None}, synchronize_session=False)
    db.query(PagamentoParcialContaPagar).filter(
        PagamentoParcialContaPagar.criado_por_id == usuario_id
    ).update({PagamentoParcialContaPagar.criado_por_id: None}, synchronize_session=False)
    db.query(FechamentoDiario).filter(FechamentoDiario.gerado_por_id == usuario_id).update(
        {FechamentoDiario.gerado_por_id: None}, synchronize_session=False)
    db.query(LogAuditoria).filter(LogAuditoria.usuario_id == usuario_id).update(
        {LogAuditoria.usuario_id: None}, synchronize_session=False)
    db.query(AnotacaoCliente).filter(AnotacaoCliente.autor_id == usuario_id).update(
        {AnotacaoCliente.autor_id: None}, synchronize_session=False)
    db.query(TarefaRotina).filter(TarefaRotina.funcionario_id == usuario_id).delete(
        synchronize_session=False)
    db.delete(alvo)
    db.commit()
    _log(db, "Usuário excluído", "admin", usuario_id=coordenador.id,
         usuario_nome=coordenador.nome, detalhes=f"{nome_alvo} — {email_alvo}")
    return RedirectResponse(url="/admin/funcionarios?sucesso=excluido", status_code=303)


@router.post("/equipe/usuario/{usuario_id}/toggle")
@router.post("/funcionarios/usuario/{usuario_id}/toggle")
async def toggle_usuario(
    usuario_id: int,
    db: Session = Depends(get_db),
    coordenador: Usuario = Depends(requer_coordenador),
):
    # Não permite desativar a si mesmo
    if usuario_id == coordenador.id:
        return RedirectResponse(url="/admin/funcionarios", status_code=303)

    alvo = db.query(Usuario).filter(Usuario.id == usuario_id).first()
    if alvo:
        alvo.ativo = not alvo.ativo
        db.commit()
        acao = "Usuário ativado" if alvo.ativo else "Usuário desativado"
        _log(db, acao, "admin", usuario_id=coordenador.id, usuario_nome=coordenador.nome, detalhes=alvo.nome)
    return RedirectResponse(url="/admin/funcionarios", status_code=303)


@router.post("/equipe/cliente")
@router.post("/clientes/cliente")
async def criar_cliente(
    nome: str = Form(...),
    razao_social: Optional[str] = Form(None),
    cnpj: Optional[str] = Form(None),
    especialidade: Optional[str] = Form(None),
    tem_maquininha: str = Form("nao"),
    rede_maquininha: Optional[str] = Form(None),
    antecipa: str = Form("nao"),
    bandeira: List[str] = Form(default=[]),
    taxa_percentual: List[str] = Form(default=[]),
    funcionario_id: Optional[int] = Form(None),
    grupo_empresarial_id: Optional[int] = Form(None),
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_usuario_atual),
):
    if not tem_acesso_geral(usuario):
        return RedirectResponse(url="/admin/clientes", status_code=303)

    usa_maquininha = tem_maquininha == "sim"
    cliente = ClienteBPO(
        nome=nome,
        razao_social=razao_social or None,
        cnpj=cnpj or None,
        especialidade=especialidade or None,
        tem_maquininha=usa_maquininha,
        rede_maquininha=rede_maquininha if usa_maquininha and rede_maquininha else None,
        antecipa=antecipa == "sim" if usa_maquininha else False,
        funcionario_id=funcionario_id if usuario.perfil == PerfilUsuario.coordenador and funcionario_id else None,
        grupo_empresarial_id=grupo_empresarial_id or None,
        ativo=True,
    )
    db.add(cliente)
    db.flush()

    if usa_maquininha:
        for i, band in enumerate(bandeira):
            taxa = _float_opcional(taxa_percentual[i] if i < len(taxa_percentual) else None)
            if band and taxa is not None:
                db.add(TaxaCartaoCliente(
                    cliente_id=cliente.id,
                    bandeira=band,
                    taxa_percentual=taxa,
                ))

    db.commit()
    _log(db, "Cliente criado", "admin", usuario_id=usuario.id, usuario_nome=usuario.nome, cliente_id=cliente.id, cliente_nome=nome)
    return RedirectResponse(url="/admin/clientes", status_code=303)


@router.post("/equipe/cliente/{cliente_id}/atribuir")
@router.post("/clientes/cliente/{cliente_id}/atribuir")
async def atribuir_cliente(
    cliente_id: int,
    funcionario_id: Optional[int] = Form(None),
    db: Session = Depends(get_db),
    _: Usuario = Depends(requer_coordenador),
):
    cliente = db.query(ClienteBPO).filter(ClienteBPO.id == cliente_id).first()
    if cliente:
        cliente.funcionario_id = funcionario_id if funcionario_id else None
        db.commit()
    return RedirectResponse(url="/admin/clientes", status_code=303)


@router.post("/clientes/cliente/{cliente_id}/atualizar")
async def atualizar_cliente(
    cliente_id: int,
    razao_social: Optional[str] = Form(None),
    cnpj: Optional[str] = Form(None),
    especialidade: Optional[str] = Form(None),
    tem_maquininha: str = Form("nao"),
    rede_maquininha: Optional[str] = Form(None),
    antecipa: str = Form("nao"),
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_usuario_atual),
):
    if not pode_acessar_cliente(db, usuario, cliente_id):
        return RedirectResponse(url="/admin/clientes", status_code=303)

    cliente = db.query(ClienteBPO).filter(ClienteBPO.id == cliente_id).first()
    if cliente:
        cliente.razao_social = razao_social or None
        cliente.cnpj = cnpj or None
        cliente.especialidade = especialidade or None
        db.commit()

    return RedirectResponse(url="/admin/clientes", status_code=303)


@router.get("/clientes/cliente/{cliente_id}/editar", response_class=HTMLResponse)
async def pagina_editar_cliente(
    cliente_id: int,
    request: Request,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_usuario_atual),
):
    if not pode_acessar_cliente(db, usuario, cliente_id):
        return RedirectResponse(url="/admin/clientes?erro=sem_acesso", status_code=303)

    cliente = db.query(ClienteBPO).filter(ClienteBPO.id == cliente_id).first()
    if not cliente:
        return RedirectResponse(url="/admin/clientes?erro=cliente_nao_encontrado", status_code=303)

    funcionarios = db.query(Usuario).filter(
        Usuario.perfil == PerfilUsuario.funcionario,
        Usuario.ativo == True,
    ).order_by(Usuario.nome).all()
    grupos = db.query(GrupoEmpresarial).filter(
        GrupoEmpresarial.ativo == True,
    ).order_by(GrupoEmpresarial.nome).all()
    return templates.TemplateResponse("admin/cliente_editar.html", {
        "request": request,
        "usuario": usuario,
        "cliente": cliente,
        "funcionarios": funcionarios,
        "grupos": grupos,
        "redes_maquininha": REDES_MAQUININHA,
        "pode_coordenar": usuario.perfil == PerfilUsuario.coordenador,
    })


@router.post("/clientes/cliente/{cliente_id}/editar")
async def editar_cliente_completo(
    cliente_id: int,
    nome: str = Form(...),
    razao_social: Optional[str] = Form(None),
    cnpj: Optional[str] = Form(None),
    especialidade: Optional[str] = Form(None),
    regime_tributario: Optional[str] = Form(None),
    banco: Optional[str] = Form(None),
    agencia: Optional[str] = Form(None),
    conta: Optional[str] = Form(None),
    tem_maquininha: str = Form("nao"),
    rede_maquininha: Optional[str] = Form(None),
    antecipa: str = Form("nao"),
    funcionario_id: Optional[int] = Form(None),
    grupo_empresarial_id: Optional[int] = Form(None),
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_usuario_atual),
):
    if not pode_acessar_cliente(db, usuario, cliente_id):
        return RedirectResponse(url="/admin/clientes?erro=sem_acesso", status_code=303)

    cliente = db.query(ClienteBPO).filter(ClienteBPO.id == cliente_id).first()
    if not cliente:
        return RedirectResponse(url="/admin/clientes?erro=cliente_nao_encontrado", status_code=303)

    nome = nome.strip()
    if not nome:
        return RedirectResponse(
            url=f"/admin/clientes/cliente/{cliente_id}/editar?erro=nome_obrigatorio",
            status_code=303,
        )

    cliente.nome = nome
    cliente.razao_social = (razao_social or "").strip() or None
    cliente.cnpj = (cnpj or "").strip() or None
    cliente.especialidade = (especialidade or "").strip() or None
    cliente.regime_tributario = (regime_tributario or "").strip() or None
    cliente.banco = (banco or "").strip() or None
    cliente.agencia = (agencia or "").strip() or None
    cliente.conta = (conta or "").strip() or None
    cliente.tem_maquininha = tem_maquininha == "sim"
    cliente.rede_maquininha = ((rede_maquininha or "").strip() or None) if cliente.tem_maquininha else None
    cliente.antecipa = antecipa == "sim" if cliente.tem_maquininha else False
    if usuario.perfil == PerfilUsuario.coordenador:
        responsavel = None
        if funcionario_id:
            responsavel = db.query(Usuario).filter(
                Usuario.id == funcionario_id,
                Usuario.ativo == True,
            ).first()
        cliente.funcionario_id = responsavel.id if responsavel else None
    if tem_acesso_geral(usuario):
        grupo = None
        if grupo_empresarial_id:
            grupo = db.query(GrupoEmpresarial).filter(
                GrupoEmpresarial.id == grupo_empresarial_id,
                GrupoEmpresarial.ativo == True,
            ).first()
        cliente.grupo_empresarial_id = grupo.id if grupo else None

    db.commit()
    _log(db, "Cliente editado", "admin", usuario_id=usuario.id,
         usuario_nome=usuario.nome, cliente_id=cliente.id,
         cliente_nome=cliente.nome, detalhes="Cadastro completo atualizado")
    return RedirectResponse(
        url=f"/admin/clientes/cliente/{cliente_id}/editar?sucesso=1",
        status_code=303,
    )


@router.post("/clientes/cliente/{cliente_id}/excluir")
async def excluir_cliente(
    cliente_id: int,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(requer_coordenador),
):
    cliente = db.query(ClienteBPO).filter(ClienteBPO.id == cliente_id).first()
    if not cliente:
        return RedirectResponse(url="/admin/clientes?erro=cliente_nao_encontrado", status_code=303)

    # Exclusão lógica: retira o cliente da operação sem apagar histórico financeiro.
    cliente.ativo = False
    cliente.funcionario_id = None
    db.commit()
    _log(db, "Cliente excluído", "admin", usuario_id=usuario.id,
         usuario_nome=usuario.nome, cliente_id=cliente.id,
         cliente_nome=cliente.nome, detalhes="Cliente inativado; histórico preservado")
    return RedirectResponse(url="/admin/clientes?sucesso=cliente_excluido", status_code=303)


# ---------------------------------------------------------------------------
# Taxas de cartão por cliente
# ---------------------------------------------------------------------------

BANDEIRAS = ["Visa", "Mastercard", "Elo", "Amex", "Hipercard", "Cabal", "Outras"]
REDES_MAQUININHA = ["Ton", "InfinityPay", "Stone", "Cielo", "Rede", "GetNet", "PagSeguro", "Mercado Pago", "SumUp", "Outro"]

FAIXAS_PARCELAMENTO = [
    ("avista_credito",  "À vista — Crédito"),
    ("avista_debito",   "À vista — Débito"),
    ("parcelado_2_6",   "Parcelado 2x a 6x"),
    ("parcelado_6_12",  "Parcelado 6x a 12x"),
    ("personalizada",   "Faixa personalizada"),
]
FAIXAS_PARCELAMENTO_VALIDAS = {valor for valor, _ in FAIXAS_PARCELAMENTO}


@router.get("/taxas-cartao", response_class=HTMLResponse)
async def pagina_taxas_cartao(
    request: Request,
    cliente_id: Optional[int] = None,
    maquininha_id: Optional[int] = None,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_usuario_atual),
):
    clientes = clientes_do_usuario(db, usuario)
    ids_permitidos = [c.id for c in clientes]
    taxas = []
    maquininhas = []
    cliente_selecionado = None
    maquininha_selecionada = None

    taxas_antecipacao = []
    if cliente_id and cliente_id in ids_permitidos:
        cliente_selecionado = db.query(ClienteBPO).filter(ClienteBPO.id == cliente_id).first()
        maquininhas = (
            db.query(MaquininhaCliente)
            .filter(MaquininhaCliente.cliente_id == cliente_id, MaquininhaCliente.ativa == True)
            .order_by(MaquininhaCliente.id)
            .all()
        )
        q = db.query(TaxaCartaoCliente).filter(TaxaCartaoCliente.cliente_id == cliente_id)
        if maquininha_id:
            maquininha_selecionada = db.query(MaquininhaCliente).filter(
                MaquininhaCliente.id == maquininha_id,
                MaquininhaCliente.cliente_id == cliente_id,
                MaquininhaCliente.ativa == True,
            ).first()
            if maquininha_selecionada:
                q = q.filter(TaxaCartaoCliente.maquininha_id == maquininha_id)
        taxas = q.order_by(TaxaCartaoCliente.bandeira, TaxaCartaoCliente.faixa_parcelamento).all()

        if cliente_selecionado and cliente_selecionado.antecipa:
            taxas_antecipacao = (
                db.query(TaxaAntecipacaoCliente)
                .filter(TaxaAntecipacaoCliente.cliente_id == cliente_id)
                .order_by(TaxaAntecipacaoCliente.bandeira, TaxaAntecipacaoCliente.taxa_percentual)
                .all()
            )

    return templates.TemplateResponse("admin/taxas_cartao.html", {
        "request": request,
        "usuario": usuario,
        "clientes": clientes,
        "taxas": taxas,
        "taxas_antecipacao": taxas_antecipacao,
        "maquininhas": maquininhas,
        "cliente_selecionado": cliente_selecionado,
        "maquininha_selecionada": maquininha_selecionada,
        "bandeiras": BANDEIRAS,
        "faixas": FAIXAS_PARCELAMENTO,
        "redes_maquininha": REDES_MAQUININHA,
        "pode_excluir": usuario.perfil == PerfilUsuario.coordenador,
    })


@router.post("/taxas-cartao")
async def criar_taxa(
    cliente_id: int = Form(...),
    maquininha_id: Optional[int] = Form(None),
    bandeira: str = Form(...),
    faixa_parcelamento: str = Form("avista_credito"),
    parcela_inicial: Optional[int] = Form(None),
    parcela_final: Optional[int] = Form(None),
    taxa_percentual: float = Form(...),
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_usuario_atual),
):
    if not pode_acessar_cliente(db, usuario, cliente_id):
        return RedirectResponse(url="/admin/taxas-cartao", status_code=303)

    bandeira = bandeira.strip()
    if bandeira not in BANDEIRAS or faixa_parcelamento not in FAIXAS_PARCELAMENTO_VALIDAS:
        return RedirectResponse(url=f"/admin/taxas-cartao?cliente_id={cliente_id}", status_code=303)
    if not 0 <= taxa_percentual <= 100:
        return RedirectResponse(url=f"/admin/taxas-cartao?cliente_id={cliente_id}", status_code=303)

    if maquininha_id:
        maquininha_valida = db.query(MaquininhaCliente.id).filter(
            MaquininhaCliente.id == maquininha_id,
            MaquininhaCliente.cliente_id == cliente_id,
            MaquininhaCliente.ativa == True,
        ).first()
        if not maquininha_valida:
            return RedirectResponse(url=f"/admin/taxas-cartao?cliente_id={cliente_id}", status_code=303)

    if faixa_parcelamento == "personalizada":
        if (
            parcela_inicial is None or parcela_final is None
            or parcela_inicial < 2 or parcela_final > 24
            or parcela_inicial > parcela_final
        ):
            return RedirectResponse(url=f"/admin/taxas-cartao?cliente_id={cliente_id}", status_code=303)
    else:
        parcela_inicial = None
        parcela_final = None

    q = db.query(TaxaCartaoCliente).filter(
        TaxaCartaoCliente.cliente_id == cliente_id,
        TaxaCartaoCliente.bandeira == bandeira,
        TaxaCartaoCliente.faixa_parcelamento == faixa_parcelamento,
        TaxaCartaoCliente.ativo == True,
    )
    if faixa_parcelamento == "personalizada":
        q = q.filter(
            TaxaCartaoCliente.parcela_inicial == parcela_inicial,
            TaxaCartaoCliente.parcela_final == parcela_final,
        )
    else:
        q = q.filter(
            TaxaCartaoCliente.parcela_inicial.is_(None),
            TaxaCartaoCliente.parcela_final.is_(None),
        )
    if maquininha_id:
        q = q.filter(TaxaCartaoCliente.maquininha_id == maquininha_id)
    else:
        q = q.filter(TaxaCartaoCliente.maquininha_id.is_(None))

    existente = q.first()
    if existente:
        existente.taxa_percentual = taxa_percentual
    else:
        db.add(TaxaCartaoCliente(
            cliente_id=cliente_id,
            maquininha_id=maquininha_id or None,
            bandeira=bandeira,
            faixa_parcelamento=faixa_parcelamento,
            parcela_inicial=parcela_inicial,
            parcela_final=parcela_final,
            taxa_percentual=taxa_percentual,
        ))
    db.commit()
    url = f"/admin/taxas-cartao?cliente_id={cliente_id}"
    if maquininha_id:
        url += f"&maquininha_id={maquininha_id}"
    return RedirectResponse(url=url, status_code=303)


@router.post("/taxas-cartao/{taxa_id}/excluir")
async def excluir_taxa(
    taxa_id: int,
    cliente_id: int = Form(...),
    maquininha_id: Optional[int] = Form(None),
    db: Session = Depends(get_db),
    _: Usuario = Depends(requer_coordenador),
):
    taxa = db.query(TaxaCartaoCliente).filter(TaxaCartaoCliente.id == taxa_id).first()
    if taxa:
        db.delete(taxa)
        db.commit()
    url = f"/admin/taxas-cartao?cliente_id={cliente_id}"
    if maquininha_id:
        url += f"&maquininha_id={maquininha_id}"
    return RedirectResponse(url=url, status_code=303)


# ---------------------------------------------------------------------------
# Maquininhas por cliente
# ---------------------------------------------------------------------------

@router.post("/clientes/cliente/{cliente_id}/maquininha/adicionar")
async def adicionar_maquininha(
    cliente_id: int,
    rede: str = Form(...),
    apelido: Optional[str] = Form(None),
    antecipa: str = Form("nao"),
    origem: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_usuario_atual),
):
    if not pode_acessar_cliente(db, usuario, cliente_id):
        return RedirectResponse(url="/admin/clientes", status_code=303)

    rede = rede.strip()
    apelido_limpo = (apelido or "").strip() or None
    if rede not in REDES_MAQUININHA:
        return RedirectResponse(
            url=_url_retorno_maquininha(cliente_id, origem), status_code=303,
        )

    existente = db.query(MaquininhaCliente).filter(
        MaquininhaCliente.cliente_id == cliente_id,
        MaquininhaCliente.rede == rede,
        MaquininhaCliente.apelido == apelido_limpo,
        MaquininhaCliente.ativa == True,
    ).first()
    if existente:
        return RedirectResponse(
            url=_url_retorno_maquininha(cliente_id, origem, existente.id), status_code=303,
        )

    nova_maquininha = MaquininhaCliente(
        cliente_id=cliente_id,
        rede=rede,
        apelido=apelido_limpo,
        antecipa=antecipa == "sim",
        ativa=True,
    )
    db.add(nova_maquininha)
    cliente = db.query(ClienteBPO).filter(ClienteBPO.id == cliente_id).first()
    if cliente:
        cliente.tem_maquininha = True
    db.commit()
    db.refresh(nova_maquininha)
    return RedirectResponse(
        url=_url_retorno_maquininha(cliente_id, origem, nova_maquininha.id), status_code=303,
    )


@router.post("/maquininha/{maquininha_id}/editar")
async def editar_maquininha(
    maquininha_id: int,
    rede: str = Form(...),
    apelido: Optional[str] = Form(None),
    antecipa: str = Form("nao"),
    origem: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_usuario_atual),
):
    maquininha = db.query(MaquininhaCliente).filter(
        MaquininhaCliente.id == maquininha_id,
        MaquininhaCliente.ativa == True,
    ).first()
    if not maquininha or not pode_acessar_cliente(db, usuario, maquininha.cliente_id):
        return RedirectResponse(url="/admin/clientes?erro=sem_acesso", status_code=303)

    rede = rede.strip()
    if rede not in REDES_MAQUININHA:
        return RedirectResponse(
            url=_url_retorno_maquininha(maquininha.cliente_id, origem, maquininha.id),
            status_code=303,
        )
    maquininha.rede = rede
    maquininha.apelido = (apelido or "").strip() or None
    maquininha.antecipa = antecipa == "sim"
    db.commit()
    return RedirectResponse(
        url=_url_retorno_maquininha(maquininha.cliente_id, origem, maquininha.id),
        status_code=303,
    )


# ---------------------------------------------------------------------------
# Toggle antecipa diretamente da página de taxas
# ---------------------------------------------------------------------------

@router.post("/taxas-cartao/toggle-antecipa")
async def toggle_antecipa_cliente(
    cliente_id: int = Form(...),
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_usuario_atual),
):
    if not pode_acessar_cliente(db, usuario, cliente_id):
        return RedirectResponse(url="/admin/taxas-cartao", status_code=303)
    cliente = db.query(ClienteBPO).filter(ClienteBPO.id == cliente_id).first()
    if cliente:
        cliente.antecipa = not cliente.antecipa
        db.commit()
    return RedirectResponse(url=f"/admin/taxas-cartao?cliente_id={cliente_id}", status_code=303)


# ---------------------------------------------------------------------------
# Taxas de antecipação
# ---------------------------------------------------------------------------

@router.post("/taxas-antecipacao")
async def criar_taxa_antecipacao(
    cliente_id: int = Form(...),
    bandeira: str = Form(...),
    descricao: str = Form(...),
    taxa_percentual: float = Form(...),
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_usuario_atual),
):
    if not pode_acessar_cliente(db, usuario, cliente_id):
        return RedirectResponse(url="/admin/taxas-cartao", status_code=303)

    cliente = db.query(ClienteBPO).filter(ClienteBPO.id == cliente_id).first()
    if not cliente or not cliente.antecipa:
        return RedirectResponse(url=f"/admin/taxas-cartao?cliente_id={cliente_id}", status_code=303)

    db.add(TaxaAntecipacaoCliente(
        cliente_id=cliente_id,
        bandeira=bandeira,
        descricao=descricao.strip(),
        taxa_percentual=taxa_percentual,
        selecionada=False,
        ativo=True,
    ))
    db.commit()
    return RedirectResponse(url=f"/admin/taxas-cartao?cliente_id={cliente_id}", status_code=303)


@router.post("/taxas-antecipacao/{taxa_id}/selecionar")
async def selecionar_taxa_antecipacao(
    taxa_id: int,
    cliente_id: int = Form(...),
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_usuario_atual),
):
    if not pode_acessar_cliente(db, usuario, cliente_id):
        return RedirectResponse(url="/admin/taxas-cartao", status_code=303)

    taxa = db.query(TaxaAntecipacaoCliente).filter(
        TaxaAntecipacaoCliente.id == taxa_id,
        TaxaAntecipacaoCliente.cliente_id == cliente_id,
    ).first()
    if taxa:
        # Desmarca todas do mesmo cliente+bandeira
        db.query(TaxaAntecipacaoCliente).filter(
            TaxaAntecipacaoCliente.cliente_id == cliente_id,
            TaxaAntecipacaoCliente.bandeira == taxa.bandeira,
        ).update({"selecionada": False})
        taxa.selecionada = True
        db.commit()
    return RedirectResponse(url=f"/admin/taxas-cartao?cliente_id={cliente_id}", status_code=303)


@router.post("/taxas-antecipacao/{taxa_id}/toggle-ativo")
async def toggle_ativo_antecipacao(
    taxa_id: int,
    cliente_id: int = Form(...),
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_usuario_atual),
):
    if not pode_acessar_cliente(db, usuario, cliente_id):
        return RedirectResponse(url="/admin/taxas-cartao", status_code=303)
    taxa = db.query(TaxaAntecipacaoCliente).filter(
        TaxaAntecipacaoCliente.id == taxa_id,
        TaxaAntecipacaoCliente.cliente_id == cliente_id,
    ).first()
    if taxa:
        taxa.ativo = not taxa.ativo
        if not taxa.ativo and taxa.selecionada:
            taxa.selecionada = False
        db.commit()
    return RedirectResponse(url=f"/admin/taxas-cartao?cliente_id={cliente_id}", status_code=303)


@router.post("/taxas-antecipacao/{taxa_id}/excluir")
async def excluir_taxa_antecipacao(
    taxa_id: int,
    cliente_id: int = Form(...),
    db: Session = Depends(get_db),
    _: Usuario = Depends(requer_coordenador),
):
    taxa = db.query(TaxaAntecipacaoCliente).filter(
        TaxaAntecipacaoCliente.id == taxa_id,
        TaxaAntecipacaoCliente.cliente_id == cliente_id,
    ).first()
    if taxa:
        db.delete(taxa)
        db.commit()
    return RedirectResponse(url=f"/admin/taxas-cartao?cliente_id={cliente_id}", status_code=303)


@router.get("/centros-custo", response_class=HTMLResponse)
async def pagina_centros_custo(
    request: Request,
    cliente_id: int,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_usuario_atual),
):
    if not pode_acessar_cliente(db, usuario, cliente_id):
        return RedirectResponse(url="/admin/clientes", status_code=303)
    cliente = db.query(ClienteBPO).filter(ClienteBPO.id == cliente_id).first()
    centros = db.query(CentroCusto).filter(
        CentroCusto.cliente_id == cliente_id,
        CentroCusto.ativo == True,
    ).order_by(CentroCusto.nome).all()
    return templates.TemplateResponse("admin/centros_custo.html", {
        "request": request,
        "usuario": usuario,
        "cliente": cliente,
        "centros": centros,
    })


@router.post("/centros-custo")
async def criar_centro_custo(
    cliente_id: int = Form(...),
    codigo: str = Form(...),
    nome: str = Form(...),
    is_medico: bool = Form(False),
    especialidade: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_usuario_atual),
):
    if not pode_acessar_cliente(db, usuario, cliente_id):
        return RedirectResponse(url="/admin/clientes", status_code=303)
    especialidade_medico = (especialidade or "").strip() if is_medico else None
    db.add(CentroCusto(
        codigo=codigo.strip(),
        nome=nome.strip(),
        cliente_id=cliente_id,
        is_medico=is_medico,
        especialidade=especialidade_medico or None,
    ))
    db.commit()
    return RedirectResponse(url=f"/admin/centros-custo?cliente_id={cliente_id}", status_code=303)


@router.post("/centros-custo/{cc_id}/excluir")
async def excluir_centro_custo(
    cc_id: int,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_usuario_atual),
):
    cc = db.query(CentroCusto).filter(CentroCusto.id == cc_id).first()
    if cc and pode_acessar_cliente(db, usuario, cc.cliente_id):
        cc.ativo = False
        db.commit()
        return RedirectResponse(url=f"/admin/centros-custo?cliente_id={cc.cliente_id}", status_code=303)
    return RedirectResponse(url="/admin/clientes", status_code=303)


@router.post("/centros-custo/{cc_id}/editar")
async def editar_centro_custo(
    cc_id: int,
    is_medico: bool = Form(False),
    especialidade: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_usuario_atual),
):
    cc = db.query(CentroCusto).filter(CentroCusto.id == cc_id).first()
    if not cc or not pode_acessar_cliente(db, usuario, cc.cliente_id):
        return RedirectResponse(url="/admin/clientes", status_code=303)
    cc.is_medico = is_medico
    cc.especialidade = ((especialidade or "").strip() or None) if is_medico else None
    db.commit()
    return RedirectResponse(url=f"/admin/centros-custo?cliente_id={cc.cliente_id}", status_code=303)


@router.post("/maquininha/{maquininha_id}/remover")
async def remover_maquininha(
    maquininha_id: int,
    origem: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_usuario_atual),
):
    maq = db.query(MaquininhaCliente).filter(MaquininhaCliente.id == maquininha_id).first()
    cliente_id = maq.cliente_id if maq else 0
    if maq and pode_acessar_cliente(db, usuario, maq.cliente_id):
        maq.ativa = False
        ativas = db.query(MaquininhaCliente).filter(
            MaquininhaCliente.cliente_id == maq.cliente_id,
            MaquininhaCliente.ativa == True,
            MaquininhaCliente.id != maquininha_id,
        ).count()
        if ativas == 0:
            cliente = db.query(ClienteBPO).filter(ClienteBPO.id == maq.cliente_id).first()
            if cliente:
                cliente.tem_maquininha = False
        db.commit()
    return RedirectResponse(
        url=_url_retorno_maquininha(cliente_id, origem), status_code=303,
    )
