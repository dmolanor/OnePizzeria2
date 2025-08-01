# 🚀 Guía de Producción - One Pizzeria Bot

## 📋 Configuración con Docker

### Archivos Creados
- `Dockerfile` - Imagen optimizada para producción
- `docker-compose.yml` - Orquestación de servicios
- `.dockerignore` - Optimización del build
- `/health` endpoint agregado para monitoring

### Comandos Básicos

```bash
# Construir y ejecutar
docker-compose up --build -d

# Ver logs
docker-compose logs -f pizzeria-bot

# Parar servicios
docker-compose down

# Reconstruir solo el bot
docker-compose up --build pizzeria-bot
```

### ¿Puedo seguir usando `uv python run main.py`?

**✅ SÍ**, puedes seguir usando `uv python run main.py` para:
- **Desarrollo local**: Perfecto para testing rápido
- **Debugging**: Más fácil para usar debuggers
- **CI/CD**: Para tests automatizados

**🐳 Docker es recomendado para**:
- **Producción**: Consistencia entre entornos
- **Despliegue**: En servidores remotos
- **Escalabilidad**: Múltiples instancias

## 🔧 Mejoras Recomendadas para Producción

### 1. 🛡️ Seguridad

#### Variables de Entorno Seguras
```bash
# En lugar de archivo .env, usar secrets
docker secret create telegram_token /path/to/token.txt
docker secret create whatsapp_token /path/to/whatsapp_token.txt
```

#### Reverse Proxy (Nginx)
```nginx
# /etc/nginx/sites-available/pizzeria-bot
server {
    listen 443 ssl;
    server_name tu-dominio.com;
    
    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;
    
    location /webhook/whatsapp {
        proxy_pass http://localhost:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
    
    location /health {
        proxy_pass http://localhost:5000;
    }
}
```

### 2. 📊 Monitoring y Observabilidad

#### Health Checks
- ✅ Endpoint `/health` implementado
- 🔄 Liveness y readiness probes en K8s
- 📈 Métricas de sistema

#### Logging Estructurado
```python
# config/logging.py (crear)
import structlog
import logging.config

LOGGING_CONFIG = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'json': {
            'format': '%(message)s',
            'class': 'pythonjsonlogger.jsonlogger.JsonFormatter'
        }
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'json'
        },
        'file': {
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': 'logs/pizzeria-bot.log',
            'maxBytes': 10485760,  # 10MB
            'backupCount': 5,
            'formatter': 'json'
        }
    },
    'root': {
        'level': 'INFO',
        'handlers': ['console', 'file']
    }
}
```

#### Métricas con Prometheus
```python
# src/monitoring/metrics.py (crear)
from prometheus_client import Counter, Histogram, Gauge, start_http_server

# Métricas de negocio
ORDERS_TOTAL = Counter('pizzeria_orders_total', 'Total orders processed')
RESPONSE_TIME = Histogram('pizzeria_response_seconds', 'Response time')
ACTIVE_USERS = Gauge('pizzeria_active_users', 'Current active users')

def init_metrics():
    """Inicializar servidor de métricas"""
    start_http_server(8000)  # Puerto separado para métricas
```

### 3. 🔄 CI/CD Pipeline

#### GitHub Actions (.github/workflows/deploy.yml)
```yaml
name: Deploy to Production

on:
  push:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Build Docker image
        run: docker build -t pizzeria-bot:${{ github.sha }} .
      
      - name: Run tests
        run: docker run --rm pizzeria-bot:${{ github.sha }} python -m pytest
      
      - name: Deploy to production
        run: |
          docker tag pizzeria-bot:${{ github.sha }} pizzeria-bot:latest
          # Deploy to your server
```

### 4. 📈 Escalabilidad

#### Load Balancer Config
```yaml
# docker-compose.production.yml
version: '3.8'
services:
  pizzeria-bot:
    deploy:
      replicas: 3
      update_config:
        parallelism: 1
        delay: 10s
      restart_policy:
        condition: on-failure
        delay: 5s
        max_attempts: 3
  
  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf
    depends_on:
      - pizzeria-bot
```

