from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardButton, InlineKeyboardMarkup, InputFile
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ConversationHandler, CallbackContext, CallbackQueryHandler
import logging
import os

# Estados de la conversación
SALUDO, DATOS, MENU, PEDIDO, CONFIRMACION = range(5)

# Configura logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# Simulación de base de datos de usuarios (en memoria)
usuarios = {}

# Mensajes y botones
MENU_PDF_URL = "https://onepizzeria.com/menu.pdf"  # Cambia por el real si lo tienes

# --- Handlers ---
async def start(update: Update, context: CallbackContext) -> int:
    user_id = update.effective_user.id
    if user_id in usuarios:
        nombre = usuarios[user_id]['nombre'].split()[0]
        await update.message.reply_text(f"¡Hola {nombre}, bienvenido de vuelta a ONE PIZZERIA ☺🍕✨!")
        # Simula dirección guardada
        await update.message.reply_text(
            "Tenemos guardada la dirección Calle 123a #45b-67 Torre 8 Apto 901, ¿deseas ordenar a esta misma o una dirección distinta? Si es así, dime a cuál.",
            reply_markup=ReplyKeyboardMarkup([
                [KeyboardButton("Usar dirección guardada")],
                [KeyboardButton("Ingresar nueva dirección")]
            ], one_time_keyboard=True, resize_keyboard=True)
        )
        return MENU
    else:
        await update.message.reply_text(
            "¡Hola y bienvenido a ONE PIZZERIA ☺🍕✨!\nPara comenzar, por favor compártenos tu nombre completo, dirección de entrega, tu teléfono y tu correo. Así podremos agilizar tu orden hoy y en futuras compras."
        )
        return DATOS

async def recibir_datos(update: Update, context: CallbackContext) -> int:
    user_id = update.effective_user.id
    datos = update.message.text
    usuarios[user_id] = {'nombre': datos.split()[0] if datos else 'Cliente', 'datos': datos}
    await update.message.reply_text(f"¡Genial {usuarios[user_id]['nombre']} ☺🍕✨!")
    await update.message.reply_text(
        "Antes de que elijas tus pizzas, aquí tienes algunos detalles importantes:\n" +
        "Elige tus pizzas, combos, postres o bebidas. Indica sabor, tamaño, tipo de masa, borde y queso (si quieres los tradicionales, no hace falta mencionarlo).\n" +
        "Dinos tu método de pago. Recibe tu pedido y disfruta la mejor pizza del mundo mundial.\n¡Además, te enviamos nuestro menú en PDF con todos los productos! También tenemos descuentos disponibles hoy. Échales un vistazo en el PDF o pregúntanos por ellos. Si necesitas saber más sobre ingredientes, adiciones o nuestras sucursales (Bogotá Chicó, Bogotá Cedritos y Chía San Roque), ¡pregunta con confianza!",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("Ver menú PDF", url=MENU_PDF_URL)]
        ])
    )
    await update.message.reply_text("¿Qué te gustaría pedir hoy? Escríbelo o usa el botón de abajo.",
        reply_markup=ReplyKeyboardMarkup([
            [KeyboardButton("Ver menú PDF")],
            [KeyboardButton("Hacer pedido")]
        ], one_time_keyboard=True, resize_keyboard=True)
    )
    return PEDIDO

async def menu_handler(update: Update, context: CallbackContext) -> int:
    await update.message.reply_text(
        "Aquí tienes el menú en PDF:",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("Ver menú PDF", url=MENU_PDF_URL)]
        ])
    )
    await update.message.reply_text("¿Qué te gustaría pedir hoy? Puedes escribirlo o usar el botón de abajo.",
        reply_markup=ReplyKeyboardMarkup([
            [KeyboardButton("Hacer pedido")]
        ], one_time_keyboard=True, resize_keyboard=True)
    )
    return PEDIDO

async def recibir_pedido(update: Update, context: CallbackContext) -> int:
    pedido = update.message.text
    context.user_data['pedido'] = pedido
    await update.message.reply_text(
        f"¡Perfecto! Este es tu pedido provisional:\n{pedido}\n¿Te gustaría agregar o modificar algún producto de tu pedido?",
        reply_markup=ReplyKeyboardMarkup([
            [KeyboardButton("Agregar producto")],
            [KeyboardButton("No, está perfecto")] 
        ], one_time_keyboard=True, resize_keyboard=True)
    )
    return CONFIRMACION

async def confirmacion(update: Update, context: CallbackContext) -> int:
    respuesta = update.message.text
    if "agregar" in respuesta.lower():
        await update.message.reply_text("Por favor, dime qué producto deseas agregar.")
        return PEDIDO
    else:
        await update.message.reply_text("¡Genial! Ahora, ¿cómo deseas pagar? Elige una opción:",
            reply_markup=ReplyKeyboardMarkup([
                [KeyboardButton("Efectivo")],
                [KeyboardButton("Datáfono (tarjeta)")]
            ], one_time_keyboard=True, resize_keyboard=True)
        )
        await update.message.reply_text("¡Gracias por tu pedido! Pronto te contactaremos para confirmar la entrega. Si tienes dudas, ¡escríbenos! 😊🍕")
        return ConversationHandler.END

async def cancelar(update: Update, context: CallbackContext) -> int:
    await update.message.reply_text("Conversación cancelada. ¡Esperamos verte pronto en ONE PIZZERIA! 🍕")
    return ConversationHandler.END

# --- Main ---
def main():
    TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
    if not TOKEN:
        print("Por favor, define la variable de entorno TELEGRAM_BOT_TOKEN.")
        return
    app = ApplicationBuilder().token(TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            SALUDO: [MessageHandler(filters.TEXT & ~filters.COMMAND, start)],
            DATOS: [MessageHandler(filters.TEXT & ~filters.COMMAND, recibir_datos)],
            MENU: [MessageHandler(filters.Regex(".*(menú|menu|ver menú|ver menu|dirección|direccion|Usar dirección guardada|Ingresar nueva dirección).*"), menu_handler)],
            PEDIDO: [MessageHandler(filters.TEXT & ~filters.COMMAND, recibir_pedido)],
            CONFIRMACION: [MessageHandler(filters.TEXT & ~filters.COMMAND, confirmacion)],
        },
        fallbacks=[CommandHandler('cancel', cancelar)]
    )
    app.add_handler(conv_handler)
    print("Bot iniciado. Esperando mensajes...")
    app.run_polling()

if __name__ == "__main__":
    main()
