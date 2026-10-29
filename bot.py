import os
import re
import json
import random
from datetime import datetime
from aiohttp import web
from fpdf import FPDF

from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, FSInputFile, ReplyKeyboardMarkup, KeyboardButton
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

# Recupero token bot da variabile d'ambiente
bottoken = os.getenv("bottoken")
if not bottoken:
    raise ValueError("❌ ERRORE: La variabile d'ambiente 'bottoken' non è impostata!")

bot = Bot(token=bottoken)
dp = Dispatcher(storage=MemoryStorage())

OUTPUT_DIR = "output_files"
os.makedirs(OUTPUT_DIR, exist_ok=True)

BTC_WALLET = "bc1qr3lkmmwyrenuz2f7menf55yu8kt0ckzxzye2sy"
SECRET_PASS = "laziomerda"
VIP_FILE = "vip_users.json"

def carica_vip() -> set:
    if os.path.exists(VIP_FILE):
        try:
            with open(VIP_FILE, "r") as f:
                return set(json.load(f))
        except Exception:
            return set()
    return set()

def salva_vip(user_id: int):
    vips = carica_vip()
    vips.add(user_id)
    try:
        with open(VIP_FILE, "w") as f:
            json.dump(list(vips), f)
    except Exception:
        pass

VIP_USERS = carica_vip()

# Database Città, Medici e Studi
CITTA_DB = {
    "cerignola": {"nome": "Cerignola", "cap": "71042", "prov": "FG", "medico": "Dott. DOMENICO GIURATO", "via": "Via Don Minzoni 57,", "tel": "338406556"},
    "san severo": {"nome": "San Severo", "cap": "71016", "prov": "FG", "medico": "Dott.ssa LAURA RITA PIA FONTANELLO", "via": "Via Soccorso 185,", "tel": "338406555"},
    "foggia": {"nome": "Foggia", "cap": "71121", "prov": "FG", "medico": "Dott. ANTONIO DIOGUARDI", "via": "Via Dei Carbonari Dauni 40,", "tel": "3395412098"},
    "milano": {"nome": "Milano", "cap": "20121", "prov": "MI", "medico": "Dott.ssa ERIKA SABBATINI", "via": "Via Giuseppe Ripamonti 114,", "tel": "338229055"},
    "roma": {"nome": "Roma", "cap": "00185", "prov": "RM", "medico": "Dott. MARCO VALERIO PROIETTI", "via": "Via Appia Nuova 215,", "tel": "3358901234"}
}

# Database AIFA completo con varianti e codici AIC ufficiali
FARMACI_DB = {
    "DEPALGOS": {
        "nome": "DEPALGOS", 
        "categoria": "oppioidi", 
        "prezzo": 50, 
        "principio": "Ossicodone + Paracetamolo", 
        "varianti": [
            {"label": "5MG/325MG - 28 Compresse", "aic": "037310014", "unita": "Conf.", "qta_str": "28CPR", "dos_str": "5MG/325MG", "rip": "(Non ripetibile)"},
            {"label": "10MG/325MG - 28 Compresse", "aic": "037310026", "unita": "Conf.", "qta_str": "28CPR", "dos_str": "10MG/325MG", "rip": "(Non ripetibile)"},
            {"label": "20MG/325MG - 28 Compresse", "aic": "037310038", "unita": "Conf.", "qta_str": "28CPR", "dos_str": "20MG/325MG", "rip": "(Non ripetibile)"}
        ]
    },
    "RIVOTRIL": {
        "nome": "RIVOTRIL", 
        "categoria": "benzo", 
        "prezzo": 30, 
        "principio": "Clonazepam", 
        "varianti": [
            {"label": "2MG - 20 Compresse", "aic": "023159068", "unita": "Conf.", "dos_str": "20CPR/2MG", "rip": "(Ripetibile)"},
            {"label": "0.5MG - 20 Compresse", "aic": "023159056", "unita": "Conf.", "dos_str": "20CPR/0.5MG", "rip": "(Ripetibile)"},
            {"label": "2.5MG/ML - Gocce 10ML", "aic": "023159031", "unita": "Flac.", "dos_str": "2.5MG/ML", "rip": "(Ripetibile)"}
        ]
    },
    "XANAX": {
        "nome": "XANAX", 
        "categoria": "benzo", 
        "prezzo": 30, 
        "principio": "Alprazolam", 
        "varianti": [
            {"label": "0.25MG - 20 Compresse", "aic": "025980010", "unita": "Conf.", "dos_str": "20CPR/0.25MG", "rip": "(Ripetibile)"},
            {"label": "1MG - 20 Compresse", "aic": "025980034", "unita": "Conf.", "dos_str": "20CPR/1MG", "rip": "(Ripetibile)"},
            {"label": "0.75MG/ML - Gocce 20ML", "aic": "025980059", "unita": "Flac.", "dos_str": "0.75MG/ML", "rip": "(Ripetibile)"}
        ]
    }
}

