import os
import re
import json
import random
import difflib
import asyncio
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

# Configurazione Accessi e Monetizzazione
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

# ==============================================================================
# 1. DATABASE INTERNO
# ==============================================================================
CITTA_DB = {
    "cerignola": {
        "nome": "Cerignola", "cap": "71042", "prov": "FG", "catastale": "C514",
        "medici": [
            {"nome": "Dott. DOMENICO GIURATO", "via": "Via Don Minzoni 57,", "tel": "338406556"},
            {"nome": "Dott. FRANCESCO SAVERIO SPECCHIO", "via": "Corso Aldo Moro 112,", "tel": "0885421890"}
        ]
    },
    "san severo": {
        "nome": "San Severo", "cap": "71016", "prov": "FG", "catastale": "I158",
        "medici": [
            {"nome": "Dott.ssa LAURA RITA PIA FONTANELLO", "via": "Via Soccorso 185,", "tel": "338406555"},
            {"nome": "Dott. MATTEO PRATTICHIZZO", "via": "Via Tiberio Solis 45,", "tel": "0882331422"}
        ]
    },
    "foggia": {
        "nome": "Foggia", "cap": "71121", "prov": "FG", "catastale": "D643",
        "medici": [
            {"nome": "Dott. ANTONIO DIOGUARDI", "via": "Via Dei Carbonari Dauni 40,", "tel": "3395412098"},
            {"nome": "Dott.ssa MARIA TERESA LOPORCHIO", "via": "Viale Ofanto 198,", "tel": "0881723411"}
        ]
    },
    "lucera": {
        "nome": "Lucera", "cap": "71036", "prov": "FG", "catastale": "E716",
        "medici": [
            {"nome": "Dott. GIUSEPPE DE LUCA", "via": "Via Gramsci 22,", "tel": "3478891234"}
        ]
    },
    "bari": {
        "nome": "Bari", "cap": "70121", "prov": "BA", "catastale": "A662",
        "medici": [
            {"nome": "Dott. NICOLA BIANCHI", "via": "Via Sparano da Bari 12,", "tel": "3409182736"},
            {"nome": "Dott.ssa ROSA CONTE", "via": "Corso Vittorio Emanuele 88,", "tel": "0805214390"}
        ]
    },
    "taranto": {
        "nome": "Taranto", "cap": "74121", "prov": "TA", "catastale": "L049",
        "medici": [
            {"nome": "Dott. COSIMO DAMIANO RIZZO", "via": "Via Di Palma 74,", "tel": "3336789120"}
        ]
    },
    "milano": {
        "nome": "Milano", "cap": "20121", "prov": "MI", "catastale": "F205",
        "medici": [
            {"nome": "Dott.ssa ERIKA SABBATINI", "via": "Via Giuseppe Ripamonti 114,", "tel": "338229055"},
            {"nome": "Dott. ALESSANDRO COLOMBO", "via": "Corso Buenos Aires 42,", "tel": "026748392"}
        ]
    },
    "roma": {
        "nome": "Roma", "cap": "00185", "prov": "RM", "catastale": "H501",
        "medici": [
            {"nome": "Dott. MARCO VALERIO PROIETTI", "via": "Via Appia Nuova 215,", "tel": "3358901234"}
        ]
    },
    "napoli": {
        "nome": "Napoli", "cap": "80121", "prov": "NA", "catastale": "F839",
        "medici": [
            {"nome": "Dott. GENNARO ESPOSITO", "via": "Via Toledo 156,", "tel": "3389012345"}
        ]
    },
    "torino": {
        "nome": "Torino", "cap": "10121", "prov": "TO", "catastale": "L219",
        "medici": [
            {"nome": "Dott. EDOARDO FERRERO", "via": "Corso Francia 90,", "tel": "3487654321"}
        ]
    },
    "bologna": {
        "nome": "Bologna", "cap": "40121", "prov": "BO", "catastale": "A944",
        "medici": [
            {"nome": "Dott.ssa CHIARA RIGHI", "via": "Via Indipendenza 54,", "tel": "3391122334"}
        ]
    }
}

CATASTALI_EXTRA = {
    "brasile": "Z602", "romania": "Z129", "albania": "Z100", "marocco": "Z330",
    "svizzera": "Z133", "germania": "Z112", "francia": "Z110", "spagna": "Z131",
    "udine": "L483", "manduria": "E882", "francavilla fontana": "D761",
    "lecce": "E506", "brindisi": "B180", "firenze": "D612", "palermo": "G273",
    "genova": "D969", "venezia": "L736", "verona": "L781", "pescara": "G482",
    "barletta": "A669", "andria": "A285", "trani": "L328", "manfredonia": "E885"
}

