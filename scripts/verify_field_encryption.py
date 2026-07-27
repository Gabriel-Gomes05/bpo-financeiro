"""Confirma que nao restou texto legado e testa leitura/busca pelo ORM."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import text

from app.database import SessionLocal, engine
from app.field_encryption import BASIC_PLAINTEXT_FIELDS, SENSITIVE_FIELDS
from app.models import Usuario


falhas = []
basicos_ainda_cifrados = []
with engine.connect() as conn:
    for tabela, coluna, _, _ in SENSITIVE_FIELDS:
        quantidade = conn.execute(text(
            f'SELECT count(*) FROM "{tabela}" '
            f'WHERE "{coluna}" IS NOT NULL AND "{coluna}" <> \'\' '
            f'AND "{coluna}" NOT LIKE \'enc:v1:%\''
        )).scalar_one()
        if quantidade:
            falhas.append((tabela, coluna, quantidade))
    for tabela, coluna in BASIC_PLAINTEXT_FIELDS:
        quantidade = conn.execute(text(
            f'SELECT count(*) FROM "{tabela}" '
            f'WHERE "{coluna}" LIKE \'enc:v1:%\''
        )).scalar_one()
        if quantidade:
            basicos_ainda_cifrados.append((tabela, coluna, quantidade))

with SessionLocal() as db:
    usuario = db.query(Usuario).first()
    assert usuario is not None
    assert not usuario.email.startswith("enc:v1:")
    encontrado = db.query(Usuario).filter(Usuario.email == usuario.email).first()
    assert encontrado is not None and encontrado.id == usuario.id

assert not falhas, f"Campos com texto legado: {falhas}"
assert not basicos_ainda_cifrados, (
    f"Campos basicos ainda cifrados: {basicos_ainda_cifrados}"
)
print(
    f"campos_sensiveis_verificados={len(SENSITIVE_FIELDS)}; "
    f"campos_basicos_verificados={len(BASIC_PLAINTEXT_FIELDS)}; "
    "sensiveis_nao_cifrados=0; basicos_cifrados=0; "
    "leitura_orm_e_busca_email=ok"
)
