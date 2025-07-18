# gunicorn-cfg.py
# -*- encoding: utf-8 -*-

bind = '0.0.0.0:5005'
workers = 9  # Ajuste conforme o número de núcleos (2 * núcleos + 1)
threads = 4  # Ajuste conforme o overhead do I/O
timeout = 600  # 6 minuto para a maioria das requisições
graceful_timeout = 60
max_requests = 1000  # Reinicia worker após processar 1000 requisições
max_requests_jitter = 50  # Aleatoriedade para evitar todos os workers reiniciarem ao mesmo tempo
accesslog = '-'
loglevel = 'info'  # Use 'info' ou 'warning' para produção
capture_output = True
enable_stdio_inheritance = True