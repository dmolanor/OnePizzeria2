# Dockerfile para One Pizzeria Bot - Producción
# Usando Python 3.12 oficial como base
FROM python:3.12-slim

# Metadatos
LABEL maintainer="One Pizzeria Bot"
LABEL description="Multi-platform pizzeria bot with Telegram and WhatsApp support"
LABEL version="1.0.0"

# Variables de entorno para Python
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Crear usuario no-root para seguridad
RUN groupadd --gid 1000 appuser && \
    useradd --uid 1000 --gid appuser --shell /bin/bash --create-home appuser

# Instalar dependencias del sistema
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Crear directorio de la aplicación
WORKDIR /app

# Copiar archivos de configuración de dependencias
COPY pyproject.toml requirements.txt ./

# Instalar uv para gestión rápida de dependencias
RUN pip install uv

# Instalar dependencias usando uv (más rápido)
RUN uv pip install --system -r requirements.txt

# Copiar el código de la aplicación
COPY . .

# Cambiar ownership al usuario no-root
RUN chown -R appuser:appuser /app

# Cambiar al usuario no-root
USER appuser

# Exponer puerto para WhatsApp webhook
EXPOSE 5000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:5000/health', timeout=5)" || exit 1

# Comando por defecto - ejecutar ambas plataformas
CMD ["python", "main.py", "--platform", "both", "--host", "0.0.0.0", "--port", "5000"]