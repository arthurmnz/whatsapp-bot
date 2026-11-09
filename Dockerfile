FROM python:3.11-slim

WORKDIR /app

# Evita arquivos .pyc e garante logs em tempo real no Docker (sem buffer no print)
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

# Instala dependências Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copia o código da aplicação e configurações
COPY src/ ./src/
COPY config/ ./config/

EXPOSE 5000

CMD ["uvicorn", "src.webhook:app", "--host", "0.0.0.0", "--port", "5000"]
