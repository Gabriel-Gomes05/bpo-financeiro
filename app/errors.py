"""Mensagens públicas estáveis para falhas inesperadas."""
from __future__ import annotations

import logging


def public_import_error(logger: logging.Logger, operation: str) -> str:
    logger.exception("file_processing_failed", extra={"operation": operation})
    return "Não foi possível processar o arquivo. Verifique o formato e tente novamente."