#### Redis para Estado Compartido
```python
# config/settings.py (agregar)
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")

# src/core/cache.py (crear)
import redis
from config.settings import REDIS_URL

redis_client = redis.from_url(REDIS_URL)

def get_user_state(user_id: str):
    return redis_client.get(f"user:{user_id}:state")

def set_user_state(user_id: str, state: dict):
    redis_client.setex(f"user:{user_id}:state", 3600, json.dumps(state))
```

### 5. 🔐 Base de Datos

#### Migraciones Automáticas
```python
# scripts/migrate.py (crear)
import logging
from supabase import create_client
from config.settings import SUPABASE_URL, SUPABASE_KEY

def run_migrations():
    """Ejecutar migraciones de base de datos"""
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    
    # Crear tablas si no existen
    migrations = [
        "CREATE TABLE IF NOT EXISTS orders (...)",
        "CREATE INDEX IF NOT EXISTS idx_orders_created_at ON orders(created_at)",
        # Más migraciones...
    ]
    
    for migration in migrations:
        try:
            supabase.rpc('execute_sql', {'sql': migration}).execute()
            logging.info(f"Migration executed: {migration[:50]}...")
        except Exception as e:
            logging.error(f"Migration failed: {e}")
```

#### Backup Automático
```bash
#!/bin/bash
# scripts/backup.sh
DATE=$(date +%Y%m%d_%H%M%S)
pg_dump $DATABASE_URL > "backups/pizzeria_$DATE.sql"
# Subir a S3 o storage similar
aws s3 cp "backups/pizzeria_$DATE.sql" s3://tu-bucket/backups/
```

### 6. 🚨 Alerting

#### Webhooks de Alerta
```python
# src/monitoring/alerts.py (crear)
import requests
import logging

def send_alert(message: str, severity: str = "warning"):
    """Enviar alerta a Slack/Discord/Teams"""
    webhook_url = os.getenv("ALERT_WEBHOOK_URL")
    if not webhook_url:
        return
    
    payload = {
        "text": f"🚨 {severity.upper()}: {message}",
        "username": "Pizzeria Bot Monitor"
    }
    
    try:
        requests.post(webhook_url, json=payload)
    except Exception as e:
        logging.error(f"Failed to send alert: {e}")

# Usar en puntos críticos
def handle_order_error(error):
    send_alert(f"Order processing failed: {error}", "critical")
```

## 🎯 Plan de Implementación

### Fase 1: Básico (Semana 1)
- ✅ Docker configurado
- ✅ Health checks
- 🔄 SSL/HTTPS con reverse proxy
- 📊 Logging estructurado

### Fase 2: Producción (Semana 2-3)
- 🔐 Secrets management
- 📈 Métricas básicas
- 🔄 CI/CD pipeline
- 💾 Backups automáticos

### Fase 3: Escalabilidad (Semana 4+)
- ⚖️ Load balancing
- 🔄 Redis para caché
- 📊 Monitoring avanzado
- 🚨 Alerting completo

## 📝 Comandos de Mantenimiento

```bash
# Actualizar en producción
docker-compose pull
docker-compose up -d

# Ver métricas
curl http://localhost:8000/metrics

# Backup manual
docker exec pizzeria-db pg_dump -U user dbname > backup.sql

# Logs en tiempo real
docker-compose logs -f --tail=100 pizzeria-bot

# Reiniciar solo el bot
docker-compose restart pizzeria-bot

# Limpiar logs viejos
docker system prune -f
```

## 🔍 Troubleshooting

### Problemas Comunes

1. **Puerto 5000 ocupado**
   ```bash
   # Cambiar puerto en docker-compose.yml
   ports:
     - "5001:5000"
   ```

2. **WhatsApp webhook no responde**
   - Verificar HTTPS
   - Comprobar firewall
   - Revisar logs: `docker-compose logs whatsapp`

3. **Memoria insuficiente**
   ```yaml
   # En docker-compose.yml
   deploy:
     resources:
       limits:
         memory: 1G
   ```

## 🚀 ¡Listo para Producción!

Con esta configuración tendrás:
- 🐳 Contenedores optimizados
- 🔒 Seguridad básica
- 📊 Monitoring
- 🔄 Actualizaciones automáticas
- 💾 Persistencia de datos

**¿Siguiente paso?** Implementa las mejoras fase por fase según tus necesidades.