FARMACI_DB = {
    "DEPALGOS": {
        "nome": "DEPALGOS", "categoria": "oppioidi", "prezzo": 50, "principio": "Ossicodone+Paracetamolo", "layout": "long",
        "varianti": [
            {"label": "5MG/325MG - 28 Compresse", "aic": "037310014", "unita": "Conf.", "qta_str": "28CPR", "dos_str": "5MG/325MG", "rip": "(Non ripetibile)"},
            {"label": "10MG/325MG - 28 Compresse", "aic": "037310026", "unita": "Conf.", "qta_str": "10MG/325MG", "rip": "(Non ripetibile)"},
            {"label": "20MG/325MG - 28 Compresse", "aic": "037310038", "unita": "Conf.", "qta_str": "20MG/325MG", "rip": "(Non ripetibile)"}
        ]
    },
    "TARGIN": {
        "nome": "TARGIN", "categoria": "oppioidi", "prezzo": 50, "principio": "Ossicodone+Naloxone", "layout": "long",
        "varianti": [
            {"label": "5MG/2.5MG - 28 Compresse", "aic": "039405018", "unita": "Conf.", "qta_str": "5MG/2.5MG", "rip": "(Non ripetibile)"},
            {"label": "10MG/5MG - 28 Compresse", "aic": "039405057", "unita": "Conf.", "qta_str": "10MG/5MG", "rip": "(Non ripetibile)"},
            {"label": "20MG/10MG - 28 Compresse", "aic": "039405095", "unita": "Conf.", "qta_str": "20MG/10MG", "rip": "(Non ripetibile)"}
        ]
    },
    "CONTRAMAL": {
        "nome": "CONTRAMAL", "categoria": "oppioidi", "prezzo": 50, "principio": "Tramadolo", "layout": "short",
        "varianti": [
            {"label": "50MG - 20 Capsule", "aic": "028853013", "unita": "Conf.", "dos_str": "20CPS/50MG", "rip": "(Non ripetibile)"},
            {"label": "100MG - 20 Compresse SR", "aic": "028853076", "unita": "Conf.", "dos_str": "20CPR/100MG", "rip": "(Non ripetibile)"},
            {"label": "100MG/ML - Gocce 10ML", "aic": "028853049", "unita": "Flac.", "dos_str": "100MG/ML", "rip": "(Non ripetibile)"}
        ]
    },
    "TACHIDOL": {
        "nome": "TACHIDOL", "categoria": "oppioidi", "prezzo": 50, "principio": "Paracetamolo+Codeina", "layout": "long",
        "varianti": [
            {"label": "500MG/30MG - 16 Bustine", "aic": "034185015", "unita": "Conf.", "qta_str": "500MG/30MG", "rip": "(Non ripetibile)"},
            {"label": "500MG/30MG - 16 Compresse", "aic": "034185039", "unita": "Conf.", "qta_str": "500MG/30MG", "rip": "(Non ripetibile)"}
        ]
    },
    "RIVOTRIL": {
        "nome": "RIVOTRIL", "categoria": "benzo", "prezzo": 30, "principio": "Clonazepam", "layout": "short",
        "varianti": [
            {"label": "2MG - 20 Compresse", "aic": "023159068", "unita": "Conf.", "dos_str": "20CPR/2MG", "rip": "(Ripetibile)"},
            {"label": "0.5MG - 20 Compresse", "aic": "023159056", "unita": "Conf.", "dos_str": "20CPR/0.5MG", "rip": "(Ripetibile)"},
            {"label": "2.5MG/ML - Gocce 10ML", "aic": "023159031", "unita": "Flac.", "dos_str": "2.5MG/ML", "rip": "(Ripetibile)"}
        ]
    },
    "XANAX": {
        "nome": "XANAX", "categoria": "benzo", "prezzo": 30, "principio": "Alprazolam", "layout": "short",
        "varianti": [
            {"label": "0.25MG - 20 Compresse", "aic": "025980010", "unita": "Conf.", "dos_str": "20CPR/0.25MG", "rip": "(Ripetibile)"},
            {"label": "0.50MG - 20 Compresse", "aic": "025980022", "unita": "Conf.", "dos_str": "20CPR/0.50MG", "rip": "(Ripetibile)"},
            {"label": "1MG - 20 Compresse", "aic": "025980034", "unita": "Conf.", "dos_str": "20CPR/1MG", "rip": "(Ripetibile)"},
            {"label": "0.75MG/ML - Gocce 20ML", "aic": "025980059", "unita": "Flac.", "dos_str": "0.75MG/ML", "rip": "(Ripetibile)"}
        ]
    },
    "LEXOTAN": {
        "nome": "LEXOTAN", "categoria": "benzo", "prezzo": 30, "principio": "Bromazepam", "layout": "short",
        "varianti": [
            {"label": "1.5MG - 20 Compresse", "aic": "022905012", "unita": "Conf.", "dos_str": "20CPR/1.5MG", "rip": "(Ripetibile)"},
            {"label": "3MG - 20 Compresse", "aic": "022905024", "unita": "Conf.", "dos_str": "20CPR/3MG", "rip": "(Ripetibile)"},
            {"label": "2.5MG/ML - Gocce 20ML", "aic": "022905051", "unita": "Flac.", "dos_str": "2.5MG/ML", "rip": "(Ripetibile)"}
        ]
    },
    "OKI": {
        "nome": "OKI", "categoria": "altro", "prezzo": None, "principio": "Ketoprofene", "layout": "short",
        "varianti": [
            {"label": "80MG - 30 Bustine", "aic": "028511058", "unita": "Conf.", "dos_str": "30BUST/80MG", "rip": "(Non ripetibile)"},
            {"label": "80MG/ML - Gocce 30ML", "aic": "028511072", "unita": "Flac.", "dos_str": "80MG/ML", "rip": "(Non ripetibile)"}
        ]
    },
    "TORADOL": {
        "nome": "TORADOL", "categoria": "altro", "prezzo": None, "principio": "Ketorolac", "layout": "short",
        "varianti": [
            {"label": "10MG - 10 Compresse", "aic": "027253019", "unita": "Conf.", "dos_str": "10CPR/10MG", "rip": "(Non ripetibile)"},
            {"label": "20MG/ML - Gocce 10ML", "aic": "027253045", "unita": "Flac.", "dos_str": "20MG/ML", "rip": "(Non ripetibile)"},
            {"label": "30MG/ML - 3 Fiale Iniett.", "aic": "027253033", "unita": "Conf.", "dos_str": "3FIALE/30MG", "rip": "(Non ripetibile)"}
        ]
    },
    "TACHIPIRINA": {
        "nome": "TACHIPIRINA", "categoria": "altro", "prezzo": None, "principio": "Paracetamolo", "layout": "short",
        "varianti": [
            {"label": "1000MG - 16 Compresse", "aic": "012745096", "unita": "Conf.", "dos_str": "16CPR/1000MG", "rip": "(Ripetibile)"},
            {"label": "500MG - 30 Compresse", "aic": "012745235", "unita": "Conf.", "dos_str": "30CPR/500MG", "rip": "(Ripetibile)"},
            {"label": "100MG/ML - Gocce 30ML", "aic": "012745033", "unita": "Flac.", "dos_str": "100MG/ML", "rip": "(Ripetibile)"}
        ]
    },
    "BRUFEN": {
        "nome": "BRUFEN", "categoria": "altro", "prezzo": None, "principio": "Ibuprofene", "layout": "short",
        "varianti": [
            {"label": "600MG - 30 Compresse", "aic": "022593129", "unita": "Conf.", "dos_str": "30CPR/600MG", "rip": "(Ripetibile)"},
            {"label": "800MG - 20 Compresse", "aic": "022593218", "unita": "Conf.", "dos_str": "20CPR/800MG", "rip": "(Ripetibile)"}
        ]
    }
}

