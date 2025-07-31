# 📱 WhatsApp Business API Setup Guide

Esta guía te ayudará a configurar el bot de WhatsApp para One Pizzeria usando la WhatsApp Business API oficial de Meta.

## 📋 Tabla de Contenidos

1. [Requisitos Previos](#requisitos-previos)
2. [Configuración de Meta for Developers](#configuración-de-meta-for-developers)
3. [Obtener Credenciales](#obtener-credenciales)
4. [Configurar Variables de Entorno](#configurar-variables-de-entorno)
5. [Configurar Webhook](#configurar-webhook)
6. [Ejecutar el Bot](#ejecutar-el-bot)
7. [Verificación y Pruebas](#verificación-y-pruebas)
8. [Resolución de Problemas](#resolución-de-problemas)

## 🔧 Requisitos Previos

### Cuentas Necesarias
- ✅ **Cuenta de Facebook Business**: Para acceder a Meta for Developers
- ✅ **Número de teléfono comercial**: Para WhatsApp Business API
- ✅ **Servidor público o túnel**: Para recibir webhooks (recomendamos ngrok para desarrollo)

### Verificaciones Importantes
- 📱 El número de teléfono **NO** debe estar registrado en WhatsApp personal
- 🏢 Debe ser un número comercial verificable
- 🌐 Necesitas acceso a un servidor público o herramientas como ngrok

## 🏗️ Configuración de Meta for Developers

### Paso 1: Crear Aplicación en Meta for Developers

1. Ve a [Meta for Developers](https://developers.facebook.com/)
2. Inicia sesión con tu cuenta de Facebook Business
3. Haz clic en **"Crear aplicación"**
4. Selecciona **"Empresa"** como tipo de aplicación
5. Completa la información:
   - **Nombre de la aplicación**: `One Pizzeria Bot`
   - **Email de contacto**: Tu email comercial
   - **Categoría**: `Empresa`

### Paso 2: Añadir WhatsApp Business API

1. En el dashboard de tu aplicación
2. Busca **"WhatsApp"** en la lista de productos
3. Haz clic en **"Configurar"**
4. Sigue el proceso de configuración inicial

### Paso 3: Verificación Comercial

> ⚠️ **Importante**: Para usar WhatsApp Business API en producción, necesitas completar la verificación comercial de Meta.

1. Ve a **Configuración de la aplicación** → **Básico**
2. Completa toda la información comercial requerida
3. Sube documentos de verificación (puede tomar 2-5 días hábiles)

## 🔑 Obtener Credenciales

### 1. Access Token (Token de Acceso)

```bash
# Ubicación: WhatsApp > API Setup
# Copia el "Temporary access token" o genera uno permanente
```

**Para Desarrollo (Temporal - 24 horas):**
- Usa el token temporal proporcionado en la consola

**Para Producción (Permanente):**
1. Ve a **WhatsApp** → **Configuration**
2. Crea un **System User** con permisos `whatsapp_business_messaging`
3. Genera un **Access Token** permanente

### 2. Phone Number ID

```bash
# Ubicación: WhatsApp > API Setup
# En la sección "From phone number ID"
# Ejemplo: 123456789012345
```

### 3. Webhook Verify Token

```bash
# Este token lo defines tú mismo
# Recomendación: Usa un string aleatorio y seguro
# Ejemplo: "mi_webhook_token_super_secreto_2024"
```

### 4. WhatsApp Business Account ID (WABA ID)

```bash
# Ubicación: WhatsApp > API Setup  
# En la parte superior de la página
# Ejemplo: 987654321098765
```

## ⚙️ Configurar Variables de Entorno

Agrega las siguientes variables a tu archivo `.env`:

```bash
# WhatsApp Business API Configuration
WHATSAPP_ACCESS_TOKEN=tu_access_token_aqui
WHATSAPP_PHONE_NUMBER_ID=123456789012345
WHATSAPP_WEBHOOK_VERIFY_TOKEN=mi_webhook_token_super_secreto_2024
WHATSAPP_API_URL=https://graph.facebook.com/v18.0

# Opcional: Para desarrollo local
WHATSAPP_WEBHOOK_HOST=0.0.0.0
WHATSAPP_WEBHOOK_PORT=5000
```

### Ejemplo completo de .env

```bash
# Telegram (existente)
TELEGRAM_BOT_TOKEN=tu_telegram_token

# WhatsApp (nuevo)
WHATSAPP_ACCESS_TOKEN=EAAxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
WHATSAPP_PHONE_NUMBER_ID=123456789012345
WHATSAPP_WEBHOOK_VERIFY_TOKEN=mi_webhook_super_secreto_2024
WHATSAPP_API_URL=https://graph.facebook.com/v18.0

# Base de datos y otros servicios (existentes)
SUPABASE_URL=tu_supabase_url
SUPABASE_KEY=tu_supabase_key
# ... otras variables
```

## 🌐 Configurar Webhook

### Para Desarrollo Local (usando ngrok)

#### Paso 1: Instalar ngrok
```bash
# macOS
brew install ngrok

# Windows
# Descarga desde https://ngrok.com/download

# Linux
sudo snap install ngrok
```

#### Paso 2: Exponer tu servidor local
```bash
# Inicia tu bot de WhatsApp (en otra terminal)
python main.py --platform whatsapp --port 5000

# En otra terminal, ejecuta ngrok
ngrok http 5000
```

#### Paso 3: Copiar URL pública
```bash
# ngrok te dará una URL como:
# https://abc123.ngrok-free.app

# Tu webhook URL será:
# https://abc123.ngrok-free.app/webhook/whatsapp
```

### Para Producción (Servidor Público)

Si tienes un servidor público (AWS, DigitalOcean, etc.):

```bash
# Tu webhook URL será:
# https://tu-dominio.com/webhook/whatsapp
# o
# https://tu-ip:puerto/webhook/whatsapp
```

### Configurar Webhook en Meta

1. Ve a **WhatsApp** → **Configuration** en tu app de Meta
2. En la sección **Webhook**, haz clic en **Edit**
3. Completa:
   - **Callback URL**: `https://tu-url/webhook/whatsapp`
   - **Verify Token**: El mismo que pusiste en `WHATSAPP_WEBHOOK_VERIFY_TOKEN`
4. Haz clic en **Verify and save**
5. Suscríbete a los eventos **messages** marcando la casilla

## 🚀 Ejecutar el Bot

### Verificar Configuración

```bash
# Verifica que todas las variables estén configuradas
python main.py --config
```

Deberías ver algo como:
```
==================================================
🔧 CONFIGURATION STATUS
==================================================
📱 Telegram Bot: ✅ Configured
   Token: **********1234
💬 WhatsApp Bot: ✅ Configured
   Phone Number ID: 123456789012345
   Access Token: **********abcd
   Verify Token: ******24
==================================================
```

### Ejecutar Solo WhatsApp

```bash
# Ejecutar solo el bot de WhatsApp
python main.py --platform whatsapp

# Con configuraciones específicas
python main.py --platform whatsapp --host 0.0.0.0 --port 5000 --debug
```

### Ejecutar Ambos Bots

```bash
# Ejecutar Telegram y WhatsApp simultáneamente
python main.py --platform both
```

### Autodetección

```bash
# El sistema detectará automáticamente qué bots están configurados
python main.py
```

## ✅ Verificación y Pruebas

### 1. Verificar Estado del Webhook

Visita: `http://localhost:5000/whatsapp/status`

Deberías ver:
```json
{
  "status": "active",
  "bot_type": "whatsapp",
  "pending_messages": {...}
}
```

### 2. Probar con Tu Número

1. Desde **otro** número de teléfono (no el registrado como business)
2. Envía un mensaje de WhatsApp al número business
3. Deberías recibir una respuesta automática

### 3. Verificar Logs

```bash
# Los logs mostrarán algo como:
# INFO - 📨 Received WhatsApp webhook: {...}
# INFO - 📱 Processing message from Usuario (573001234567), type: text
# INFO - ✅ Message sent successfully to 573001234567, ID: wamid.xxx
```

## 🔧 Resolución de Problemas

### Error: "Webhook verification failed"

**Causas comunes:**
- ❌ `WHATSAPP_WEBHOOK_VERIFY_TOKEN` no coincide con Meta
- ❌ URL webhook incorrecta
- ❌ Servidor no está ejecutándose

**Soluciones:**
```bash
# 1. Verifica que el token sea exactamente el mismo
echo $WHATSAPP_WEBHOOK_VERIFY_TOKEN

# 2. Verifica que la URL esté accesible
curl -X GET "https://tu-url/webhook/whatsapp?hub.mode=subscribe&hub.verify_token=tu_token&hub.challenge=test"

# 3. Revisa los logs del servidor
python main.py --platform whatsapp --debug
```

### Error: "Access token invalid"

**Causas:**
- ❌ Token expirado (tokens temporales duran 24h)
- ❌ Token copiado incorrectamente
- ❌ Permisos insuficientes

**Soluciones:**
1. Genera un nuevo token en Meta for Developers
2. Para producción, usa tokens permanentes de System User
3. Verifica permisos `whatsapp_business_messaging`

### Error: "Phone number not verified"

**Causas:**
- ❌ Número no verificado en Meta
- ❌ Número ya usado en WhatsApp personal
- ❌ Verificación comercial pendiente

**Soluciones:**
1. Completa el proceso de verificación del número
2. Usa un número diferente, exclusivo para business
3. Espera la verificación comercial de Meta

### Error: "Rate limit exceeded"

**Información:**
- 🚫 WhatsApp limita: 1 mensaje cada 6 segundos por usuario
- 🚫 80 mensajes por segundo global
- 🚫 Límites de conversaciones por día

**El bot maneja esto automáticamente, pero si persiste:**
```bash
# Verifica los logs para rate limiting
grep "Rate limit" logs.txt

# Considera implementar cola de mensajes para alto volumen
```

### Webhook no recibe mensajes

**Checklist:**
1. ✅ Servidor ejecutándose y accesible públicamente
2. ✅ URL webhook correcta en Meta configuración
3. ✅ Token de verificación coincide
4. ✅ Suscrito a eventos "messages"
5. ✅ Mensajes enviados desde número diferente al business

**Debug paso a paso:**
```bash
# 1. Verifica conectividad
curl https://tu-url/whatsapp/status

# 2. Simula webhook
curl -X POST https://tu-url/webhook/whatsapp \
  -H "Content-Type: application/json" \
  -d '{"test": "message"}'

# 3. Revisa logs de Meta
# Ve a WhatsApp > Configuration > Webhook > View logs
```

## 📚 Recursos Adicionales

### Documentación Oficial
- [WhatsApp Business API Docs](https://developers.facebook.com/docs/whatsapp/)
- [Meta for Developers](https://developers.facebook.com/)

### Rate Limits y Mejores Prácticas
- [WhatsApp Rate Limits Guide](https://developers.facebook.com/docs/whatsapp/overview/rate-limits)
- [Best Practices for Authentication](https://developers.facebook.com/docs/whatsapp/business-management-api/authentication-templates/authentication-best-practices/)

### Herramientas de Desarrollo
- [ngrok](https://ngrok.com/) - Túneles para desarrollo local
- [Postman WhatsApp Collection](https://www.postman.com/whatsapp/) - Para probar APIs

## 🆘 Soporte

Si tienes problemas con la configuración:

1. **Revisa los logs**: `python main.py --platform whatsapp --debug`
2. **Verifica configuración**: `python main.py --config`
3. **Consulta documentación**: Los enlaces en "Recursos Adicionales"
4. **Contacta soporte**: Si sigues teniendo problemas, contacta al equipo de desarrollo

---

**¡Listo!** 🎉 Tu bot de WhatsApp debería estar funcionando. Recuerda que para uso en producción necesitarás completar la verificación comercial de Meta y considerar límites de rate limiting y costos asociados.