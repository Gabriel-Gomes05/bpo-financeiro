"""Cifra/decifra backups locais com a chave de campos da aplicacao."""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.field_encryption import _key


MAGIC = b"FLIC-BACKUP-AESGCM-v1\0"


def encrypt(source: Path, target: Path) -> None:
    nonce = os.urandom(12)
    payload = AESGCM(_key()[:32]).encrypt(nonce, source.read_bytes(), MAGIC)
    target.write_bytes(MAGIC + nonce + payload)


def decrypt(source: Path, target: Path) -> None:
    raw = source.read_bytes()
    if not raw.startswith(MAGIC):
        raise ValueError("Formato de backup cifrado invalido.")
    nonce = raw[len(MAGIC):len(MAGIC) + 12]
    payload = raw[len(MAGIC) + 12:]
    target.write_bytes(AESGCM(_key()[:32]).decrypt(nonce, payload, MAGIC))


parser = argparse.ArgumentParser()
parser.add_argument("operation", choices=("encrypt", "decrypt"))
parser.add_argument("source", type=Path)
parser.add_argument("target", type=Path)
parser.add_argument("--delete-source", action="store_true")
args = parser.parse_args()

if args.operation == "encrypt":
    encrypt(args.source, args.target)
else:
    decrypt(args.source, args.target)
if args.delete_source:
    args.source.unlink()
print(f"Backup {args.operation} concluido: {args.target}")