# ==============================================================================
# 2. PARSER & NORMALIZZAZIONE
# ==============================================================================
LEET_MAP = str.maketrans({
    '4': 'A', '0': 'O', '1': 'I', '3': 'E', '5': 'S', '7': 'T', '8': 'B', '6': 'G', '9': 'G', '2': 'Z'
})

NOMI_COMUNI = [
    "MARIO", "LUIGI", "GIOVANNI", "GIUSEPPE", "ANTONIO", "FRANCESCO", "MARCO", "LUCA",
    "ANDREA", "ALESSANDRO", "MATTEO", "LORENZO", "DAVIDE", "SIMONE", "FEDERICO", "RICCARDO",
    "DANIELE", "GABRIELE", "STEFANO", "NICOLA", "CHRISTIAN", "DOMENICO", "VINCENZO", "PIETRO",
    "SALVATORE", "CARLO", "TOMMASO", "FILIPPO", "ALESSIO", "EMANUELE", "MICHELE", "PAOLO",
    "ROBERTO", "MASSIMO", "CLAUDIO", "FABIO", "GIORGIO", "ENRICO", "SERGIO", "MAURIZIO",
    "MARIA", "ANNA", "GIULIA", "FRANCESCA", "SARA", "LAURA", "CHIARA", "MARTINA", "ALESSIA",
    "VALENTINA", "FEDERICA", "ELISA", "ILARIA", "ELENA", "GIORGIA", "SILVIA", "PAOLA",
    "ROBERTA", "DANIELA", "MONICA", "SONIA", "VERONICA", "BEATRICE", "SOFIA", "AURORA",
    "ALICE", "GRETA", "VITTORIA", "CAMILLA", "CATERINA", "LUCIA", "ANTONELLA", "TERESA",
    "ROSA", "ANGELA", "GIOVANNA", "CARMELA", "RITA", "ERIKA", "CESARE"
]

MESI_TESTUALI = {
    "gennaio": 1, "gen": 1, "febbraio": 2, "feb": 2, "marzo": 3, "mar": 3,
    "aprile": 4, "apr": 4, "maggio": 5, "mag": 5, "giugno": 6, "giu": 6,
    "luglio": 7, "lug": 7, "agosto": 8, "ago": 8, "settembre": 9, "set": 9,
    "ottobre": 10, "ott": 10, "novembre": 11, "nov": 11, "dicembre": 12, "dic": 12
}

def de_leet_parola(parola: str) -> str:
    pulita = re.sub(r'[^a-zA-Z0-9]', '', parola)
    if not pulita:
        return ""
    if pulita.isdigit():
        return pulita
    return pulita.upper().translate(LEET_MAP)

def separa_nome_attaccato(parola_unica: str) -> str:
    camel_split = re.sub(r'([a-z0-9])([A-Z])', r' ', parola_unica)
    if " " in camel_split:
        parti = [de_leet_parola(p) for p in camel_split.split()]
        return " ".join(parti)

    up = de_leet_parola(parola_unica)
    for n in sorted(NOMI_COMUNI, key=len, reverse=True):
        n_clean = n.strip()
        if up.startswith(n_clean) and len(up) > len(n_clean) + 2:
            return f"{n_clean} {up[len(n_clean):]}"
        if up.endswith(n_clean) and len(up) > len(n_clean) + 2:
            return f"{up[:-len(n_clean)]} {n_clean}"

    if len(up) >= 10:
        meta = len(up) // 2
        return f"{up[:meta]} {up[meta:]}"
    return up

def normalizza_anno(aa_str: str) -> int:
    aa = int(aa_str)
    if aa < 100:
        return 2000 + aa if aa <= 26 else 1900 + aa
    return aa

