"""Cifra/decifra backups em streaming com uma chave exclusiva."""
from __future__ import annotations

import argparse
import base64
import os
import sys
import tempfile
from pathlib import Path

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.config import BACKUP_ENCRYPTION_KEY


MAGIC = b"FLIC-BACKUP-AESGCM-v2\0"
NONCE_SIZE = 12
TAG_SIZE = 16
CHUNK_SIZE = 1024 * 1024


def _backup_key() -> bytes:
    if not BACKUP_ENCRYPTION_KEY:
        raise RuntimeError("BACKUP_ENCRYPTION_KEY nao configurada.")
    key = base64.urlsafe_b64decode(BACKUP_ENCRYPTION_KEY.encode("ascii"))
    if len(key) != 64:
        raise RuntimeError("BACKUP_ENCRYPTION_KEY deve representar 64 bytes.")
    return key[:32]


def _temporary_target(target: Path):
    target.parent.mkdir(parents=True, exist_ok=True)
    return tempfile.NamedTemporaryFile(
        mode="wb",
        prefix=f".{target.name}.",
        dir=target.parent,
        delete=False,
    )


def encrypt(source: Path, target: Path) -> None:
    nonce = os.urandom(NONCE_SIZE)
    encryptor = Cipher(algorithms.AES(_backup_key()), modes.GCM(nonce)).encryptor()
    encryptor.authenticate_additional_data(MAGIC)
    temporary: Path | None = None
    try:
        with source.open("rb") as input_file, _temporary_target(target) as output_file:
            temporary = Path(output_file.name)
            output_file.write(MAGIC + nonce)
            while chunk := input_file.read(CHUNK_SIZE):
                output_file.write(encryptor.update(chunk))
            output_file.write(encryptor.finalize())
            output_file.write(encryptor.tag)
        os.replace(temporary, target)
    except Exception:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
        raise


def decrypt(source: Path, target: Path) -> None:
    minimum_size = len(MAGIC) + NONCE_SIZE + TAG_SIZE
    if source.stat().st_size < minimum_size:
        raise ValueError("Formato de backup cifrado invalido.")
    temporary: Path | None = None
    try:
        with source.open("rb") as input_file:
            if input_file.read(len(MAGIC)) != MAGIC:
                raise ValueError("Formato de backup cifrado invalido.")
            nonce = input_file.read(NONCE_SIZE)
            input_file.seek(-TAG_SIZE, os.SEEK_END)
            tag = input_file.read(TAG_SIZE)
            ciphertext_size = source.stat().st_size - minimum_size
            input_file.seek(len(MAGIC) + NONCE_SIZE)
            decryptor = Cipher(
                algorithms.AES(_backup_key()),
                modes.GCM(nonce, tag),
            ).decryptor()
            decryptor.authenticate_additional_data(MAGIC)
            with _temporary_target(target) as output_file:
                temporary = Path(output_file.name)
                remaining = ciphertext_size
                while remaining:
                    chunk = input_file.read(min(CHUNK_SIZE, remaining))
                    if not chunk:
                        raise ValueError("Backup cifrado truncado.")
                    remaining -= len(chunk)
                    output_file.write(decryptor.update(chunk))
                output_file.write(decryptor.finalize())
        os.replace(temporary, target)
    except Exception:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
        raise


parser = argparse.ArgumentParser()
parser.add_argument("operation", choices=("encrypt", "decrypt"))
parser.add_argument("source", type=Path)
parser.add_argument("target", type=Path)
parser.add_argument("--delete-source", action="store_true")
args = parser.parse_args()

if args.source.resolve() == args.target.resolve():
    parser.error("source e target devem ser arquivos diferentes")
if args.operation == "encrypt":
    encrypt(args.source, args.target)
else:
    decrypt(args.source, args.target)
if args.delete_source:
    args.source.unlink()
print(f"Backup {args.operation} concluido: {args.target}")
