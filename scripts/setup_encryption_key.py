"""Gera FIELD_ENCRYPTION_KEY sem imprimir o segredo no terminal."""
from __future__ import annotations

import base64
import os
from pathlib import Path


env_path = Path(__file__).resolve().parents[1] / ".env"
lines = env_path.read_text(encoding="utf-8").splitlines() if env_path.exists() else []
if any(line.startswith("FIELD_ENCRYPTION_KEY=") and line.split("=", 1)[1].strip() for line in lines):
    print("FIELD_ENCRYPTION_KEY ja esta configurada; nenhuma alteracao feita.")
    raise SystemExit(0)

entry = "FIELD_ENCRYPTION_KEY=" + base64.urlsafe_b64encode(os.urandom(64)).decode("ascii")
lines = [line for line in lines if not line.startswith("FIELD_ENCRYPTION_KEY=")]
lines.append(entry)
env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
print("FIELD_ENCRYPTION_KEY gerada e salva no .env sem exibir o segredo.")