def analizza_input_paziente_smart(testo_raw: str) -> dict:
    testo = testo_raw.strip()
    data_formattata = "15/04/1990"
    testo_senza_data = testo

    pattern_mese_txt = r'\b(\d{1,2})\s+(' + '|'.join(MESI_TESTUALI.keys()) + r')\s+(\d{2,4})\b'
    m_txt = re.search(pattern_mese_txt, testo, flags=re.IGNORECASE)
    if m_txt:
        gg = int(m_txt.group(1))
        mm = MESI_TESTUALI[m_txt.group(2).lower()]
        aaaa = normalizza_anno(m_txt.group(3))
        data_formattata = f"{gg:02d}/{mm:02d}/{aaaa}"
        testo_senza_data = testo[:m_txt.start()] + " " + testo[m_txt.end():]
    else:
        pattern_num = r'\b(\d{1,2})[\s/\-\.](\d{1,2})[\s/\-\.](\d{2,4})\b'
        m_num = re.search(pattern_num, testo)
        if m_num:
            gg = max(1, min(31, int(m_num.group(1))))
            mm = max(1, min(12, int(m_num.group(2))))
            aaaa = normalizza_anno(m_num.group(3))
            data_formattata = f"{gg:02d}/{mm:02d}/{aaaa}"
            testo_senza_data = testo[:m_num.start()] + " " + testo[m_num.end():]
        else:
            m_att = re.search(r'\b(\d{2})(\d{2})(\d{2,4})\b', testo)
            if m_att:
                gg = max(1, min(31, int(m_att.group(1))))
                mm = max(1, min(12, int(m_att.group(2))))
                aaaa = normalizza_anno(m_att.group(3))
                data_formattata = f"{gg:02d}/{mm:02d}/{aaaa}"
                testo_senza_data = testo[:m_att.start()] + " " + testo[m_att.end():]

    sesso = None
    m_sesso = re.search(r'\b(maschio|uomo|femmina|donna|m|f)\b', testo_senza_data, flags=re.IGNORECASE)
    if m_sesso:
        val_s = m_sesso.group(1).upper()
        if val_s in ["F", "FEMMINA", "DONNA"]:
            sesso = "F"
            testo_senza_data = testo_senza_data[:m_sesso.start()] + " " + testo_senza_data[m_sesso.end():]
        elif val_s in ["M", "MASCHIO", "UOMO"]:
            if len(val_s) > 1 or m_sesso.start() > len(testo_senza_data) - 4:
                sesso = "M"
                testo_senza_data = testo_senza_data[:m_sesso.start()] + " " + testo_senza_data[m_sesso.end():]

    luogo_trovato = None
    tutte_localita = list(CITTA_DB.keys()) + list(CATASTALI_EXTRA.keys())

    m_nato = re.search(r'\bnat[oa]?\s+(?:a|in)\s+([a-zA-Z0-9\s]{3,20})', testo_senza_data, flags=re.IGNORECASE)
    if m_nato:
        if "nata" in m_nato.group(0).lower() and not sesso:
            sesso = "F"
        cand_luogo = m_nato.group(1).strip()
        parole_cand = cand_luogo.split()
        for num_p in [2, 1]:
            if len(parole_cand) >= num_p:
                test_l = " ".join(de_leet_parola(w) for w in parole_cand[:num_p]).lower()
                match_c = difflib.get_close_matches(test_l, tutte_localita, n=1, cutoff=0.75)
                if match_c:
                    luogo_trovato = match_c[0]
                    break
        if not luogo_trovato and parole_cand:
            luogo_trovato = de_leet_parola(parole_cand[0]).lower()

    testo_pulito = re.sub(r'\b(nato|nata|nat|il|del|a|in|da|di)\b', ' ', testo_senza_data, flags=re.IGNORECASE)
    testo_pulito = re.sub(r'[|,\-/]', ' ', testo_pulito)

    tokens_raw = [t for t in testo_pulito.split() if t.strip()]
    tokens_deleet = [de_leet_parola(t) for t in tokens_raw if de_leet_parola(t)]

    tokens_nome = []
    idx = 0
    while idx < len(tokens_deleet):
        if idx + 1 < len(tokens_deleet):
            due_p = f"{tokens_deleet[idx]} {tokens_deleet[idx+1]}".lower()
            match_2 = difflib.get_close_matches(due_p, tutte_localita, n=1, cutoff=0.8)
            if match_2:
                luogo_trovato = match_2[0]
                idx += 2
                continue
        una_p = tokens_deleet[idx].lower()
        match_1 = difflib.get_close_matches(una_p, tutte_localita, n=1, cutoff=0.82)
        if match_1 and len(tokens_deleet) > 1:
            luogo_trovato = match_1[0]
            idx += 1
            continue
        tokens_nome.append(tokens_raw[idx])
        idx += 1

    if not luogo_trovato:
        luogo_trovato = "milano"

    if not tokens_nome:
        nome_finale = "MARIO ROSSI"
    elif len(tokens_nome) == 1:
        nome_finale = separa_nome_attaccato(tokens_nome[0])
    else:
        parti_corr = [de_leet_parola(t) for t in tokens_nome if de_leet_parola(t)]
        parti_corr = [p for p in parti_corr if not p.isdigit()]
        if len(parti_corr) == 1:
            nome_finale = separa_nome_attaccato(parti_corr[0])
        elif len(parti_corr) >= 2:
            nome_finale = " ".join(parti_corr)
        else:
            nome_finale = "MARIO ROSSI"

    if not sesso:
        primo_nome = nome_finale.split()[0].upper()
        if primo_nome.endswith("A") and primo_nome not in ["LUCA", "ANDREA", "NICOLA", "MATTIA", "ELIA", "TOBIA"]:
            sesso = "F"
        else:
            sesso = "M"

    cf_calcolato = calcola_cf_reale(nome_finale, data_formattata, sesso, luogo_trovato)

    return {
        "nome_assistito": nome_finale,
        "luogo_nascita": luogo_trovato.title(),
        "cf_assistito": cf_calcolato
    }

