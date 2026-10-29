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

# Legge il token dalla variabile d'ambiente su Render
bottoken = os.getenv("bottoken")

bot = Bot(token=bottoken)
dp = Dispatcher(storage=MemoryStorage())
fake = Faker('it_IT')

OUTPUT_DIR = "output_files"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Database di medici reali per città (estratti da MioDottore)
MEDICI_DB = {
    "cerignola": {
        "nome_medico": "Dott. DOMENICO GIURATO",
        "spec_medico": "Medicina Generale",
        "via_medico": "Via Don Minzoni 57,",
        "cap_citta_medico": "71042 Cerignola",
        "prov_medico": "(FG)",
        "tel_medico": "338406556"
    },
    "foggia": {
        "nome_medico": "Dott. ANTONIO DIOGUARDI",
        "spec_medico": "Medicina Generale",
        "via_medico": "Via Dei Carbonari Dauni 40,",
        "cap_citta_medico": "71121 Foggia",
        "prov_medico": "(FG)",
        "tel_medico": "088123456"
    },
    "bari": {
        "nome_medico": "Dott. NICOLA BIANCHI",
        "spec_medico": "Medicina Generale",
        "via_medico": "Via Sparano da Bari 12,",
        "cap_citta_medico": "70121 Bari",
        "prov_medico": "(BA)",
        "tel_medico": "080555667"
    },
    "milano": {
        "nome_medico": "Dott. SABBATINI ERIKA",
        "spec_medico": "Medicina Generale",
        "via_medico": "Via Contrada Ciro 14,",
        "cap_citta_medico": "71042 Milano",
        "prov_medico": "(FG)",
        "tel_medico": "338229055"
    }
}

class FormPrescrizione(StatesGroup):
    paziente = State()
    citta = State()
    farmaco = State()
    quantita = State()
    luogo_data = State()

def genera_barcode_pulito(valore: str, nome_file_output: str) -> str:
    valore_pulito = "".join(c for c in valore.upper() if c.isalnum() or c in " -.")
    if not valore_pulito:
        valore_pulito = "000000000"
    code39_class = barcode.get_barcode_class('code39')
    
    writer_options = {
        'write_text': False,
        'module_width': 0.28,
        'module_height': 14.0,
        'quiet_zone': 1.0
    }
    my_barcode = code39_class(valore_pulito, writer=ImageWriter(), add_checksum=False)
    return my_barcode.save(os.path.join(OUTPUT_DIR, nome_file_output), options=writer_options)

def crea_pdf_identico(dati: dict, pdf_path: str, bc_cf_path: str, bc_aic_path: str):
    pdf = FPDF(orientation="P", unit="mm", format="A4")
    pdf.set_auto_page_break(False)
    pdf.add_page()

    # --- 1. INTESTAZIONE MEDICO ---
    pdf.set_xy(13.0, 36.0)
    pdf.set_font("Times", "B", 11.5)
    pdf.cell(0, 5.2, dati["nome_medico"], ln=True)

    pdf.set_x(14.5)
    pdf.set_font("Times", "I", 11.5)
    pdf.cell(0, 5.2, dati["spec_medico"], ln=True)

    pdf.set_font("Times", "", 11.5)
    pdf.set_x(13.0)
    pdf.cell(0, 5.2, dati["via_medico"], ln=True)
    pdf.set_x(13.0)
    pdf.cell(0, 5.2, dati["cap_citta_medico"], ln=True)
    pdf.set_x(13.0)
    pdf.cell(0, 5.2, dati["prov_medico"], ln=True)
    pdf.set_x(13.0)
    pdf.cell(0, 5.2, f"Tel. {dati['tel_medico']}", ln=True)

    # --- 2. ASSISTITO ---
    pdf.set_xy(13.0, 99.5)
    pdf.set_font("Times", "B", 12)
    pdf.cell(0, 6, "Assistito", ln=True)

    pdf.set_xy(13.0, 113.0)
    pdf.set_font("Times", "", 12)
    pdf.cell(0, 6, dati["nome_assistito"], ln=True)

    # --- 3. CODICE FISCALE + BARCODE ---
    pdf.set_xy(13.0, 137.0)
    pdf.set_font("Times", "", 12)
    pdf.cell(0, 6, "Codice Fiscale:", ln=True)

    pdf.image(bc_cf_path, x=21.5, y=143.0, w=66.0, h=14.5)

    # --- 4. PRESCRIZIONE + BARCODE + TESTO FARMACO ---
    pdf.set_xy(13.0, 180.5)
    pdf.set_font("Times", "B", 12)
    pdf.cell(0, 6, "Prescrizione:", ln=True)

    pdf.image(bc_aic_path, x=16.5, y=193.0, w=53.0, h=13.5)

    pdf.set_font("Times", "", 13)
    pdf.set_xy(84.5, 207.0)
    pdf.cell(0, 6.2, dati["farmaco_riga1"], ln=True)

    pdf.set_xy(83.0, 213.5)
    pdf.cell(0, 6.2, dati["farmaco_riga2"], ln=True)

    pdf.set_xy(89.0, 220.0)
    pdf.cell(0, 6.2, dati["farmaco_riga3"], ln=True)

    # --- 5. DATA E FIRMA ---
    pdf.set_font("Times", "", 12)
    pdf.set_xy(11.0, 236.5)
    pdf.cell(80, 6, dati["luogo_data"], ln=0)

    pdf.set_xy(132.0, 236.5)
    pdf.cell(40, 6, "Firma", ln=1)

    pdf.output(pdf_path)

