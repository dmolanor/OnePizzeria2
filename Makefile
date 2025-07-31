# Makefile para One Pizzeria Bot

.PHONY: help dev prod build test clean logs status health

# Variables
COMPOSE_FILE = docker-compose.yml
COMPOSE_DEV_FILE = docker-compose.dev.yml
SERVICE_NAME = pizzeria-bot
DEV_SERVICE_NAME = pizzeria-bot-dev

# Mostrar ayuda por defecto
help:
	@echo "🍕 One Pizzeria Bot - Comandos Disponibles"
	@echo ""
	@echo "📋 Desarrollo:"
	@echo "  make dev        - Ejecutar en modo desarrollo con hot reload"
	@echo "  make dev-build  - Construir y ejecutar en desarrollo"
	@echo "  make dev-down   - Parar servicios de desarrollo"
	@echo ""
	@echo "🚀 Producción:"
	@echo "  make prod       - Ejecutar en modo producción"
	@echo "  make prod-build - Construir y ejecutar en producción"
	@echo "  make prod-down  - Parar servicios de producción"
	@echo ""
	@echo "🔧 Utilidades:"
	@echo "  make build      - Solo construir imagen"
	@echo "  make test       - Ejecutar tests"
	@echo "  make logs       - Ver logs en tiempo real"
	@echo "  make status     - Ver estado de servicios"
	@echo "  make health     - Verificar health check"
	@echo "  make clean      - Limpiar contenedores y volúmenes"
	@echo ""
	@echo "🏃‍♂️ Ejecución Local (sin Docker):"
	@echo "  make local      - Ejecutar con uv python"
	@echo "  make install    - Instalar dependencias con uv"

# Desarrollo
dev:
	@echo "🔄 Iniciando en modo desarrollo..."
	docker-compose -f $(COMPOSE_DEV_FILE) up -d

dev-build:
	@echo "🔨 Construyendo y ejecutando en desarrollo..."
	docker-compose -f $(COMPOSE_DEV_FILE) up --build -d

dev-down:
	@echo "⏹️ Parando servicios de desarrollo..."
	docker-compose -f $(COMPOSE_DEV_FILE) down

# Producción
prod:
	@echo "🚀 Iniciando en modo producción..."
	docker-compose -f $(COMPOSE_FILE) up -d

prod-build:
	@echo "🔨 Construyendo y ejecutando en producción..."
	docker-compose -f $(COMPOSE_FILE) up --build -d

prod-down:
	@echo "⏹️ Parando servicios de producción..."
	docker-compose -f $(COMPOSE_FILE) down

# Construcción
build:
	@echo "🔨 Construyendo imagen Docker..."
	docker build -t pizzeria-bot:latest .

# Tests
test:
	@echo "🧪 Ejecutando tests..."
	uv run python -m pytest tests/ -v

test-docker:
	@echo "🧪 Ejecutando tests en Docker..."
	docker run --rm pizzeria-bot:latest python -m pytest tests/ -v

# Utilidades
logs:
	@echo "📋 Mostrando logs (Ctrl+C para salir)..."
	docker-compose -f $(COMPOSE_FILE) logs -f $(SERVICE_NAME)

logs-dev:
	@echo "📋 Mostrando logs de desarrollo (Ctrl+C para salir)..."
	docker-compose -f $(COMPOSE_DEV_FILE) logs -f $(DEV_SERVICE_NAME)

status:
	@echo "📊 Estado de servicios de producción:"
	docker-compose -f $(COMPOSE_FILE) ps
	@echo ""
	@echo "📊 Estado de servicios de desarrollo:"
	docker-compose -f $(COMPOSE_DEV_FILE) ps

health:
	@echo "🏥 Verificando health check..."
	curl -f http://localhost:5000/health || echo "❌ Health check falló"

# Limpieza
clean:
	@echo "🧹 Limpiando contenedores y volúmenes..."
	docker-compose -f $(COMPOSE_FILE) down -v
	docker-compose -f $(COMPOSE_DEV_FILE) down -v
	docker system prune -f

clean-all:
	@echo "🧹 Limpieza completa (¡CUIDADO! Elimina imágenes)..."
	docker-compose -f $(COMPOSE_FILE) down -v --rmi all
	docker-compose -f $(COMPOSE_DEV_FILE) down -v --rmi all
	docker system prune -a -f

# Ejecución local sin Docker
local:
	@echo "🏃‍♂️ Ejecutando localmente con uv..."
	uv run python main.py --config
	uv run python main.py

install:
	@echo "📦 Instalando dependencias con uv..."
	uv sync

# Comandos de mantenimiento
restart:
	@echo "🔄 Reiniciando servicio de producción..."
	docker-compose -f $(COMPOSE_FILE) restart $(SERVICE_NAME)

restart-dev:
	@echo "🔄 Reiniciando servicio de desarrollo..."
	docker-compose -f $(COMPOSE_DEV_FILE) restart $(DEV_SERVICE_NAME)

update:
	@echo "⬆️ Actualizando y reiniciando..."
	git pull
	docker-compose -f $(COMPOSE_FILE) pull
	docker-compose -f $(COMPOSE_FILE) up -d

# Monitoring
stats:
	@echo "📊 Estadísticas de recursos:"
	docker stats $(SERVICE_NAME) --no-stream 2>/dev/null || echo "Servicio no está ejecutándose"

backup:
	@echo "💾 Creando backup..."
	mkdir -p backups
	docker-compose -f $(COMPOSE_FILE) exec postgres pg_dump -U user dbname > "backups/backup_$(shell date +%Y%m%d_%H%M%S).sql"

# Configuración
config-check:
	@echo "⚙️ Verificando configuración..."
	uv run python main.py --config

env-example:
	@echo "📄 Mostrando ejemplo de configuración..."
	cat config.example.env

# Default target
.DEFAULT_GOAL := help