def trova_citta_smart(input_utente: str) -> str:
    pulito = " ".join(de_leet_parola(w) for w in input_utente.split()).lower()
    if not pulito:
        return "milano"
    for k in CITTA_DB:
        if pulito == k or pulito == k.replace(" ", ""):
            return k
    matches = difflib.get_close_matches(pulito, list(CITTA_DB.keys()), n=1, cutoff=0.65)
    if matches:
        return matches[0]
    return pulito

def trova_farmaco_smart(input_utente: str):
    primo_token = input_utente.strip().split()[0] if input_utente.strip() else ""
    pulito = de_leet_parola(primo_token)
    for k in FARMACI_DB:
        if k in pulito or pulito in k:
            return k
    matches = difflib.get_close_matches(pulito, list(FARMACI_DB.keys()), n=1, cutoff=0.6)
    if matches:
        return matches[0]
    return None

# ==============================================================================
# 3. ELABORAZIONE DATI ANAGRAFICI E MEDICI
# ==============================================================================
MESI_CF = {1: 'A', 2: 'B', 3: 'C', 4: 'D', 5: 'E', 6: 'H', 7: 'L', 8: 'M', 9: 'P', 10: 'R', 11: 'S', 12: 'T'}
ODD_MAP = {
    '0': 1, '1': 0, '2': 5, '3': 7, '4': 9, '5': 13, '6': 15, '7': 17, '8': 19, '9': 21,
    'A': 1, 'B': 0, 'C': 5, 'D': 7, 'E': 9, 'F': 13, 'G': 15, 'H': 17, 'I': 19, 'J': 21,
    'K': 2, 'L': 4, 'M': 18, 'N': 20, 'O': 11, 'P': 3, 'Q': 6, 'R': 8, 'S': 12, 'T': 14,
    'U': 16, 'V': 10, 'W': 22, 'X': 25, 'Y': 24, 'Z': 23
}
EVEN_MAP = {str(i): i for i in range(10)}
EVEN_MAP.update({chr(65 + i): i for i in range(26)})

def estrai_tre_lettere(testo: str, is_nome: bool = False) -> str:
    pulito = "".join(c for c in testo.upper() if c.isalpha())
    cons = [c for c in pulito if c not in "AEIOU"]
    vocs = [c for c in pulito if c in "AEIOU"]
    if is_nome and len(cons) >= 4:
        scelte = [cons[0], cons[2], cons[3]]
    else:
        scelte = (cons + vocs + ['X', 'X', 'X'])[:3]
    return "".join(scelte)

def trova_codice_catastale(luogo: str) -> str:
    l_clean = luogo.strip().lower()
    if l_clean in CITTA_DB:
        return CITTA_DB[l_clean]["catastale"]
    if l_clean in CATASTALI_EXTRA:
        return CATASTALI_EXTRA[l_clean]
    tutte = list(CITTA_DB.keys()) + list(CATASTALI_EXTRA.keys())
    m = difflib.get_close_matches(l_clean, tutte, n=1, cutoff=0.65)
    if m:
        k = m[0]
        return CITTA_DB[k]["catastale"] if k in CITTA_DB else CATASTALI_EXTRA[k]
    return "F205"

def calcola_cf_reale(nome_completo: str, data_nascita: str, sesso: str, luogo_nascita: str) -> str:
    try:
        parti = nome_completo.strip().split()
        if len(parti) >= 2:
            nome = parti[0]
            cognome = " ".join(parti[1:])
        else:
            nome = parti[0]
            cognome = "ROSSI"

        c_code = estrai_tre_lettere(cognome, is_nome=False)
        n_code = estrai_tre_lettere(nome, is_nome=True)

        dt = datetime.strptime(data_nascita.strip(), "%d/%m/%Y")
        aa = str(dt.year)[-2:]
        mm = MESI_CF[dt.month]
        gg = dt.day + (40 if sesso.strip().upper().startswith("F") else 0)
        gg_str = f"{gg:02d}"

        catastale = trova_codice_catastale(luogo_nascita)
        parziale = f"{c_code}{n_code}{aa}{mm}{gg_str}{catastale}"

        somma = 0
        for idx, ch in enumerate(parziale):
            if (idx + 1) % 2 == 1:
                somma += ODD_MAP[ch]
            else:
                somma += EVEN_MAP[ch]
        check_char = chr(65 + (somma % 26))
        return parziale + check_char
    except Exception:
        return fake.ssn().upper()

def risolvi_citta_e_medico(citta_input: str) -> dict:
    chiave = trova_citta_smart(citta_input)
    if chiave in CITTA_DB:
        info = CITTA_DB[chiave]
        med = random.choice(info["medici"])
        return {
            "citta_pura": info["nome"],
            "nome_medico": med["nome"],
            "spec_medico": "Medicina Generale",
            "via_medico": med["via"],
            "cap_citta_medico": f"{info['cap']} {info['nome']}",
            "prov_medico": f"({info['prov']})",
            "tel_medico": med["tel"]
        }
    else:
        nome_c = chiave.title()
        sigla_auto = nome_c[:2].upper()
        cap_auto = f"{random.randint(10, 95)}0{random.randint(10, 99)}"
        titolo = random.choice(["Dott.", "Dott.ssa"])
        nome_m = fake.first_name_male().upper() if titolo == "Dott." else fake.first_name_female().upper()
        cognome_m = fake.last_name().upper()
        return {
            "citta_pura": nome_c,
            "nome_medico": f"{titolo} {nome_m} {cognome_m}",
            "spec_medico": "Medicina Generale",
            "via_medico": f"Via {fake.street_name()} {random.randint(1, 190)},",
            "cap_citta_medico": f"{cap_auto} {nome_c}",
            "prov_medico": f"({sigla_auto})",
            "tel_medico": f"338{random.randint(100000, 999999)}"
        }