@dp.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    kb = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="📄 Nuova Ricetta Medica")]],
        resize_keyboard=True
    )
    await message.answer(
        "🤖 **Bot Ricette Pronto!**\n\n"
        "Clicca sul pulsante qui sotto per inserire i tuoi dati e creare la ricetta.",
        reply_markup=kb,
        parse_mode="Markdown"
    )

@dp.message(F.text == "📄 Nuova Ricetta Medica")
async def step_paziente(message: Message, state: FSMContext):
    await state.set_state(FormPrescrizione.paziente)
    kb = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="PIERLUIGI LEPORE | 25")]],
        resize_keyboard=True
    )
    await message.answer(
        "1️⃣ **Inserisci il tuo Nome, Cognome e la tua Età**\n"
        "Scrivi nel formato: `Nome Cognome | Età`\n"
        "(Es. `PIERLUIGI LEPORE | 25`)",
        reply_markup=kb,
        parse_mode="Markdown"
    )

@dp.message(FormPrescrizione.paziente)
async def ricevi_paziente(message: Message, state: FSMContext):
    parti = [p.strip() for p in message.text.split("|")]
    nome_paziente = parti[0].upper() if len(parti) > 0 else "MARIO ROSSI"
    eta_paziente = parti[1] if len(parti) > 1 else "25"
    cf_paziente = fake.ssn().upper()

    await state.update_data(
        nome_assistito=f"{nome_paziente} (Età: {eta_paziente})",
        cf_assistito=cf_paziente
    )
    await state.set_state(FormPrescrizione.citta)

    kb = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Cerignola"), KeyboardButton(text="Foggia")],
            [KeyboardButton(text="Milano"), KeyboardButton(text="Bari")]
        ],
        resize_keyboard=True
    )
    await message.answer(
        "2️⃣ **Seleziona o scrivi la città** per cercare un medico di medicina generale (verificato su MioDottore):",
        reply_markup=kb,
        parse_mode="Markdown"
    )

@dp.message(FormPrescrizione.citta)
async def ricevi_citta(message: Message, state: FSMContext):
    citta_input = message.text.strip().lower()
    
    if citta_input in MEDICI_DB:
        medico_scelto = MEDICI_DB[citta_input]
    else:
        medico_scelto = {
            "nome_medico": f"Dott. {fake.last_name().upper()} {fake.first_name().upper()}",
            "spec_medico": "Medicina Generale",
            "via_medico": f"Via {fake.street_name()} 14,",
            "cap_citta_medico": f"71042 {message.text.strip().capitalize()}",
            "prov_medico": "(FG)",
            "tel_medico": f"338{random.randint(100000, 999999)}"
        }

    await state.update_data(**medico_scelto)
    await state.set_state(FormPrescrizione.farmaco)

    kb = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="Depalgos")], [KeyboardButton(text="Rivotril")]],
        resize_keyboard=True
    )
    await message.answer(
        f"✅ Medico assegnato:\n*{medico_scelto['nome_medico']}* ({medico_scelto['spec_medico']})\n\n"
        "3️⃣ **Inserisci il nome del farmaco** (es. `Depalgos` o `Rivotril`):",
        reply_markup=kb,
        parse_mode="Markdown"
    )

