import os
import random
from datetime import datetime
from aiohttp import web
import barcode
from barcode.writer import ImageWriter
from fpdf import FPDF
from faker import Faker

from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, FSInputFile, ReplyKeyboardMarkup, KeyboardButton
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

TOKEN = "9294177492:AAFRGYyUXwj6J3d7BqWIISfW0eJZ0hmWTp8"

bot = Bot(token=TOKEN)
dp = Dispatcher(storage=MemoryStorage())
fake = Faker('it_IT')

OUTPUT_DIR = "output_files"
os.makedirs(OUTPUT_DIR, exist_ok=True)

class FormPrescrizione(StatesGroup):
    inserimento_medico = State()
    inserimento_farmaco = State()

def genera_barcode_code39(valore: str, nome_file_output: str) -> str:
    valore_pulito = "".join(c for c in valore.upper() if c.isalnum() or c in " -.")
    code39_class = barcode.get_barcode_class('code39')
    my_barcode = code39_class(valore_pulito, writer=ImageWriter(), add_checksum=False)
    return my_barcode.save(os.path.join(OUTPUT_DIR, nome_file_output))

@dp.message(Command("start"))
async def cmd_start(message: Message):
    kb = [[KeyboardButton(text="🩺 Crea Prescrizione Personalizzata")]]
    await message.answer(
        "🤖 **Bot Pronto!**\nClicca sul pulsante per inserire qualsiasi medico e farmaco tu voglia.",
        reply_markup=ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True),
        parse_mode="Markdown"
    )

@dp.message(F.text == "🩺 Crea Prescrizione Personalizzata")
async def avvia_creazione(message: Message, state: FSMContext):
    await state.set_state(FormPrescrizione.inserimento_medico)
    await message.answer(
        "1️⃣ **Inserisci i dati del medico:**\nScrivi in questo formato con la stanghetta `|`:\n\n"
        "Titolo Nome Cognome | Specializzazione | Indirizzo | Città CAP (Prov) | Telefono\n\n"
        "_Esempio:_\nDr. Mario Rossi | Cardiologia | Via Roma 10 | Foggia 71121 (FG) | 3331234567",
        parse_mode="Markdown"
    )

@dp.message(FormPrescrizione.inserimento_medico)
async def ricevi_medico(message: Message, state: FSMContext):
    parti = [p.strip() for p in message.text.split("|")]
    if len(parti) < 5:
        await message.answer("❌ Formato non valido. Assicurati di separare i campi con la stanghetta `|`. Riprova:")
        return
    
    medico_obj = {
        "stringa_medico": f"{parti[0]}\n{parti[1]}\n{parti[2]}\n{parti[3]}\nTel. {parti[4]}"
    }
    await state.update_data(medico=medico_obj)
    await state.set_state(FormPrescrizione.inserimento_farmaco)
    await message.answer("2️⃣ **Inserisci il nome del farmaco e il codice AIC:**\n_(Es. XANAX | 025980059)_")

@dp.message(FormPrescrizione.inserimento_farmaco)
async def ricevi_farmaco(message: Message, state: FSMContext):
    dati = await state.get_data()
    medico = dati["medico"]
    
    parts_farmaco = [p.strip() for p in message.text.split("|")]
    nome_farmaco = parts_farmaco[0]
    aic_farmaco = parts_farmaco[1] if len(parts_farmaco) > 1 else "025980059"
    
    await state.clear()
    
    assistito = f"{fake.first_name().upper()} {fake.last_name().upper()}"
    cf = fake.ssn().upper()
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    bc_assistito = genera_barcode_code39(assistito, f"bc_as_{timestamp}")
    bc_aic = genera_barcode_code39(aic_farmaco, f"bc_aic_{timestamp}")
    
    pdf_path = os.path.join(OUTPUT_DIR, f"Prescrizione_{timestamp}.pdf")
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 11)
    
    for riga in medico["stringa_medico"].split("\n"):
        pdf.cell(0, 6, riga, ln=True)
        
    pdf.ln(8)
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(0, 6, f"Assistito: {assistito} (CF: {cf})", ln=True)
    pdf.image(bc_assistito, w=70, h=18)
    pdf.ln(5)
    pdf.cell(0, 6, f"Farmaco: {nome_farmaco} | AIC: {aic_farmaco}", ln=True)
    pdf.image(bc_aic, w=60, h=18)
    pdf.output(pdf_path)
    
    await message.answer_document(FSInputFile(pdf_path), caption="📑 Ecco il documento generato con il medico personalizzato e i Barcode Code 39!")

# --- SERVER WEB PER RENDER ---
async def handle(request):
    return web.Response(text="Bot is running!")

async def main():
    app = web.Application()
    app.router.add_get("/", handle)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 10000))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    
    await dp.start_polling(bot)

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