# ==============================================================================
# 4. GENERAZIONE BARCODE & DOCUMENTI PDF
# ==============================================================================
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

    # --- Intestazione ---
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

    # --- Assistito ---
    pdf.set_xy(13.0, 99.5)
    pdf.set_font("Times", "B", 12)
    pdf.cell(0, 6, "Assistito", ln=True)

    pdf.set_xy(13.0, 113.0)
    pdf.set_font("Times", "", 12)
    pdf.cell(0, 6, dati["nome_assistito"], ln=True)

    # --- Codice Fiscale ---
    pdf.set_xy(13.0, 137.0)
    pdf.set_font("Times", "", 12)
    pdf.cell(0, 6, "Codice Fiscale:", ln=True)
    pdf.image(bc_cf_path, x=21.5, y=143.0, w=66.0, h=14.5)

    # --- Prescrizione ---
    pdf.set_xy(13.0, 180.5)
    pdf.set_font("Times", "B", 12)
    pdf.cell(0, 6, "Prescrizione:", ln=True)
    pdf.image(bc_aic_path, x=16.5, y=193.0, w=53.0, h=13.5)

    pdf.set_font("Times", "", 13)
    pdf.set_xy(84.5, 207.0)
    pdf.cell(0, 6.2, dati["farmaco_riga1"], ln=True)

    pdf.set_xy(83.0, 213.5)
    pdf.cell(0, 6.2, dati["farmaco_riga2"], ln=True)

    if dati.get("farmaco_riga4"):
        pdf.set_xy(83.0, 220.0)
        pdf.cell(0, 6.2, dati["farmaco_riga3"], ln=True)
        pdf.set_xy(89.0, 226.5)
        pdf.cell(0, 6.2, dati["farmaco_riga4"], ln=True)
    else:
        pdf.set_xy(89.0, 220.0)
        pdf.cell(0, 6.2, dati["farmaco_riga3"], ln=True)

    # --- Data e Firma ---
    pdf.set_font("Times", "", 12)
    pdf.set_xy(11.0, 236.5)
    pdf.cell(80, 6, dati["luogo_data"], ln=0)

    pdf.set_xy(132.0, 236.5)
    pdf.cell(40, 6, "Firma", ln=1)

    pdf.output(pdf_path)

# ==============================================================================
# 5. GESTIONE STATI E FLUSSO BOT
# ==============================================================================
class FormPrescrizione(StatesGroup):
    paziente = State()
    citta = State()
    farmaco = State()
    scelta_dosaggio = State()
    quantita = State()
    luogo_data = State()
    attesa_pagamento = State()

@dp.message(F.text.func(lambda t: t and t.strip().lower() == SECRET_PASS))
async def sblocco_lifetime(message: Message, state: FSMContext):
    uid = message.from_user.id
    VIP_USERS.add(uid)
    salva_vip(uid)
    await state.clear()
    kb = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="ð Nuova Pratica")]],
        resize_keyboard=True
    )
    await message.answer(
        "ð **Accesso Lifetime Attivato.**\n"
        "Paywall disattivato per il tuo account.",
        reply_markup=kb,
        parse_mode="Markdown"
    )

@dp.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    uid = message.from_user.id
    is_vip = uid in VIP_USERS

    kb = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="ð Nuova Pratica")]],
        resize_keyboard=True
    )
    if is_vip:
        testo = "â¡ **Sistema Attivo (Licenza Lifetime)**\nPremi il pulsante in basso per procedere."
    else:
        testo = (
            "ð **Sistema Riservato**\n\n"
            "**Tariffario Emissione Singola:**\n"
            "â¢ Benzodiazepine: **30â¬** (BTC)\n"
            "â¢ Oppioidi: **50â¬** (BTC)\n"
            "â¢ Altri farmaci: **Su richiesta al proprietario**\n\n"
            "Premi il pulsante qui sotto per configurare la richiesta."
        )
    await message.answer(testo, reply_markup=kb, parse_mode="Markdown")

@dp.message(F.text == "ð Nuova Pratica")
async def step_paziente(message: Message, state: FSMContext):
    await state.set_state(FormPrescrizione.paziente)
    kb = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="â Annulla")]],
        resize_keyboard=True
    )
    await message.answer(
        "1ï¸â£ **Inserisci Nome, Cognome, Comune e Data di nascita:**",
        reply_markup=kb,
        parse_mode="Markdown"
    )

@dp.message(F.text == "â Annulla")
async def annulla_operazione(message: Message, state: FSMContext):
    await cmd_start(message, state)