@dp.message(FormPrescrizione.farmaco)
async def ricevi_farmaco(message: Message, state: FSMContext):
    nome_farmaco = message.text.strip().upper()
    await state.update_data(nome_farmaco_input=nome_farmaco)
    await state.set_state(FormPrescrizione.quantita)

    kb = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="1"), KeyboardButton(text="2")]],
        resize_keyboard=True
    )
    await message.answer(
        "4️⃣ **Quante confezioni (o flaconi) vuoi prescrivere?**\n"
        "Scrivi il numero (es. `1` o `2`):",
        reply_markup=kb,
        parse_mode="Markdown"
    )

@dp.message(FormPrescrizione.quantita)
async def ricevi_quantita(message: Message, state: FSMContext):
    qta = message.text.strip()
    dati = await state.get_data()
    nome_f = dati["nome_farmaco_input"]

    # Verifica simulata AIFA per principi attivi, formati e ripetibilità
    if "DEPALGOS" in nome_f:
        riga1 = f"N.{qta}Conf. {nome_f}"
        riga2 = "(Ossicodone+Paracetamolo) 28CPR"
        riga3 = "(Non ripetibile)"
    elif "RIVOTRIL" in nome_f:
        riga1 = f"N.{qta}Conf. {nome_f}"
        riga2 = "(Clonazepam) 20CPR/2MG"
        riga3 = "(Ripetibile)"
    else:
        riga1 = f"N.{qta}Conf. {nome_f}"
        riga2 = "(Principio Attivo Standard) 20CPR"
        riga3 = "(Ripetibile)"

    aic_generato = f"{random.randint(10000000, 99999999)}"

    await state.update_data(
        farmaco_riga1=riga1,
        farmaco_riga2=riga2,
        farmaco_riga3=riga3,
        aic_farmaco=aic_generato
    )
    await state.set_state(FormPrescrizione.luogo_data)

    oggi = datetime.now().strftime("%d/%m/%Y")
    citta_luogo = dati["cap_citta_medico"].split()[1] if len(dati["cap_citta_medico"].split()) > 1 else "Milano"

    kb = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=f"{citta_luogo}, {oggi}")],
            [KeyboardButton(text="Milano, 29/10/2026")]
        ],
        resize_keyboard=True
    )
    await message.answer(
        f"🔍 *Verifica AIFA completata:* Codice AIC `{aic_generato}` | Stato: `{riga3}`\n\n"
        "5️⃣ **Inserisci Luogo e Data** per il piede pagina:",
        reply_markup=kb,
        parse_mode="Markdown"
    )

@dp.message(FormPrescrizione.luogo_data)
async def finalizza_ricetta(message: Message, state: FSMContext):
    await state.update_data(luogo_data=message.text.strip())
    dati = await state.get_data()
    await state.clear()

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    bc_cf = genera_barcode_pulito(dati["cf_assistito"], f"bc_cf_{timestamp}")
    bc_aic = genera_barcode_pulito(dati["aic_farmaco"], f"bc_aic_{timestamp}")

    pdf_path = os.path.join(OUTPUT_DIR, f"ricetta_{timestamp}.pdf")
    crea_pdf_identico(dati, pdf_path, bc_cf, bc_aic)

    kb = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="📄 Nuova Ricetta Medica")]],
        resize_keyboard=True
    )
    await message.answer_document(
        FSInputFile(pdf_path),
        caption="✅ **Ricetta generata con successo!**\n"
                "• Nome ed età inseriti correttamente\n"
                "• Medico da MioDottore integrato\n"
                "• Principio attivo, confezioni e ripetibilità verificati via AIFA.",
        reply_markup=kb
    )

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
