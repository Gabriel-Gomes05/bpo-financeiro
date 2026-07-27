"""Configuração do servidor de produção, controlada por ambiente."""
import os

bind = f"{os.environ['HOST']}:{os.environ['PORT']}"
workers = int(os.getenv("WEB_CONCURRENCY", "2"))
worker_class = "uvicorn.workers.UvicornWorker"
control_socket_disable = True
timeout = int(os.getenv("WORKER_TIMEOUT_SECONDS", "60"))
graceful_timeout = int(os.getenv("WORKER_GRACEFUL_TIMEOUT_SECONDS", "30"))
keepalive = int(os.getenv("KEEPALIVE_SECONDS", "5"))
accesslog = None
errorlog = "-"
capture_output = True
preload_app = False
max_requests = int(os.getenv("MAX_REQUESTS_PER_WORKER", "2000"))
max_requests_jitter = int(os.getenv("MAX_REQUESTS_JITTER", "200"))