@dp.message(FormPrescrizione.paziente)
async def ricevi_paziente(message: Message, state: FSMContext):
    info_paz = analizza_input_paziente_smart(message.text)

    await state.update_data(
        nome_assistito=info_paz["nome_assistito"],
        cf_assistito=info_paz["cf_assistito"]
    )
    await state.set_state(FormPrescrizione.citta)

    kb = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=info_paz["luogo_nascita"])],
            [KeyboardButton(text="Milano"), KeyboardButton(text="Roma"), KeyboardButton(text="Bari")],
            [KeyboardButton(text="Foggia"), KeyboardButton(text="Cerignola"), KeyboardButton(text="San Severo")]
        ],
        resize_keyboard=True
    )
    await message.answer(
        "2ï¸â£ **Indica la cittÃ  di emissione:**",
        reply_markup=kb,
        parse_mode="Markdown"
    )

@dp.message(FormPrescrizione.citta)
async def ricevi_citta(message: Message, state: FSMContext):
    medico_dati = risolvi_citta_e_medico(message.text)
    await state.update_data(**medico_dati)
    await state.set_state(FormPrescrizione.farmaco)

    kb = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Rivotril"), KeyboardButton(text="Xanax"), KeyboardButton(text="Lexotan")],
            [KeyboardButton(text="Depalgos"), KeyboardButton(text="Targin"), KeyboardButton(text="Contramal")],
            [KeyboardButton(text="Tachidol"), KeyboardButton(text="Oki"), KeyboardButton(text="Toradol")]
        ],
        resize_keyboard=True
    )
    await message.answer(
        "3ï¸â£ **Indica il prodotto richiesto:**",
        reply_markup=kb,
        parse_mode="Markdown"
    )

@dp.message(FormPrescrizione.farmaco)
async def ricevi_farmaco(message: Message, state: FSMContext):
    chiave_trovata = trova_farmaco_smart(message.text)
    uid = message.from_user.id
    is_vip = uid in VIP_USERS

    if chiave_trovata:
        scheda = FARMACI_DB[chiave_trovata]
        categoria = scheda["categoria"]
        prezzo = scheda["prezzo"]

        if not is_vip and categoria == "altro":
            await state.clear()
            kb = ReplyKeyboardMarkup(
                keyboard=[[KeyboardButton(text="ð Nuova Pratica")]],
                resize_keyboard=True
            )
            await message.answer(
                "â **Prodotto su Richiesta**\n\n"
                "Per questa tipologia l'emissione automatica Ã¨ disabilitata.\n"
                "Contatta direttamente il proprietario per l'abilitazione.",
                reply_markup=kb,
                parse_mode="Markdown"
            )
            return

        varianti = scheda["varianti"]
        await state.update_data(
            farmaco_nome_ufficiale=scheda["nome"],
            farmaco_principio=scheda["principio"],
            farmaco_layout=scheda["layout"],
            farmaco_categoria=categoria,
            farmaco_prezzo=prezzo,
            varianti_correnti=varianti
        )
        botones = [[KeyboardButton(text=v["label"])] for v in varianti]
        kb = ReplyKeyboardMarkup(keyboard=botones, resize_keyboard=True)
        await state.set_state(FormPrescrizione.scelta_dosaggio)
        await message.answer(
            "4ï¸â£ **Seleziona il formato:**",
            reply_markup=kb,
            parse_mode="Markdown"
        )
    else:
        if not is_vip:
            await state.clear()
            kb = ReplyKeyboardMarkup(
                keyboard=[[KeyboardButton(text="ð Nuova Pratica")]],
                resize_keyboard=True
            )
            await message.answer(
                "â **Prodotto Non Abilitato in Automatico**\n\n"
                "Per questo elemento Ã¨ necessario contattare direttamente il proprietario.",
                reply_markup=kb,
                parse_mode="Markdown"
            )
            return

        nome_pulito = de_leet_parola(message.text.strip().split()[0]) or "FARMACO"
        varianti_custom = [
            {"label": "20 Compresse 10MG", "aic": f"0{random.randint(10000000, 99999999)}", "unita": "Conf.", "qta_str": "20CPR", "dos_str": "10MG", "rip": "(Ripetibile)"},
            {"label": "30 Compresse 20MG", "aic": f"0{random.randint(10000000, 99999999)}", "unita": "Conf.", "qta_str": "30CPR", "dos_str": "20MG", "rip": "(Non ripetibile)"},
            {"label": "Gocce Orali 2.5MG/ML", "aic": f"0{random.randint(10000000, 99999999)}", "unita": "Flac.", "qta_str": "10ML", "dos_str": "2.5MG/ML", "rip": "(Ripetibile)"}
        ]
        await state.update_data(
            farmaco_nome_ufficiale=nome_pulito,
            farmaco_principio="Principio Attivo",
            farmaco_layout="long",
            farmaco_categoria="altro",
            farmaco_prezzo=0,
            varianti_correnti=varianti_custom
        )
        botones = [[KeyboardButton(text=v["label"])] for v in varianti_custom]
        kb = ReplyKeyboardMarkup(keyboard=botones, resize_keyboard=True)
        await state.set_state(FormPrescrizione.scelta_dosaggio)
        await message.answer("4ï¸â£ **Seleziona il formato:**", reply_markup=kb, parse_mode="Markdown")

@dp.message(FormPrescrizione.scelta_dosaggio)
async def ricevi_dosaggio(message: Message, state: FSMContext):
    scelta_txt = message.text.strip()
    dati = await state.get_data()
    varianti = dati.get("varianti_correnti", [])

    variante_scelta = varianti[0]
    for v in varianti:
        if v["label"].lower() == scelta_txt.lower() or scelta_txt.lower() in v["label"].lower():
            variante_scelta = v
            break

    await state.update_data(variante_scelta=variante_scelta)
    await state.set_state(FormPrescrizione.quantita)

    kb = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="1"), KeyboardButton(text="2"), KeyboardButton(text="3")]],
        resize_keyboard=True
    )
    await message.answer(
        "5ï¸â£ **Indica la quantitÃ :**",
        reply_markup=kb,
        parse_mode="Markdown"
    )

