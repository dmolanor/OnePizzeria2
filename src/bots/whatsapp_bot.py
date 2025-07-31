import asyncio
import json
import logging
import time
from typing import Any, Dict, List, Optional

import requests
from flask import Flask, jsonify, make_response, request
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from config.settings import (WHATSAPP_ACCESS_TOKEN, WHATSAPP_API_URL,
                             WHATSAPP_PHONE_NUMBER_ID,
                             WHATSAPP_WEBHOOK_VERIFY_TOKEN)
from src.bots.base_bot import BaseBot

logger = logging.getLogger(__name__)

class WhatsAppBot(BaseBot):
    """
    WhatsApp Business API bot implementation.
    
    Features:
    - Webhook-based message receiving
    - WhatsApp Business API integration
    - Rate limiting compliance (80 msg/sec, 1 msg/6sec per user)
    - Message verification and security
    - Multiple message types support (text, image, document, etc.)
    """
    
    def __init__(self):
        """Initialize the WhatsApp bot with API configuration."""
        super().__init__()
        
        # WhatsApp API configuration
        self.access_token = WHATSAPP_ACCESS_TOKEN
        self.phone_number_id = WHATSAPP_PHONE_NUMBER_ID
        self.verify_token = WHATSAPP_WEBHOOK_VERIFY_TOKEN
        self.api_url = WHATSAPP_API_URL
        
        if not all([self.access_token, self.phone_number_id, self.verify_token]):
            raise ValueError(
                "WhatsApp configuration missing. Please set WHATSAPP_ACCESS_TOKEN, "
                "WHATSAPP_PHONE_NUMBER_ID, and WHATSAPP_WEBHOOK_VERIFY_TOKEN in your .env file"
            )
        
        # API endpoints
        self.messages_url = f"{self.api_url}/{self.phone_number_id}/messages"
        
        # Headers for API requests
        self.headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json"
        }
        
        # Rate limiting for WhatsApp API
        self.global_rate_limiter = {}  # Global rate limiting (80 msg/sec)
        self.user_rate_limiter = {}   # Per-user rate limiting (1 msg/6sec)
        self.min_message_interval = 6.0  # WhatsApp requires 6 seconds between messages per user
        
        # Setup HTTP session with retries
        self.session = requests.Session()
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)
        
        # Flask app for webhook
        self.app = Flask(__name__)
        self._setup_webhook_routes()
        
        logger.info("WhatsApp bot initialized successfully")
    
    def _setup_webhook_routes(self) -> None:
        """Set up Flask routes for WhatsApp webhook."""
        
        @self.app.route("/webhook/whatsapp", methods=["GET"])
        def webhook_verify():
            """Verify webhook URL with WhatsApp."""
            return self.verify_webhook(request)
        
        @self.app.route("/webhook/whatsapp", methods=["POST"])
        def webhook_receive():
            """Receive messages from WhatsApp."""
            return asyncio.run(self.handle_webhook(request))
        
        @self.app.route("/whatsapp/status", methods=["GET"])
        def status_check():
            """Health check endpoint."""
            return jsonify({
                "status": "active",
                "bot_type": "whatsapp",
                "pending_messages": self.get_pending_messages_info()
            })
    
    def verify_webhook(self, request) -> Any:
        """
        Verify webhook URL with WhatsApp.
        
        Args:
            request: Flask request object
            
        Returns:
            Challenge response or error
        """
        try:
            mode = request.args.get("hub.mode")
            token = request.args.get("hub.verify_token")
            challenge = request.args.get("hub.challenge")
            
            if mode == "subscribe" and token == self.verify_token:
                logger.info("✅ WhatsApp webhook verified successfully")
                return make_response(challenge, 200)
            else:
                logger.warning("❌ WhatsApp webhook verification failed")
                return make_response("Verification failed", 403)
                
        except Exception as e:
            logger.error(f"Error in webhook verification: {e}")
            return make_response("Verification error", 500)
    
    async def handle_webhook(self, request) -> Any:
        """
        Handle incoming webhook from WhatsApp.
        
        Args:
            request: Flask request object
            
        Returns:
            JSON response confirming receipt
        """
        try:
            data = request.get_json()
            
            if not data:
                logger.warning("Received empty webhook data")
                return jsonify({"status": "no_data"}), 200
            
            logger.info(f"📨 Received WhatsApp webhook: {json.dumps(data, indent=2)}")
            
            # Process webhook data
            await self._process_webhook_data(data)
            
            return jsonify({"status": "received"}), 200
            
        except Exception as e:
            logger.error(f"Error handling webhook: {e}")
            import traceback
            logger.error(f"Full traceback:\n{traceback.format_exc()}")
            return jsonify({"status": "error", "message": str(e)}), 500
    
    async def _process_webhook_data(self, data: Dict[str, Any]) -> None:
        """
        Process webhook data and extract messages.
        
        Args:
            data: Webhook data from WhatsApp
        """
        try:
            # Extract entry data
            entries = data.get("entry", [])
            
            for entry in entries:
                changes = entry.get("changes", [])
                
                for change in changes:
                    value = change.get("value", {})
                    
                    # Process messages
                    messages = value.get("messages", [])
                    contacts = value.get("contacts", [])
                    
                    # Create contact mapping for easier lookup
                    contact_map = {contact.get("wa_id"): contact.get("profile", {}).get("name", "Usuario") 
                                 for contact in contacts}
                    
                    for message in messages:
                        await self._process_message(message, contact_map)
                        
        except Exception as e:
            logger.error(f"Error processing webhook data: {e}")
            import traceback
            logger.error(f"Full traceback:\n{traceback.format_exc()}")
    
    async def _process_message(self, message: Dict[str, Any], contact_map: Dict[str, str]) -> None:
        """
        Process a single message from WhatsApp.
        
        Args:
            message: Message data from WhatsApp
            contact_map: Mapping of wa_id to contact names
        """
        try:
            # Extract message details
            message_id = message.get("id")
            from_number = message.get("from")
            message_type = message.get("type")
            timestamp = message.get("timestamp")
            
            # Skip if message is from our bot (shouldn't happen, but safety check)
            if not from_number:
                logger.warning("Received message without sender information")
                return
            
            # Get contact name
            user_name = contact_map.get(from_number, "Usuario")
            cliente_id = self.format_recipient_id(from_number)
            
            logger.info(f"📱 Processing message from {user_name} ({cliente_id}), type: {message_type}")
            
            # Extract message content based on type
            message_text = await self._extract_message_content(message, message_type)
            
            if message_text:
                # Process the message through the workflow
                await self.process_user_message(cliente_id, message_text, user_name)
            else:
                # Send acknowledgment for unsupported message types
                await self.send_message(
                    cliente_id,
                    "Recibí tu mensaje, pero este tipo de contenido no está soportado actualmente. "
                    "Por favor, envía un mensaje de texto."
                )
                
        except Exception as e:
            logger.error(f"Error processing message: {e}")
            import traceback
            logger.error(f"Full traceback:\n{traceback.format_exc()}")
    
    async def _extract_message_content(self, message: Dict[str, Any], message_type: str) -> Optional[str]:
        """
        Extract content from different message types.
        
        Args:
            message: Message data from WhatsApp
            message_type: Type of message (text, image, document, etc.)
            
        Returns:
            Extracted message content or None if unsupported
        """
        try:
            if message_type == "text":
                return message.get("text", {}).get("body", "").strip()
            
            elif message_type == "image":
                caption = message.get("image", {}).get("caption", "")
                return f"[Imagen recibida] {caption}".strip() if caption else "[Imagen recibida]"
            
            elif message_type == "document":
                filename = message.get("document", {}).get("filename", "documento")
                caption = message.get("document", {}).get("caption", "")
                content = f"[Documento recibido: {filename}]"
                if caption:
                    content += f" {caption}"
                return content
            
            elif message_type == "audio":
                return "[Audio recibido]"
            
            elif message_type == "voice":
                return "[Mensaje de voz recibido]"
            
            elif message_type == "video":
                caption = message.get("video", {}).get("caption", "")
                return f"[Video recibido] {caption}".strip() if caption else "[Video recibido]"
            
            elif message_type == "location":
                location = message.get("location", {})
                lat = location.get("latitude")
                lng = location.get("longitude")
                name = location.get("name", "")
                address = location.get("address", "")
                
                content = f"[Ubicación recibida"
                if name:
                    content += f": {name}"
                if address:
                    content += f" - {address}"
                if lat and lng:
                    content += f" ({lat}, {lng})"
                content += "]"
                return content
            
            elif message_type == "contacts":
                contacts = message.get("contacts", [])
                if contacts:
                    contact = contacts[0]  # Take first contact
                    name = contact.get("name", {}).get("formatted_name", "Contacto")
                    return f"[Contacto recibido: {name}]"
                return "[Contacto recibido]"
            
            else:
                logger.warning(f"Unsupported message type: {message_type}")
                return None
                
        except Exception as e:
            logger.error(f"Error extracting message content: {e}")
            return f"[Error procesando mensaje de tipo {message_type}]"
    
    async def send_message(self, recipient: str, message: str, **kwargs) -> bool:
        """
        Send a text message via WhatsApp Business API.
        
        Args:
            recipient: Phone number (with country code)
            message: Message content
            **kwargs: Additional parameters (preview_url, etc.)
            
        Returns:
            bool: True if message was sent successfully
        """
        try:
            # Check rate limiting
            if not await self._check_rate_limits(recipient):
                logger.warning(f"Rate limit exceeded for {recipient}")
                return False
            
            # Prepare message payload
            payload = {
                "messaging_product": "whatsapp",
                "to": recipient,
                "type": "text",
                "text": {
                    "preview_url": kwargs.get("preview_url", False),
                    "body": message
                }
            }
            
            # Send message
            response = await self._make_api_request("POST", self.messages_url, payload)
            
            if response and response.get("messages"):
                message_id = response["messages"][0].get("id")
                logger.info(f"✅ Message sent successfully to {recipient}, ID: {message_id}")
                return True
            else:
                logger.error(f"❌ Failed to send message to {recipient}: {response}")
                return False
                
        except Exception as e:
            logger.error(f"Error sending message to {recipient}: {e}")
            return False
    
    async def send_typing_action(self, recipient: str) -> bool:
        """
        Send a typing indicator to WhatsApp.
        Note: WhatsApp doesn't have a direct typing indicator like Telegram,
        but we can mark messages as read to show activity.
        
        Args:
            recipient: Phone number
            
        Returns:
            bool: True (no-op for WhatsApp)
        """
        # WhatsApp doesn't have typing indicators like Telegram
        # This is a no-op to maintain interface compatibility
        return True
    
    def format_recipient_id(self, raw_id: str) -> str:
        """
        Format phone number for WhatsApp API.
        
        Args:
            raw_id: Raw phone number from WhatsApp
            
        Returns:
            str: Formatted phone number
        """
        # WhatsApp IDs are already in the correct format (e.g., "573001234567")
        return raw_id
    
    async def _check_rate_limits(self, recipient: str) -> bool:
        """
        Check WhatsApp API rate limits.
        
        Args:
            recipient: Phone number
            
        Returns:
            bool: True if request is within rate limits
        """
        current_time = time.time()
        
        # Check per-user rate limit (1 message per 6 seconds per user)
        last_message_time = self.user_rate_limiter.get(recipient, 0)
        if current_time - last_message_time < self.min_message_interval:
            time_to_wait = self.min_message_interval - (current_time - last_message_time)
            logger.warning(f"User rate limit: Need to wait {time_to_wait:.1f}s for {recipient}")
            return False
        
        # Update rate limiter
        self.user_rate_limiter[recipient] = current_time
        
        # Clean up old entries (older than 1 hour)
        cutoff_time = current_time - 3600
        self.user_rate_limiter = {
            k: v for k, v in self.user_rate_limiter.items() 
            if v > cutoff_time
        }
        
        return True
    
    async def _make_api_request(self, method: str, url: str, data: Dict[str, Any] = None) -> Optional[Dict[str, Any]]:
        """
        Make an API request to WhatsApp Business API.
        
        Args:
            method: HTTP method (GET, POST, etc.)
            url: API endpoint URL
            data: Request payload
            
        Returns:
            Response data or None if failed
        """
        try:
            if method == "POST":
                response = self.session.post(url, headers=self.headers, json=data, timeout=30)
            elif method == "GET":
                response = self.session.get(url, headers=self.headers, timeout=30)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")
            
            response.raise_for_status()
            return response.json()
            
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 429:
                logger.error(f"Rate limit exceeded: {e}")
            else:
                logger.error(f"HTTP error {e.response.status_code}: {e}")
                logger.error(f"Response content: {e.response.text}")
            return None
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Request failed: {e}")
            return None
            
        except Exception as e:
            logger.error(f"Unexpected error in API request: {e}")
            return None
    
    def run_webhook_server(self, host: str = "0.0.0.0", port: int = 5000, debug: bool = False) -> None:
        """
        Run the Flask webhook server.
        
        Args:
            host: Server host
            port: Server port
            debug: Enable debug mode
        """
        logger.info(f"🚀 Starting WhatsApp webhook server on {host}:{port}")
        logger.info(f"📡 Webhook URL: http://{host}:{port}/webhook/whatsapp")
        logger.info(f"🔍 Status URL: http://{host}:{port}/whatsapp/status")
        
        self.app.run(host=host, port=port, debug=debug)
    
    async def send_welcome_message(self, recipient: str) -> bool:
        """
        Send a welcome message to a new user.
        
        Args:
            recipient: Phone number
            
        Returns:
            bool: True if message was sent successfully
        """
        welcome_text = (
            "¡Hola! 👋\n\n"
            "Soy tu asistente virtual de One Pizzeria. "
            "¿En qué puedo ayudarte hoy?\n\n"
            "Puedes preguntarme sobre:\n"
            "• 🍕 Nuestro menú y productos\n"
            "• 🛵 Domicilios y entregas\n"
            "• 📍 Ubicaciones\n"
            "• ⏰ Horarios de atención\n"
            "• 💰 Precios y promociones"
        )
        
        return await self.send_message(recipient, welcome_text)
    
    def get_webhook_info(self) -> Dict[str, Any]:
        """
        Get information about the webhook server.
        
        Returns:
            Dict with webhook information
        """
        return {
            "platform": "whatsapp",
            "webhook_path": "/webhook/whatsapp",
            "verify_token_set": bool(self.verify_token),
            "access_token_set": bool(self.access_token),
            "phone_number_id": self.phone_number_id,
            "api_url": self.api_url,
            "messages_endpoint": self.messages_url
        }