LEET_MAP = str.maketrans({'4': 'A', '0': 'O', '1': 'I', '3': 'E', '5': 'S', '7': 'T', '8': 'B', '6': 'G', '9': 'G', '2': 'Z'})

def de_leet(p: str) -> str:
    pulita = re.sub(r'[^a-zA-Z0-9]', '', p)
    return pulita.upper().translate(LEET_MAP) if pulita and not pulita.isdigit() else pulita

def analizza_input(testo: str) -> dict:
    testo = testo.strip()
    luogo = "Milano"
    for k in CITTA_DB:
        if k in testo.lower():
            luogo = CITTA_DB[k]["nome"]
            break
    tokens = [de_leet(t) for t in re.sub(r'[|,\-/]', ' ', re.sub(r'\b(nato|nata|nat|il|del|a|in|da|di)\b', ' ', testo, flags=re.IGNORECASE)).split() if t.strip() and not t.isdigit()]
    nome = " ".join([t for t in tokens if t.lower() != luogo.lower()]) or "MARIO ROSSI"
    cf = "RSSMRA80A01F205Z"
    return {"nome_assistito": nome, "luogo_nascita": luogo, "cf_assistito": cf}

# Motore di generazione PDF con coordinate millimetriche immacolate
def crea_pdf(dati: dict, pdf_path: str):
    pdf = FPDF(orientation="P", unit="mm", format="A4")
    pdf.set_auto_page_break(False)
    pdf.add_page()

    # Intestazione Medico
    pdf.set_xy(13.0, 36.0)
    pdf.set_font("Times", "B", 11.5)
    pdf.cell(0, 5.2, dati["nome_medico"], ln=True)
    pdf.set_x(14.5)
    pdf.set_font("Times", "I", 11.5)
    pdf.cell(0, 5.2, dati["spec_medico"], ln=True)
    pdf.set_font("Times", "", 11.5)
    for riga in [dati["via_medico"], dati["cap_citta_medico"], dati["prov_medico"], f"Tel. {dati['tel_medico']}"]:
        pdf.set_x(13.0)
        pdf.cell(0, 5.2, riga, ln=True)

    # Sezione Assistito
    pdf.set_xy(13.0, 99.5)
    pdf.set_font("Times", "B", 12)
    pdf.cell(0, 6, "Assistito", ln=True)
    pdf.set_xy(13.0, 113.0)
    pdf.set_font("Times", "", 12)
    pdf.cell(0, 6, dati["nome_assistito"], ln=True)

    # Codice Fiscale
    pdf.set_xy(13.0, 137.0)
    pdf.set_font("Times", "", 12)
    pdf.cell(0, 6, "Codice Fiscale:", ln=True)
    pdf.set_xy(21.5, 145.0)
    pdf.set_font("Courier", "B", 14)
    pdf.cell(0, 6, dati["cf_assistito"], ln=True)

    # Prescrizione Farmaco
    pdf.set_xy(13.0, 180.5)
    pdf.set_font("Times", "B", 12)
    pdf.cell(0, 6, "Prescrizione:", ln=True)

    pdf.set_font("Times", "", 13)
    pdf.set_xy(84.5, 207.0)
    pdf.cell(0, 6.2, dati["farmaco_riga1"], ln=True)
    pdf.set_xy(83.0, 213.5)
    pdf.cell(0, 6.2, dati["farmaco_riga2"], ln=True)
    pdf.set_xy(89.0, 220.0)
    pdf.cell(0, 6.2, dati["farmaco_riga3"], ln=True)

    # Luogo, Data e Firma
    pdf.set_font("Times", "", 12)
    pdf.set_xy(11.0, 236.5)
    pdf.cell(80, 6, dati["luogo_data"], ln=0)
    pdf.set_xy(132.0, 236.5)
    pdf.cell(40, 6, "Firma", ln=1)
    
    pdf.output(pdf_path)

class Form(StatesGroup):
    paziente = State()
    citta = State()
    farmaco = State()
    scelta = State()
    quantita = State()
    data = State()

@dp.message(F.text.func(lambda t: t and t.strip().lower() == SECRET_PASS))
async def vip(message: Message, state: FSMContext):
    uid = message.from_user.id
    VIP_USERS.add(uid)
    salva_vip(uid)
    await state.clear()
    await message.answer("🔓 **Lifetime Attivato.**", reply_markup=ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="📄 Nuova Pratica")]], resize_keyboard=True))