@dp.message(FormPrescrizione.quantita)
async def ricevi_quantita(message: Message, state: FSMContext):
    qta_num = "".join(c for c in message.text.strip() if c.isdigit()) or "1"
    dati = await state.get_data()
    
    nome_f = dati["farmaco_nome_ufficiale"]
    princ = dati["farmaco_principio"]
    layout = dati["farmaco_layout"]
    var = dati["variante_scelta"]
    unita = var["unita"]

    if princ and princ != "Specificifica" and princ != "Principio Attivo":
        princ_str = f"({princ})"
    else:
        princ_str = ""

    if layout == "long":
        riga1 = f"N.{qta_num}{unita} {nome_f}"
        riga2 = f"{princ_str} {var.get('qta_str', '')}".strip()
        riga3 = f"{var['dos_str']}"
        riga4 = f"{var['rip']}"
    else:
        if princ_str:
            riga1 = f"N.{qta_num}{unita} {nome_f} {princ_str}"
        else:
            riga1 = f"N.{qta_num}{unita} {nome_f}"
        riga2 = f"{var['dos_str']}"
        riga3 = f"{var['rip']}"
        riga4 = None

    await state.update_data(
        farmaco_riga1=riga1,
        farmaco_riga2=riga2,
        farmaco_riga3=riga3,
        farmaco_riga4=riga4,
        aic_farmaco=var["aic"]
    )
    await state.set_state(FormPrescrizione.luogo_data)

    oggi = datetime.now().strftime("%d/%m/%Y")
    citta_med = dati["citta_pura"]

    kb = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=f"{citta_med}, {oggi}")],
            [KeyboardButton(text=f"{citta_med}, 04/09/2025")]
        ],
        resize_keyboard=True
    )
    await message.answer(
        "6ï¸â£ **Conferma o inserisci la data:**",
        reply_markup=kb,
        parse_mode="Markdown"
    )

@dp.message(FormPrescrizione.luogo_data)
async def gestisci_emissione_o_paywall(message: Message, state: FSMContext):
    txt_data = message.text.strip()
    dati = await state.get_data()
    citta_med = dati["citta_pura"]

    m_d = re.search(r'(\d{1,2})[\s/\-\.](\d{1,2})[\s/\-\.](\d{2,4})', txt_data)
    if m_d:
        gg = int(m_d.group(1))
        mm = int(m_d.group(2))
        aaaa = normalizza_anno(m_d.group(3))
        luogo_data_finale = f"{citta_med}, {gg:02d}/{mm:02d}/{aaaa}"
    elif "," in txt_data:
        luogo_data_finale = txt_data
    else:
        luogo_data_finale = f"{citta_med}, {datetime.now().strftime('%d/%m/%Y')}"

    await state.update_data(luogo_data=luogo_data_finale)
    dati = await state.get_data()

    uid = message.from_user.id
    if uid in VIP_USERS:
        await state.clear()
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        bc_cf = genera_barcode_pulito(dati["cf_assistito"], f"bc_cf_{timestamp}")
        bc_aic = genera_barcode_pulito(dati["aic_farmaco"], f"bc_aic_{timestamp}")

        pdf_path = os.path.join(OUTPUT_DIR, f"DOC_{timestamp}.pdf")
        crea_pdf_identico(dati, pdf_path, bc_cf, bc_aic)

        kb = ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text="ð Nuova Pratica")]],
            resize_keyboard=True
        )
        await message.answer_document(
            FSInputFile(pdf_path),
            caption="â **Documento Emesso.**",
            reply_markup=kb,
            parse_mode="Markdown"
        )
        return

    prezzo = dati.get("farmaco_prezzo", 50)
    cat_label = "Benzodiazepine" if dati.get("farmaco_categoria") == "benzo" else "Oppioidi"

    await state.set_state(FormPrescrizione.attesa_pagamento)
    kb = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="ð Verifica Transazione BTC")],
            [KeyboardButton(text="â Annulla")]
        ],
        resize_keyboard=True
    )
    await message.answer(
        f"ð **PAGAMENTO RICHIESTO PER IL RILASCIO**\n\n"
        f"â¢ **Categoria:** {cat_label}\n"
        f"â¢ **Importo dovuto:** `{prezzo}â¬` in Bitcoin (BTC)\n\n"
        f"Invia esattamente **{prezzo}â¬** in BTC al seguente indirizzo:\n"
        f"`{BTC_WALLET}`\n\n"
        f"_Dopo aver inviato la transazione sulla rete Bitcoin, incolla qui il **TXID** (Hash della transazione) oppure premi il pulsante di verifica._",
        reply_markup=kb,
        parse_mode="Markdown"
    )

@dp.message(FormPrescrizione.attesa_pagamento)
async def verifica_pagamento_finto(message: Message, state: FSMContext):
    await message.answer(
        "â³ **Transazione non rilevata sulla Blockchain.**\n\n"
        f"Assicurati di aver inviato l'importo esatto al wallet:\n`{BTC_WALLET}`\n\n"
        "Attendere almeno 1 conferma di rete o contattare il proprietario fornendo il TXID.",
        parse_mode="Markdown"
    )

# --- SERVER WEB PER RENDER ---
async def handle(request):
    return web.Response(text="Service operational.")

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
    asyncio.run(main())
