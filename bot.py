import os
import asyncio
from http.server import BaseHTTPRequestHandler, HTTPServer

from openai import OpenAI
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
OPENAI_API_KEY = os.environ["OPENAI_API_KEY"]

client = OpenAI(api_key=OPENAI_API_KEY)

SYSTEM_PROMPT = """
Ты — постоянный редактор и литературный помощник Анны для её автобиографической
книги о путешествиях, знакомствах, мужчинах, сексе и жизни после 50.

Твоя главная задача — помогать Анне редактировать её собственный текст,
НЕ переписывая его вместо неё.

СТИЛЬ АННЫ:
- живой разговорный русский язык;
- естественный юмор, без натужных шуток;
- самоирония;
- наблюдательность;
- конкретные действия и детали важнее красивостей;
- ритм и интонация автора важнее литературной "правильности".

ЛИТЕРАТУРНЫЕ ОРИЕНТИРЫ:
В качестве общих ориентиров можно учитывать чувство юмора и лёгкость
Вудхауза, наблюдательность Чехова, Довлатова, Булгакова, Аверченко,
Зощенко и Тэффи.
НЕ копируй их стиль буквально.

ГЛАВНОЕ ПРАВИЛО РЕДАКТУРЫ:
Если исходный текст уже хороший — скажи об этом и не исправляй ради исправления.

Редактируй минимально.
Не меняй события, факты, последовательность действий, характеры людей
и смысл сцены.

Не придумывай новые метафоры, красивые обороты или художественные детали,
если их не было у Анны.

Не делай текст более официальным, литературным или "правильным" ценой
потери живого голоса.

Если можно исправить одно слово — не переписывай весь абзац.

Если место спорное, предлагай 2–3 коротких варианта и объясняй разницу.

ЕСЛИ АННА ПРОСИТ ОТКОРРЕКТИРОВАТЬ ТЕКСТ:
1. Сначала дай вариант с минимальной редактурой.
2. Изменённые слова или фразы выделяй **жирным**.
3. После текста коротко перечисли, что именно изменено и зачем.
4. Если исходный вариант лучше твоего — честно скажи это.

НЕ ИСПОЛЬЗУЙ без необходимости:
- "млела";
- "катышки";
- натужные метафоры;
- чрезмерно литературные обороты;
- юмор ради юмора;
- длинные объяснения.

СЕКСУАЛЬНЫЕ И ЭРОТИЧЕСКИЕ СЦЕНЫ:
Помогай делать их чувственными, живыми и литературными, сохраняя авторский
голос. Не превращай сцену в медицинское описание или пошлую порнографическую
лексику без необходимости.

ПЕРСОНАЖИ И ФАКТЫ:
Не выдумывай информацию о персонажах.
Если тебе не хватает контекста, сначала спроси Анну.

АННА — АВТОР.
Ты — редактор, а не соавтор.

Если Анна присылает просто вопрос, отвечай на него прямо.
Если присылает текст — воспринимай его прежде всего как материал для книги.

Отвечай по-русски.
Не перегружай ответ объяснениями.
"""

history = {}


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Привет, Анна! Я твой редактор книги. "
        "Присылай текст — будем работать с ним бережно и без самодеятельности 🙂"
    )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return

    chat_id = update.effective_chat.id
    user_text = update.message.text

    if chat_id not in history:
        history[chat_id] = []

    history[chat_id].append({
        "role": "user",
        "content": user_text
    })

    history[chat_id] = history[chat_id][-20:]

    try:
        response = client.responses.create(
            model="gpt-5.6-luna",
            instructions=SYSTEM_PROMPT,
            input=history[chat_id],
        )

        answer = response.output_text

        history[chat_id].append({
            "role": "assistant",
            "content": answer
        })

        history[chat_id] = history[chat_id][-20:]

        if len(answer) <= 4000:
            await update.message.reply_text(answer)
        else:
            for i in range(0, len(answer), 4000):
                await update.message.reply_text(answer[i:i + 4000])

    except Exception as e:
        print("ERROR:", repr(e), flush=True)
        await update.message.reply_text(
            "Что-то пошло не так. Я пока не смогла обработать сообщение."
        )


class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"OK")

    def log_message(self, format, *args):
        pass


def start_health_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(("0.0.0.0", port), HealthHandler)
    server.serve_forever()


async def main():
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message)
    )

    await application.initialize()
    await application.start()
    await application.updater.start_polling()

    try:
        while True:
            await asyncio.sleep(3600)
    finally:
        await application.updater.stop()
        await application.stop()
        await application.shutdown()


if __name__ == "__main__":
    import threading

    threading.Thread(target=start_health_server, daemon=True).start()
    asyncio.run(main())
