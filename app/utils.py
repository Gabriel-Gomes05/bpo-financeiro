import os
import uuid
from pathlib import Path
from typing import Optional

from fastapi import Request, UploadFile

from app.config import UPLOAD_DIR


MAX_UPLOAD_BYTES = 10 * 1024 * 1024

ASSINATURAS_PERMITIDAS = {
    ".pdf": (b"%PDF-",),
    ".png": (b"\x89PNG\r\n\x1a\n",),
    ".jpg": (b"\xff\xd8\xff",),
    ".jpeg": (b"\xff\xd8\xff",),
    ".xlsx": (b"PK\x03\x04",),
    # Alguns relatórios .xls são planilhas OOXML (.xlsx) apenas com a extensão errada.
    ".xls": (b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1", b"PK\x03\x04"),
}


def cliente_ativo(request: Request, cliente_id: Optional[int]) -> Optional[int]:
    """Retorna cliente_id do param URL; se None, lê do cookie 'cliente_ativo'."""
    raw = request.cookies.get("cliente_ativo", "")
    try:
        return int(raw) if raw else cliente_id
    except (ValueError, TypeError):
        return None


async def salvar_upload_temporario(
    arquivo: UploadFile,
    extensoes_permitidas: set[str],
    max_bytes: int = MAX_UPLOAD_BYTES,
) -> tuple[str, str, str]:
    """Valida extensao/tamanho e salva o upload em arquivo temporario."""
    nome_original = os.path.basename(arquivo.filename or "")
    if not nome_original:
        raise ValueError("Arquivo sem nome.")

    ext = os.path.splitext(nome_original)[1].lower()
    permitidas = {e.lower() for e in extensoes_permitidas}
    if ext not in permitidas:
        raise ValueError(
            "Tipo de arquivo nao permitido. Envie: "
            + ", ".join(sorted(permitidas))
        )

    upload_dir = Path(UPLOAD_DIR).resolve()
    upload_dir.mkdir(parents=True, exist_ok=True)
    caminho_path = (upload_dir / f"{uuid.uuid4().hex}{ext}").resolve()
    if upload_dir not in caminho_path.parents:
        raise ValueError("Diretorio de upload invalido.")

    caminho = str(caminho_path)
    total = 0
    inicio = b""

    try:
        with open(caminho, "wb") as f:
            while True:
                chunk = await arquivo.read(1024 * 1024)
                if not chunk:
                    break
                total += len(chunk)
                if total > max_bytes:
                    raise ValueError("Arquivo maior que 10 MB.")
                if len(inicio) < 16:
                    inicio += chunk[: 16 - len(inicio)]
                f.write(chunk)
        if total == 0:
            raise ValueError("Arquivo vazio.")
        _validar_assinatura(ext, inicio)
    except Exception:
        try:
            os.remove(caminho)
        except OSError:
            pass
        raise

    return caminho, nome_original, ext


def _validar_assinatura(ext: str, inicio: bytes) -> None:
    assinaturas = ASSINATURAS_PERMITIDAS.get(ext)
    if assinaturas and not any(inicio.startswith(sig) for sig in assinaturas):
        raise ValueError("Conteudo do arquivo nao corresponde ao tipo informado.")