@dp.message(Command("start"))
async def start(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("⚡ **Bot Operativo.**", reply_markup=ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="📄 Nuova Pratica")]], resize_keyboard=True))

@dp.message(F.text == "📄 Nuova Pratica")
async def step1(message: Message, state: FSMContext):
    await state.set_state(Form.paziente)
    await message.answer("1️⃣ **Inserisci Nome e Dati del Paziente:**")

@dp.message(Form.paziente)
async def step2(message: Message, state: FSMContext):
    info = analizza_input(message.text)
    await state.update_data(**info)
    await state.set_state(Form.citta)
    await message.answer("2️⃣ **Indica la città:**", reply_markup=ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="Milano"), KeyboardButton(text="Foggia"), KeyboardButton(text="Cerignola")], [KeyboardButton(text="San Severo"), KeyboardButton(text="Roma")]], resize_keyboard=True))

@dp.message(Form.citta)
async def step3(message: Message, state: FSMContext):
    c = message.text.strip().lower()
    info = CITTA_DB.get(c, CITTA_DB["milano"])
    await state.update_data(citta_pura=info["nome"], nome_medico=info["medico"], spec_medico="Medicina Generale", via_medico=info["via"], cap_citta_medico=f"{info['cap']} {info['nome']}", prov_medico=f"({info['prov']})", tel_medico=info["tel"])
    await state.set_state(Form.farmaco)
    await message.answer("3️⃣ **Indica il prodotto:**", reply_markup=ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="Rivotril"), KeyboardButton(text="Xanax"), KeyboardButton(text="Depalgos")]], resize_keyboard=True))

@dp.message(Form.farmaco)
async def step4(message: Message, state: FSMContext):
    f_in = message.text.strip().upper()
    k = next((x for x in FARMACI_DB if x in f_in), "RIVOTRIL")
    sch = FARMACI_DB[k]
    await state.update_data(farmaco_nome=sch["nome"], principio=sch["principio"], prezzo=sch["prezzo"], varianti=sch["varianti"])
    await state.set_state(Form.scelta)
    await message.answer("4️⃣ **Seleziona il formato/dosaggio AIFA:**", reply_markup=ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text=v["label"])] for v in sch["varianti"]], resize_keyboard=True))

@dp.message(Form.scelta)
async def step5(message: Message, state: FSMContext):
    txt = message.text.strip().lower()
    dati = await state.get_data()
    var = next((v for v in dati.get("varianti", []) if txt in v["label"].lower()), dati["varianti"][0])
    await state.update_data(var=var)
    await state.set_state(Form.quantita)
    await message.answer("5️⃣ **Indica la quantità:**", reply_markup=ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="1"), KeyboardButton(text="2"), KeyboardButton(text="3")]], resize_keyboard=True))

@dp.message(Form.quantita)
async def step6(message: Message, state: FSMContext):
    qta = "".join(c for c in message.text.strip() if c.isdigit()) or "1"
    dati = await state.get_data()
    var = dati["var"]
    await state.update_data(
        farmaco_riga1=f"N.{qta}{var['unita']} {dati['farmaco_nome']}",
        farmaco_riga2=f"({dati['principio']}) {var.get('qta_str', var['dos_str'])}",
        farmaco_riga3=var["rip"]
    )
    await state.set_state(Form.data)
    citta = dati["citta_pura"]
    await message.answer("6️⃣ **Conferma data:**", reply_markup=ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text=f"{citta}, {datetime.now().strftime('%d/%m/%Y')}")]], resize_keyboard=True))

@dp.message(Form.data)
async def end(message: Message, state: FSMContext):
    dati = await state.get_data()
    uid = message.from_user.id
    await state.clear()

    if uid not in VIP_USERS:
        await message.answer(f"🔒 **Paywall BTC:** `{dati.get('prezzo', 30)}€` al wallet:\n`{BTC_WALLET}`")
        return

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    pdf_path = os.path.join(OUTPUT_DIR, f"DOC_{ts}.pdf")
    crea_pdf({**dati, "luogo_data": message.text.strip()}, pdf_path)
    await message.answer_document(FSInputFile(pdf_path), caption="✅ **Pratica emessa con successo.**", reply_markup=ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="📄 Nuova Pratica")]], resize_keyboard=True))

# Server web integrato aiohttp per mantenere attivo il servizio sui cloud
async def handle(request):
    return web.Response(text="OK")

async def main():
    app = web.Application()
    app.router.add_get("/", handle)
    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, "0.0.0.0", int(os.environ.get("PORT", 10000))).start()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
