"""Valida adicionar, editar e desativar maquininha sem deixar dados de teste."""
from __future__ import annotations

import sys
import time
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import httpx

from app.auth import criar_token
from app.database import SessionLocal
from app.models import ClienteBPO, MaquininhaCliente, PerfilUsuario, Usuario


def aguardar_aplicacao(base_url: str, timeout_seconds: int = 30) -> None:
    """Aguarda o servidor aceitar conexões antes de iniciar o fluxo mutável."""
    limite = time.monotonic() + timeout_seconds
    while time.monotonic() < limite:
        try:
            if httpx.get(f"{base_url}/login", timeout=2).status_code == 200:
                return
        except httpx.HTTPError:
            pass
        time.sleep(0.5)
    raise RuntimeError("Aplicação não ficou pronta para o teste de maquininhas.")


base_url = "http://127.0.0.1:8000"
aguardar_aplicacao(base_url)

with SessionLocal() as db:
    usuario = db.query(Usuario).filter(
        Usuario.perfil == PerfilUsuario.coordenador,
        Usuario.ativo == True,
    ).first()
    cliente = db.query(ClienteBPO).filter(ClienteBPO.ativo == True).first()
    assert usuario is not None and cliente is not None

    tem_maquininha_original = cliente.tem_maquininha
    marcador = f"TESTE-{uuid.uuid4().hex[:10]}"
    criada_id = None
    client = httpx.Client(
        base_url=base_url,
        cookies={
            "access_token": criar_token({"sub": str(usuario.id)}),
            "cliente_ativo": str(cliente.id),
        },
        headers={"Origin": "http://localhost:8888"},
        timeout=20,
        follow_redirects=False,
    )
    try:
        resposta = client.post(
            f"/admin/clientes/cliente/{cliente.id}/maquininha/adicionar",
            data={"rede": "Outro", "apelido": marcador, "antecipa": "nao", "origem": "taxas"},
        )
        assert resposta.status_code == 303
        db.expire_all()
        criada = db.query(MaquininhaCliente).filter(
            MaquininhaCliente.cliente_id == cliente.id,
            MaquininhaCliente.apelido == marcador,
        ).one()
        criada_id = criada.id
        assert criada.ativa is True

        resposta = client.post(
            f"/admin/maquininha/{criada.id}/editar",
            data={"rede": "SumUp", "apelido": marcador, "antecipa": "sim", "origem": "taxas"},
        )
        assert resposta.status_code == 303
        db.expire_all()
        criada = db.get(MaquininhaCliente, criada.id)
        assert criada.rede == "SumUp" and criada.antecipa is True

        pagina = client.get("/admin/taxas-cartao", params={"cliente_id": cliente.id})
        assert pagina.status_code == 200 and marcador in pagina.text

        resposta = client.post(
            f"/admin/maquininha/{criada.id}/remover",
            data={"origem": "taxas"},
        )
        assert resposta.status_code == 303
        db.expire_all()
        assert db.get(MaquininhaCliente, criada.id).ativa is False
    finally:
        client.close()
        if criada_id:
            temporaria = db.get(MaquininhaCliente, criada_id)
            if temporaria:
                db.delete(temporaria)
        cliente_atual = db.get(ClienteBPO, cliente.id)
        cliente_atual.tem_maquininha = tem_maquininha_original
        db.commit()

print("fluxo_maquininha=adicionar+editar+desativar; limpeza=ok")
