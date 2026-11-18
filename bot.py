import os
import re
import json
import random
import difflib
import asyncio
from datetime import datetime
from aiohttp import web, ClientSession
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

# ==========================================
# INIZIALIZZAZIONE E DIRECTORY
# ==========================================
BOT_TOKEN = os.getenv("bottoken")
if not BOT_TOKEN:
    raise ValueError("ERRORE: Variabile d'ambiente 'bottoken' mancante.")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())
fake = Faker('it_IT')

OUTPUT_DIR = "output_files"
ASSETS_DIR = "assets_loghi"
os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(ASSETS_DIR, exist_ok=True)

# ==========================================
# CONFIGURAZIONE GLOBALE, PREZZI E SICUREZZA
# ==========================================
BTC_WALLET = os.getenv("BTC_WALLET", "bc1qr3lkmmwyrenuz2f7menf55yu8kt0ckzxzye2sy")
PREZZO_BENZO = 20
PREZZO_OPPIOIDI = 40
SECRET_PASS = "laziomerda"
FREE_PASS = "forzafoggia"

VIP_FILE = "vip_users.json"
CREDITS_FILE = "free_credits.json"
COMUNI_CACHE_FILE = "comuni_italiani_cache.json"

CITTA_ESCLUSE_BOTTONI = {
    "foggia", "san severo", "cerignola", "lucera", "manfredonia",
    "orta nova", "san giovanni rotondo", "torremaggiore", "sannicandro garganico"
}

# ==========================================
# DATABASE REGIONI (SSN DEMATERIALIZZATA)
# ==========================================
REGIONI_DB = {
    "puglia": {
        "header": "SERVIZIO SANITARIO NAZIONALE\nREGIONE PUGLIA",
        "asl_cod": "115",
        "prefisso_nre": "160A2",
        "logo": "logo_puglia.png"
    },
    "lombardia": {
        "header": "SERVIZIO SANITARIO NAZIONALE\nREGIONE LOMBARDIA",
        "asl_cod": "301",
        "prefisso_nre": "030A2",
        "logo": "logo_lombardia.png"
    },
    "lazio": {
        "header": "SERVIZIO SANITARIO NAZIONALE\nREGIONE LAZIO",
        "asl_cod": "201",
        "prefisso_nre": "120A2",
        "logo": "logo_lazio.png"
    },
    "campania": {
        "header": "SERVIZIO SANITARIO NAZIONALE\nREGIONE CAMPANIA",
        "asl_cod": "104",
        "prefisso_nre": "150A2",
        "logo": "logo_campania.png"
    },
    "piemonte": {
        "header": "SERVIZIO SANITARIO NAZIONALE\nREGIONE PIEMONTE",
        "asl_cod": "201",
        "prefisso_nre": "010A2",
        "logo": "logo_piemonte.png"
    },
    "emilia romagna": {
        "header": "SERVIZIO SANITARIO NAZIONALE\nREGIONE EMILIA-ROMAGNA",
        "asl_cod": "102",
        "prefisso_nre": "080A2",
        "logo": "logo_emilia_romagna.png"
    },
    "veneto": {
        "header": "SERVIZIO SANITARIO NAZIONALE\nREGIONE DEL VENETO",
        "asl_cod": "506",
        "prefisso_nre": "050A2",
        "logo": "logo_veneto.png"
    },
    "toscana": {
        "header": "SERVIZIO SANITARIO NAZIONALE\nREGIONE TOSCANA",
        "asl_cod": "201",
        "prefisso_nre": "090A2",
        "logo": "logo_toscana.png"
    }
}

# ==========================================
# DATABASE CITTA' DI EMISSIONE E MEDICI
# ==========================================
CITTA_DB = {
    "foggia": {
        "nome": "Foggia", "cap": "71121", "prov": "FG", "catastale": "D643", "regione": "puglia",
        "medici": [
            {"nome": "D'AMATO GIOVANNI", "titolo": "Dott.", "via": "Via Vittorio De Miro D'Ajeta 7,", "tel": "0881745210", "cf": "DMTGNN74M05D643X"},
            {"nome": "DIOGUARDI ANTONIO", "titolo": "Dott.", "via": "Via Dei Carbonari Dauni 40,", "tel": "3395412098", "cf": "DGRNTN68C12D643P"},
            {"nome": "LOPORCHIO MARIA TERESA", "titolo": "Dott.ssa", "via": "Viale Ofanto 198,", "tel": "0881723411", "cf": "LPRMRT80A41D643K"}
        ]
    },
    "san severo": {
        "nome": "San Severo", "cap": "71016", "prov": "FG", "catastale": "I158", "regione": "puglia",
        "medici": [
            {"nome": "FONTANELLO LAURA RITA PIA", "titolo": "Dott.ssa", "via": "Via Soccorso 185,", "tel": "3384065551", "cf": "FNTLRT80A41I158Z"},
            {"nome": "PRATTICHIZZO MATTEO", "titolo": "Dott.", "via": "Via Tiberio Solis 45,", "tel": "0882331422", "cf": "PRTMTT75A01I158W"}
        ]
    },
    "cerignola": {
        "nome": "Cerignola", "cap": "71042", "prov": "FG", "catastale": "C514", "regione": "puglia",
        "medici": [
            {"nome": "GIURATO DOMENICO", "titolo": "Dott.", "via": "Via Don Minzoni 57,", "tel": "3384065560", "cf": "GRTDMNC70A01C514X"},
            {"nome": "SPECCHIO FRANCESCO SAVERIO", "titolo": "Dott.", "via": "Corso Aldo Moro 112,", "tel": "0885421890", "cf": "SPCFNC80A01C514Y"}
        ]
    },
    "sannicandro garganico": {
        "nome": "Sannicandro Garganico", "cap": "71015", "prov": "FG", "catastale": "I049", "regione": "puglia",
        "medici": [
            {"nome": "RIZZO COSIMO DAMIANO", "titolo": "Dott.", "via": "Via Di Palma 74,", "tel": "3336789120", "cf": "RZZCMD72E14I049L"}
        ]
    },
    "bari": {
        "nome": "Bari", "cap": "70121", "prov": "BA", "catastale": "A662", "regione": "puglia",
        "medici": [
            {"nome": "BIANCHI NICOLA", "titolo": "Dott.", "via": "Via Sparano da Bari 12,", "tel": "3409182736", "cf": "BNCNCL75A01A662W"},
            {"nome": "DE SANTIS VALERIA", "titolo": "Dott.ssa", "via": "Corso Cavour 88,", "tel": "0805214399", "cf": "DSNVLR82H50A662Q"}
        ]
    },
    "milano": {
        "nome": "Milano", "cap": "20121", "prov": "MI", "catastale": "F205", "regione": "lombardia",
        "medici": [
            {"nome": "SABBATINI ERIKA", "titolo": "Dott.ssa", "via": "Via Giuseppe Ripamonti 114,", "tel": "3382290554", "cf": "SBBKRK80A41F205X"},
            {"nome": "COLOMBO ALESSANDRO", "titolo": "Dott.", "via": "Corso Buenos Aires 42,", "tel": "0267483921", "cf": "CLMLSN75A01F205Y"}
        ]
    },
    "bergamo": {
        "nome": "Bergamo", "cap": "24121", "prov": "BG", "catastale": "A794", "regione": "lombardia",
        "medici": [
            {"nome": "LOCATELLI GIORGIO", "titolo": "Dott.", "via": "Viale Papa Giovanni XXIII 45,", "tel": "035214589", "cf": "LCTGRG71B12A794U"}
        ]
    },
    "roma": {
        "nome": "Roma", "cap": "00185", "prov": "RM", "catastale": "H501", "regione": "lazio",
        "medici": [
            {"nome": "PROIETTI MARCO VALERIO", "titolo": "Dott.", "via": "Via Appia Nuova 215,", "tel": "3358901234", "cf": "PRTMCV78A01H501Z"},
            {"nome": "MANCINI CLAUDIA", "titolo": "Dott.ssa", "via": "Viale Trastevere 108,", "tel": "065812390", "cf": "MNCCLD81D52H501V"}
        ]
    },
    "napoli": {
        "nome": "Napoli", "cap": "80121", "prov": "NA", "catastale": "F839", "regione": "campania",
        "medici": [
            {"nome": "ESPOSITO GENNARO", "titolo": "Dott.", "via": "Via Toledo 156,", "tel": "3389012345", "cf": "SPGGNR70A01F839W"},
            {"nome": "COPPOLA CARMINE", "titolo": "Dott.", "via": "Corso Umberto I 45,", "tel": "0815543210", "cf": "CPPCMN69B15F839T"}
        ]
    },
    "torino": {
        "nome": "Torino", "cap": "10121", "prov": "TO", "catastale": "L219", "regione": "piemonte",
        "medici": [
            {"nome": "FERRERO EDOARDO", "titolo": "Dott.", "via": "Corso Francia 90,", "tel": "3487654321", "cf": "FRRDDR75A01L219K"}
        ]
    },
    "bologna": {
        "nome": "Bologna", "cap": "40121", "prov": "BO", "catastale": "A944", "regione": "emilia romagna",
        "medici": [
            {"nome": "RIGHI CHIARA", "titolo": "Dott.ssa", "via": "Via Indipendenza 54,", "tel": "3391122334", "cf": "RGHCHR82A41A944J"}
        ]
    },
    "firenze": {
        "nome": "Firenze", "cap": "50121", "prov": "FI", "catastale": "D612", "regione": "toscana",
        "medici": [
            {"nome": "ROSSI LORENZO", "titolo": "Dott.", "via": "Viale Giacomo Matteotti 18,", "tel": "0552345678", "cf": "RSSLRN74C10D612M"}
        ]
    },
    "venezia": {
        "nome": "Venezia", "cap": "30121", "prov": "VE", "catastale": "L736", "regione": "veneto",
        "medici": [
            {"nome": "TREVISAN ANDREA", "titolo": "Dott.", "via": "Corso del Popolo 110,", "tel": "0419876543", "cf": "TRVNDR77H12L736E"}
        ]
    }
}

# Database esteso di tutti i Capoluoghi d'Italia, Comuni principali e Nazioni Estere (Codici Belfiore ufficiali)
CATASTALI_ITALIA_ESTERO = {
    # Stati Esteri principali
    "brasile": "Z602", "romania": "Z129", "albania": "Z100", "marocco": "Z330",
    "svizzera": "Z133", "germania": "Z112", "francia": "Z110", "spagna": "Z131",
    "regno unito": "Z114", "inghilterra": "Z114", "ucraina": "Z138", "tunisia": "Z352",
    "egitto": "Z336", "cina": "Z210", "argentina": "Z600", "stati uniti": "Z404",
    "polonia": "Z127", "moldavia": "Z140", "peru": "Z611", "ecuador": "Z605",
    "colombia": "Z604", "nigeria": "Z335", "senegal": "Z343", "pakistan": "Z236",
    "india": "Z222", "filippine": "Z216", "bangladesh": "Z249",
    #Tutti i Capoluoghi di Provincia Italiani + Principali Comuni
    "agrigento": "A089", "alessandria": "A182", "ancona": "A271", "andria": "A285",
    "aosta": "A326", "arezzo": "A390", "ascoli piceno": "A462", "asti": "A479",
    "avellino": "A509", "bari": "A662", "barletta": "A669", "belluno": "A757",
    "benevento": "A783", "bergamo": "A794", "biella": "A859", "bologna": "A944",
    "bolzano": "A952", "brescia": "B157", "brindisi": "B180", "cagliari": "B354",
    "caltanissetta": "B429", "campobasso": "B519", "carbonia": "B745", "caserta": "B963",
    "catania": "C351", "catanzaro": "C352", "cesena": "C573", "chieti": "C632",
    "como": "C933", "cosenza": "D086", "cremona": "D150", "crotone": "D122",
    "cuneo": "D205", "enna": "C342", "fermo": "D542", "ferrara": "D548",
    "firenze": "D612", "foggia": "D643", "forli": "D704", "frosinone": "D810",
    "genova": "D969", "gorizia": "E098", "grosseto": "E202", "imperia": "E290",
    "isernia": "E335", "l'aquila": "A345", "laquila": "A345", "la spezia": "E463",
    "latina": "E472", "lecce": "E506", "lecco": "E507", "livorno": "E625",
    "lodi": "E648", "lucca": "E715", "macerata": "E783", "mantova": "E897",
    "massa": "F023", "matera": "F052", "messina": "F158", "milano": "F205",
    "modena": "F257", "monza": "F704", "napoli": "F839", "novara": "F952",
    "nuoro": "F979", "oristano": "G113", "padova": "G224", "palermo": "G273",
    "parma": "G337", "pavia": "G388", "perugia": "G478", "pesaro": "G479",
    "pescara": "G482", "piacenza": "G535", "pisa": "G702", "pistoia": "G713",
    "pordenone": "G888", "potenza": "G942", "prato": "G999", "ragusa": "H163",
    "ravenna": "H199", "reggio calabria": "H224", "reggio emilia": "H223", "rieti": "H282",
    "rimini": "H294", "roma": "H501", "rovigo": "H620", "salerno": "H703",
    "sassari": "I452", "savona": "I480", "siena": "I726", "siracusa": "I754",
    "sondrio": "I829", "taranto": "L049", "teramo": "L103", "terni": "L117",
    "torino": "L219", "trani": "L328", "trapani": "L331", "trento": "L378",
    "treviso": "L407", "trieste": "L424", "udine": "L483", "urbino": "L500",
    "varese": "L682", "venezia": "L736", "verbania": "L746", "vercelli": "L750",
    "verona": "L781", "vibo valentia": "F537", "vicenza": "L840", "viterbo": "M082",
    # Comuni extra Puglia e grandi centri
    "san severo": "I158", "cerignola": "C514", "manfredonia": "E885", "lucera": "E716",
    "orta nova": "G131", "san giovanni rotondo": "H926", "torremaggiore": "L273",
    "sannicandro garganico": "I049", "vieste": "L858", "peschici": "G487",
    "monte sant'angelo": "F631", "apricena": "A339", "troia": "L447", "bovino": "B104",
    "ascoli satriano": "A463", "carapelle": "B724", "ordona": "M266", "stornara": "I962",
    "stornarella": "I963", "zapponeta": "M267", "margherita di savoia": "E946",
    "trinitapoli": "B915", "san ferdinando di puglia": "H839", "bisceglie": "A883",
    "molfetta": "F284", "corato": "C983", "ruvo di puglia": "H645", "terlizzi": "L109",
    "bitonto": "A893", "modugno": "F262", "altamura": "A225", "gravina in puglia": "E155",
    "monopoli": "F376", "putignano": "H096", "fasano": "D508", "ostuni": "G187",
    "francavilla fontana": "D761", "manduria": "E882", "martina franca": "E986",
    "grottaglie": "E205", "massafra": "F027", "gallipoli": "D883", "nardò": "F842",
    "galatina": "D862", "casarano": "B936", "tricase": "L419", "maglie": "E815",
    "busto arsizio": "B300", "gallarate": "D869", "saronno": "I441", "sesto san giovanni": "I690",
    "cinisello balsamo": "C707", "legnano": "E514", "rho": "H264", "cologno monzese": "C895",
    "paderno dugnano": "G220", "rozzano": "H623", "corsico": "D045", "segrate": "I577",
    "pioltello": "G686", "abbiategrasso": "A010", "san donato milanese": "H827",
    "treviglio": "L400", "seriate": "I628", "dalmine": "D245", "romano di lombardia": "H509",
    "alzano lombardo": "A246", "caravaggio": "B731", "osio sotto": "G159", "ponteranica": "G853"
}

async def aggiorna_cache_comuni():
    """Scarica all'avvio tutti gli 8.000+ comuni italiani per avere copertura totale al 100%."""
    global CATASTALI_ITALIA_ESTERO
    if os.path.exists(COMUNI_CACHE_FILE):
        try:
            with open(COMUNI_CACHE_FILE, "r", encoding="utf-8") as f:
                cached = json.load(f)
                CATASTALI_ITALIA_ESTERO.update(cached)
                return
        except Exception:
            pass

    url = "https://raw.githubusercontent.com/matteocontrini/comuni-json/master/comuni.json"
    try:
        async with ClientSession() as session:
            async with session.get(url, timeout=10) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    nuovi = {}
                    for item in data:
                        nome_c = item.get("nome", "").strip().lower()
                        cod_cat = item.get("codiceCatastale", "").strip().upper()
                        if nome_c and cod_cat:
                            nuovi[nome_c] = cod_cat
                    if nuovi:
                        CATASTALI_ITALIA_ESTERO.update(nuovi)
                        with open(COMUNI_CACHE_FILE, "w", encoding="utf-8") as f:
                            json.dump(nuovi, f, ensure_ascii=False)
    except Exception:
        pass

# ==========================================
# DATABASE COMPLETO FARMACI E VARIANTI
# ==========================================
FARMACI_DB = {
    "RIVOTRIL": {
        "nome": "RIVOTRIL", "categoria": "benzo", "prezzo": PREZZO_BENZO, "principio": "CLONAZEPAM",
        "varianti": [
            {"label": "20CPR 2MG", "aic": "023159068", "ssn_str": "RIVOTRIL*20CPR 2MG", "rip": "(Ripetibile)", "is_rip": True},
            {"label": "20CPR 0,5MG", "aic": "023159056", "ssn_str": "RIVOTRIL*20CPR 0,5MG", "rip": "(Ripetibile)", "is_rip": True},
            {"label": "GOCCE 10ML 2,5MG/ML", "aic": "023159031", "ssn_str": "RIVOTRIL*OS GTT 10ML 2,5MG/ML", "rip": "(Ripetibile)", "is_rip": True}
        ]
    },
    "XANAX": {
        "nome": "XANAX", "categoria": "benzo", "prezzo": PREZZO_BENZO, "principio": "ALPRAZOLAM",
        "varianti": [
            {"label": "20CPR 1MG", "aic": "025980112", "ssn_str": "XANAX*20CPR 1MG", "rip": "(Ripetibile)", "is_rip": True},
            {"label": "20CPR 0,50MG", "aic": "025980100", "ssn_str": "XANAX*20CPR 0,50MG", "rip": "(Ripetibile)", "is_rip": True},
            {"label": "30CPR 2MG RP", "aic": "025980151", "ssn_str": "XANAX*30CPR 2MG RP", "rip": "(Ripetibile)", "is_rip": True},
            {"label": "GOCCE 20ML 0,75MG/ML", "aic": "025980050", "ssn_str": "XANAX*OS GTT 20ML 0,75MG/ML", "rip": "(Ripetibile)", "is_rip": True}
        ]
    },
    "TAVOR": {
        "nome": "TAVOR", "categoria": "benzo", "prezzo": PREZZO_BENZO, "principio": "LORAZEPAM",
        "varianti": [
            {"label": "20CPR 2,5MG", "aic": "022531028", "ssn_str": "TAVOR*20CPR 2,5MG", "rip": "(Ripetibile)", "is_rip": True},
            {"label": "20CPR 1MG", "aic": "022531016", "ssn_str": "TAVOR*20CPR 1MG", "rip": "(Ripetibile)", "is_rip": True}
        ]
    },
    "STILNOX": {
        "nome": "STILNOX", "categoria": "benzo", "prezzo": PREZZO_BENZO, "principio": "ZOLPIDEM TARTRATO",
        "varianti": [
            {"label": "30CPR/10MG", "aic": "026695020", "ssn_str": "STILNOX*30CPR RIV 10MG", "rip": "(Non ripetibile)", "is_rip": False}
        ]
    },
    "TRITTICO": {
        "nome": "TRITTICO", "categoria": "benzo", "prezzo": PREZZO_BENZO, "principio": "TRAZODONE CLORIDRATO",
        "varianti": [
            {"label": "20CPR DIV 150MG RP", "aic": "022323075", "ssn_str": "TRITTICO*20CPR DIV 150MG RP", "rip": "(Ripetibile)", "is_rip": True},
            {"label": "30CPR DIV 75MG RP", "aic": "022323063", "ssn_str": "TRITTICO*30CPR DIV 75MG RP", "rip": "(Ripetibile)", "is_rip": True}
        ]
    },
    "DEPALGOS": {
        "nome": "DEPALGOS", "categoria": "oppioidi", "prezzo": PREZZO_OPPIOIDI, "principio": "OSSICODONE+PARACETAMOLO",
        "varianti": [
            {"label": "28CPR 5MG/325MG", "aic": "035313028", "ssn_str": "DEPALGOS*28CPR RIV 5MG+325MG", "rip": "(Non ripetibile)", "is_rip": False},
            {"label": "28CPR 10MG/325MG", "aic": "035313042", "ssn_str": "DEPALGOS*28CPR RIV 10MG+325MG", "rip": "(Non ripetibile)", "is_rip": False},
            {"label": "28CPR 20MG/325MG", "aic": "035313067", "ssn_str": "DEPALGOS*28CPR RIV 20MG+325MG", "rip": "(Non ripetibile)", "is_rip": False}
        ]
    },
    "TARGIN": {
        "nome": "TARGIN", "categoria": "oppioidi", "prezzo": PREZZO_OPPIOIDI, "principio": "OSSICODONE+NALOXONE",
        "varianti": [
            {"label": "28CPR 10MG/5MG RP", "aic": "039586159", "ssn_str": "TARGIN*28CPR 10MG+5MG RP", "rip": "(Non ripetibile)", "is_rip": False},
            {"label": "28CPR 20MG/10MG RP", "aic": "039586274", "ssn_str": "TARGIN*28CPR 20MG+10MG RP", "rip": "(Non ripetibile)", "is_rip": False}
        ]
    },
    "OXYCONTIN": {
        "nome": "OXYCONTIN", "categoria": "oppioidi", "prezzo": PREZZO_OPPIOIDI, "principio": "OSSICODONE CLORIDRATO",
        "varianti": [
            {"label": "28CPR 10MG RP", "aic": "034435014", "ssn_str": "OXYCONTIN*28CPR 10MG RP", "rip": "(Non ripetibile)", "is_rip": False},
            {"label": "28CPR 20MG RP", "aic": "034435026", "ssn_str": "OXYCONTIN*28CPR 20MG RP", "rip": "(Non ripetibile)", "is_rip": False},
            {"label": "28CPR 40MG RP", "aic": "034435038", "ssn_str": "OXYCONTIN*28CPR 40MG RP", "rip": "(Non ripetibile)", "is_rip": False}
        ]
    }
}

# ==========================================
# GESTIONE PERSISTENZA CREDITI E VIP
# ==========================================
def carica_vip() -> set:
    if os.path.exists(VIP_FILE):
        try:
            with open(VIP_FILE, "r", encoding="utf-8") as f:
                return set(json.load(f))
        except Exception:
            return set()
    return set()

def salva_vip(user_id: int):
    vips = carica_vip()
    vips.add(user_id)
    try:
        with open(VIP_FILE, "w", encoding="utf-8") as f:
            json.dump(list(vips), f)
    except Exception:
        pass

def carica_crediti() -> dict:
    if os.path.exists(CREDITS_FILE):
        try:
            with open(CREDITS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def scala_credito(user_id: int) -> bool:
    crediti = carica_crediti()
    uid_str = str(user_id)
    current = crediti.get(uid_str, 0)
    if current > 0:
        crediti[uid_str] = current - 1
        try:
            with open(CREDITS_FILE, "w", encoding="utf-8") as f:
                json.dump(crediti, f)
        except Exception:
            pass
        return True
    return False

def aggiungi_crediti_gratuiti(user_id: int, quantita: int = 3):
    crediti = carica_crediti()
    uid_str = str(user_id)
    crediti[uid_str] = crediti.get(uid_str, 0) + quantita
    try:
        with open(CREDITS_FILE, "w", encoding="utf-8") as f:
            json.dump(crediti, f)
    except Exception:
        pass

VIP_USERS = carica_vip()

# ==========================================
# MOTORE INTELLIGENTE DI PARSING E CF REALE
# ==========================================
LEET_MAP = str.maketrans({
    '4': 'A', '0': 'O', '1': 'I', '3': 'E', '5': 'S', '7': 'T', '8': 'B', '6': 'G', '9': 'G', '2': 'Z'
})

MESI_CF = {1: 'A', 2: 'B', 3: 'C', 4: 'D', 5: 'E', 6: 'H', 7: 'L', 8: 'M', 9: 'P', 10: 'R', 11: 'S', 12: 'T'}

MESI_TESTUALI = {
    "gennaio": 1, "gen": 1, "febbraio": 2, "feb": 2, "marzo": 3, "mar": 3,
    "aprile": 4, "apr": 4, "maggio": 5, "mag": 5, "giugno": 6, "giu": 6,
    "luglio": 7, "lug": 7, "agosto": 8, "ago": 8, "settembre": 9, "set": 9,
    "ottobre": 10, "ott": 10, "novembre": 11, "nov": 11, "dicembre": 12, "dic": 12
}

ODD_MAP = {
    '0': 1, '1': 0, '2': 5, '3': 7, '4': 9, '5': 13, '6': 15, '7': 17, '8': 19, '9': 21,
    'A': 1, 'B': 0, 'C': 5, 'D': 7, 'E': 9, 'F': 13, 'G': 15, 'H': 17, 'I': 19, 'J': 21,
    'K': 2, 'L': 4, 'M': 18, 'N': 20, 'O': 11, 'P': 3, 'Q': 6, 'R': 8, 'S': 12, 'T': 14,
    'U': 16, 'V': 10, 'W': 22, 'X': 25, 'Y': 24, 'Z': 23
}

EVEN_MAP = {
    '0': 0, '1': 1, '2': 2, '3': 3, '4': 4, '5': 5, '6': 6, '7': 7, '8': 8, '9': 9,
    'A': 0, 'B': 1, 'C': 2, 'D': 3, 'E': 4, 'F': 5, 'G': 6, 'H': 7, 'I': 8, 'J': 9,
    'K': 10, 'L': 11, 'M': 12, 'N': 13, 'O': 14, 'P': 15, 'Q': 16, 'R': 17, 'S': 18, 'T': 19,
    'U': 20, 'V': 21, 'W': 22, 'X': 23, 'Y': 24, 'Z': 25
}

NOMI_MASCHILI = {
    "MARIO", "LUIGI", "GIOVANNI", "GIUSEPPE", "ANTONIO", "FRANCESCO", "MARCO", "LUCA",
    "ANDREA", "ALESSANDRO", "MATTEO", "LORENZO", "DAVIDE", "SIMONE", "FEDERICO", "RICCARDO",
    "STEFANO", "NICOLA", "MICHELE", "FABIO", "PAOLO", "ROBERTO", "DANIELE", "CRISTIAN",
    "CHRISTIAN", "PIERLUIGI", "VINCENZO", "SALVATORE", "EMANUELE", "PIETRO", "MASSIMO",
    "CLAUDIO", "MAURIZIO", "PASQUALE", "DOMENICO", "GABRIELE", "SAMUELE", "TOMMASO",
    "EDOARDO", "LEONARDO", "FILIPPO", "GIANLUCA", "ALESSIO", "RAFFAELE", "GENNARO",
    "CARMINE", "COSIMO", "DAMIANO", "GAETANO", "CIRO", "ENRICO", "GIORGIO", "ALBERTO",
    "DIEGO", "MANUEL", "MIRKO", "KEVIN", "DENIS", "IVAN", "SERGIO", "LUCIANO", "CARLO"
}

NOMI_FEMMINILI = {
    "MARIA", "ANNA", "GIULIA", "FRANCESCA", "SARA", "LAURA", "CHIARA", "MARTINA",
    "VALENTINA", "ALESSIA", "FEDERICA", "ELENA", "SOFIA", "ROBERTA", "GIOVANNA",
    "PAOLA", "DANIELA", "MONICA", "SILVIA", "BEATRICE", "GIORGIA", "ELISA", "LUCILEIDE",
    "ANTONELLA", "TERESA", "LUCIA", "CARMELA", "ROSA", "ANGELA", "CONCETTA", "RITA",
    "VALERIA", "CLAUDIA", "VERONICA", "CAMILLA", "ARIANNA", "NOEMI", "AURORA", "ALICE",
    "GRETA", "VITTORIA", "GINEVRA", "NICOLE", "GAIA", "REBECCA", "IRENE", " CATERINA",
    "SERENA", "SIMONA", "STEFANIA", "CRISTINA", "BARBARA", "SABRINA", "PATRIZIA",
    "DEBORA", "DEBORAH", "JESSICA", "VANESSA", "MELISSA", "ILARIA", "SONIA", "NADIA",
    " ERIKA", "ERICA", "DILETTA", "MIRIAM", "MARTA", "ELEONORA", "CARLOTTA", "BIANCA"
}

TUTTI_NOMI_PROPRI = NOMI_MASCHILI | NOMI_FEMMINILI

PREFISSI_COGNOME = {"DE", "DI", "DEL", "DELLA", "DELLO", "DEGLI", "DAL", "DALLA", "LA", "LO", "LI", "LE", "VAN", "VON", "SAN", "SANTA"}

def de_leet_parola(parola: str) -> str:
    pulita = re.sub(r"[^a-zA-Z0-9']", "", parola)
    if not pulita:
        return ""
    if pulita.isdigit():
        return pulita
    return pulita.upper().translate(LEET_MAP)

def estrai_cons_voc(testo: str):
    t = re.sub(r'[^A-Z]', '', testo.upper())
    cons = [c for c in t if c not in "AEIOU"]
    voc = [c for c in t if c in "AEIOU"]
    return cons, voc

def codifica_cognome(cognome: str) -> str:
    cons, voc = estrai_cons_voc(cognome)
    lettere = cons + voc + ['X', 'X', 'X']
    return "".join(lettere[:3])

def codifica_nome(nome: str) -> str:
    cons, voc = estrai_cons_voc(nome)
    if len(cons) >= 4:
        scelte = [cons[0], cons[2], cons[3]]
    else:
        scelte = (cons + voc + ['X', 'X', 'X'])[:3]
    return "".join(scelte)

def calcola_cf_reale(cognome: str, nome: str, gg: int, mm: int, aaaa: int, sesso: str, catastale: str) -> str:
    c_cod = codifica_cognome(cognome)
    n_cod = codifica_nome(nome)
    aa_cod = f"{aaaa % 100:02d}"
    m_cod = MESI_CF.get(mm, 'A')
    g_cod = f"{gg + 40 if sesso.upper() == 'F' else gg:02d}"
    parziale = f"{c_cod}{n_cod}{aa_cod}{m_cod}{g_cod}{catastale.upper()}"
    
    somma = 0
    for idx, ch in enumerate(parziale[:15]):
        if (idx + 1) % 2 == 1:
            somma += ODD_MAP.get(ch, 0)
        else:
            somma += EVEN_MAP.get(ch, 0)
    check_char = chr(ord('A') + (somma % 26))
    return f"{parziale[:15]}{check_char}"

def normalizza_anno(aa_str: str) -> int:
    aa = int(aa_str)
    if aa < 100:
        return 2000 + aa if aa <= 26 else 1900 + aa
    return aa

def analizza_input_paziente_smart(testo_raw: str) -> dict:
    """
    Riconosce automaticamente data di nascita, qualsiasi comune italiano/estero (anche con errori di battitura)
    e distingue tra Nome e Cognome anche se scritti invertiti (es. 'Valentina Melchionda' -> Cognome: MELCHIONDA, Nome: VALENTINA).
    """
    testo = testo_raw.strip()
    gg, mm, aaaa = 24, 3, 1995
    testo_senza_data = testo

    # 1. Estrazione Data (formati: 24/03/2006, 24-03-06, 24.03.2006, 24 03 2006)
    pattern_num = r'\b(\d{1,2})[\s/\-\.](\d{1,2})[\s/\-\.](\d{2,4})\b'
    m_num = re.search(pattern_num, testo)
    if m_num:
        gg = max(1, min(31, int(m_num.group(1))))
        mm = max(1, min(12, int(m_num.group(2))))
        aaaa = normalizza_anno(m_num.group(3))
        testo_senza_data = testo[:m_num.start()] + " " + testo[m_num.end():]
    else:
        # Formato testuale: 24 marzo 2006
        pattern_txt = r'\b(\d{1,2})\s+(' + '|'.join(MESI_TESTUALI.keys()) + r')\s+(\d{2,4})\b'
        m_txt = re.search(pattern_txt, testo.lower())
        if m_txt:
            gg = max(1, min(31, int(m_txt.group(1))))
            mm = MESI_TESTUALI[m_txt.group(2)]
            aaaa = normalizza_anno(m_txt.group(3))
            testo_senza_data = testo[:m_txt.start()] + " " + testo[m_txt.end():]

    # Pulizia parole di collegamento ("nato a", "nata il", ecc.)
    testo_pulito = re.sub(r'\b(nato|nata|nat|il|del|a|in|da)\b', ' ', testo_senza_data, flags=re.IGNORECASE)

    # 2. Riconoscimento Comune di Nascita (Esatto + Fuzzy su tutti i comuni)
    tutte_localita = {**{k: v["catastale"] for k, v in CITTA_DB.items()}, **CATASTALI_ITALIA_ESTERO}
    luogo_trovato = None
    catastale = None

    # A) Ricerca match esatto (partendo dai nomi di comune più lunghi, es. "San Giovanni Rotondo")
    testo_lower = testo_pulito.lower()
    for loc, cat in sorted(tutte_localita.items(), key=lambda x: len(x[0]), reverse=True):
        if re.search(rf'\b{re.escape(loc)}\b', testo_lower):
            luogo_trovato = loc
            catastale = cat
            testo_pulito = re.sub(rf'\b{re.escape(loc)}\b', ' ', testo_pulito, count=1, flags=re.IGNORECASE)
            break

    tokens_raw = [de_leet_parola(t) for t in testo_pulito.split() if t.strip() and not t.isdigit()]
    tokens_raw = [t for t in tokens_raw if t]

    # B) Se non ha trovato un match esatto, controlla se una delle parole è un comune scritto con leggero typo (es. "bergmo")
    if not luogo_trovato and len(tokens_raw) >= 3:
        for idx in range(len(tokens_raw) - 1, -1, -1):
            parola_test = tokens_raw[idx].lower()
            if parola_test.upper() in TUTTI_NOMI_PROPRI or parola_test.upper() in PREFISSI_COGNOME:
                continue
            matches = difflib.get_close_matches(parola_test, list(tutte_localita.keys()), n=1, cutoff=0.82)
            if matches:
                luogo_trovato = matches[0]
                catastale = tutte_localita[luogo_trovato]
                tokens_raw.pop(idx)
                break

    if not luogo_trovato:
        luogo_trovato = "foggia"
        catastale = "D643"

    # 3. Riconoscimento intelligente NOME vs COGNOME (anche invertiti)
    cognome = "ROSSI"
    nome = "MARIO"

    if len(tokens_raw) == 1:
        cognome = tokens_raw[0]
        nome = "MARIO"
    elif len(tokens_raw) == 2:
        t1, t2 = tokens_raw[0], tokens_raw[1]
        t1_is_nome = t1 in TUTTI_NOMI_PROPRI
        t2_is_nome = t2 in TUTTI_NOMI_PROPRI

        # Se la prima parola è un nome proprio (es. VALENTINA) e la seconda non lo è (es. MELCHIONDA) -> Inverti!
        if t1_is_nome and not t2_is_nome:
            nome = t1
            cognome = t2
        elif t2_is_nome and not t1_is_nome:
            cognome = t1
            nome = t2
        else:
            # Se entrambi o nessuno sono nel set, controlla desinenze tipiche o mantieni standard Cognome Nome
            cognome = t1
            nome = t2
    elif len(tokens_raw) >= 3:
        # Gestione cognomi composti (es. "De Miro", "Di Palma") o doppi nomi (es. "Maria Teresa")
        if tokens_raw[0] in PREFISSI_COGNOME:
            cognome = f"{tokens_raw[0]} {tokens_raw[1]}"
            nome = " ".join(tokens_raw[2:])
        elif tokens_raw[-2] in PREFISSI_COGNOME:
            cognome = f"{tokens_raw[-2]} {tokens_raw[-1]}"
            nome = " ".join(tokens_raw[:-2])
        elif tokens_raw[0] in TUTTI_NOMI_PROPRI and tokens_raw[-1] not in TUTTI_NOMI_PROPRI:
            # Es. "Maria Teresa Loporchio" -> Nome: Maria Teresa, Cognome: Loporchio
            cognome = tokens_raw[-1]
            nome = " ".join(tokens_raw[:-1])
        else:
            cognome = tokens_raw[0]
            nome = " ".join(tokens_raw[1:])

    nome_completo = f"{cognome} {nome}"

    # 4. Determinazione Sesso automatico per il calcolo del Codice Fiscale (+40 per le donne)
    primo_nome = nome.split()[0] if nome else "MARIO"
    if primo_nome in NOMI_FEMMINILI:
        sesso = "F"
    elif primo_nome in NOMI_MASCHILI:
        sesso = "M"
    else:
        sesso = "F" if primo_nome.endswith("A") and primo_nome not in {"LUCA", "ANDREA", "NICOLA", "MATTIA", "ELIA", "TOBIA"} else "M"

    cf_reale = calcola_cf_reale(cognome, nome, gg, mm, aaaa, sesso, catastale)

    return {
        "nome_assistito": nome_completo,
        "luogo_nascita": luogo_trovato.title(),
        "cf_assistito": cf_reale,
        "data_nascita": f"{gg:02d}/{mm:02d}/{aaaa}",
        "sesso": sesso,
        "indirizzo_assistito": f"{fake.street_address().upper()}"
    }

def trova_citta_smart(input_utente: str) -> str:
    pulito = input_utente.strip().lower()
    if pulito in CITTA_DB:
        return pulito
    matches = difflib.get_close_matches(pulito, list(CITTA_DB.keys()), n=1, cutoff=0.6)
    return matches[0] if matches else "foggia"

def risolvi_citta_e_medico(citta_input: str) -> dict:
    chiave = trova_citta_smart(citta_input)
    info = CITTA_DB[chiave]
    med = random.choice(info["medici"])
    reg_key = info["regione"]
    reg_info = REGIONI_DB[reg_key]

    return {
        "citta_pura": info["nome"],
        "cap": info["cap"],
        "prov": info["prov"],
        "nome_medico_bianca": f"{med['titolo']} {med['nome']}",
        "nome_medico_ssn": med["nome"],
        "cf_medico": med["cf"],
        "via_medico": med["via"],
        "tel_medico": med["tel"],
        "header_regione": reg_info["header"],
        "asl_cod": reg_info["asl_cod"],
        "prefisso_nre": reg_info["prefisso_nre"],
        "logo_file": reg_info["logo"]
    }

# ==========================================
# GENERATORI BARCODE (CODE 128) E PDF
# ==========================================
def genera_barcode_img(valore: str, nome_file_output: str, module_w: float = 0.25, module_h: float = 9.0) -> str:
    code128_class = barcode.get_barcode_class('code128')
    writer_options = {
        'write_text': False,
        'module_width': module_w,
        'module_height': module_h,
        'quiet_zone': 1.0
    }
    my_barcode = code128_class(str(valore).upper(), writer=ImageWriter())
    return my_barcode.save(os.path.join(OUTPUT_DIR, nome_file_output), options=writer_options)

def crea_pdf_ricetta_bianca(dati: dict, pdf_path: str, bc_cf_path: str, bc_farmaco_path: str):
    pdf = FPDF(orientation="P", unit="mm", format="A4")
    pdf.set_auto_page_break(False)
    pdf.add_page()

    pdf.set_xy(18, 22)
    pdf.set_font("Times", "B", 10.5)
    pdf.cell(0, 5, dati["nome_medico_bianca"], ln=True)
    
    pdf.set_x(18)
    pdf.set_font("Times", "I", 9.5)
    pdf.cell(0, 4.5, "Medicina Generale", ln=True)
    
    pdf.set_x(18)
    pdf.set_font("Times", "", 9.5)
    pdf.cell(0, 4.5, dati["via_medico"], ln=True)
    
    pdf.set_x(18)
    pdf.cell(0, 4.5, f"{dati['cap']} {dati['citta_pura']}", ln=True)
    
    pdf.set_x(18)
    pdf.cell(0, 4.5, f"({dati['prov']})", ln=True)
    
    pdf.set_x(18)
    pdf.cell(0, 4.5, f"Tel. {dati['tel_medico']}", ln=True)

    pdf.set_xy(18, 68)
    pdf.set_font("Times", "B", 9.5)
    pdf.cell(0, 5, "Assistito", ln=True)
    
    pdf.set_xy(18, 76)
    pdf.set_font("Times", "", 10)
    pdf.cell(0, 5, f"{dati['nome_assistito']} {dati['luogo_nascita'].upper()}", ln=True)

    pdf.set_xy(18, 94)
    pdf.set_font("Times", "", 9)
    pdf.cell(0, 5, "Codice Fiscale:", ln=True)
    pdf.image(bc_cf_path, x=24, y=100, w=72, h=13)

    pdf.set_xy(18, 126)
    pdf.set_font("Times", "B", 9.5)
    pdf.cell(0, 5, "Prescrizione:", ln=True)
    pdf.image(bc_farmaco_path, x=21, y=134, w=58, h=13)

    pdf.set_xy(95, 150)
    pdf.set_font("Times", "", 10)
    prefisso_qta = "" if dati["is_ripetibile"] else "N.1Conf. "
    pdf.cell(0, 5, f"{prefisso_qta}{dati['farmaco_nome']} ({dati['principio'].title()})", ln=True)
    
    pdf.set_x(95)
    pdf.cell(0, 5, dati["variante_label"], ln=True)
    
    pdf.set_x(102)
    pdf.cell(0, 5, dati["ripetibilita"], ln=True)

    pdf.set_xy(18, 178)
    pdf.set_font("Times", "", 9.5)
    pdf.cell(90, 5, f"{dati['citta_pura']}, {dati['data_emissione']}", ln=False)
    pdf.cell(60, 5, "Firma", align="C", ln=True)

    pdf.output(pdf_path)

def crea_pdf_ricetta_elettronica(dati: dict, pdf_path: str, bc_nre1_path: str, bc_nre2_path: str, bc_cf_path: str):
    pdf = FPDF(orientation="P", unit="mm", format="A4")
    pdf.set_auto_page_break(False)
    pdf.add_page()

    pdf.rect(10, 10, 190, 132)

    logo_path = os.path.join(ASSETS_DIR, dati["logo_file"])
    if os.path.exists(logo_path):
        pdf.image(logo_path, x=12, y=12, w=14)

    pdf.set_xy(28, 12)
    pdf.set_font("Helvetica", "B", 8.5)
    linee_reg = dati["header_regione"].splitlines()
    pdf.cell(65, 4, linee_reg[0], ln=True)
    pdf.set_x(28)
    pdf.cell(65, 4, linee_reg[1] if len(linee_reg) > 1 else "", ln=True)

    pdf.set_xy(95, 11)
    pdf.set_font("Helvetica", "B", 7.5)
    pdf.cell(100, 4, "RICETTA ELETTRONICA - PROMEMORIA PER L'ASSISTITO", align="R", ln=True)

    pdf.image(bc_nre1_path, x=98, y=16, w=32, h=8)
    pdf.image(bc_nre2_path, x=135, y=16, w=60, h=8)
    pdf.set_xy(98, 24.5)
    pdf.set_font("Helvetica", "", 7)
    pdf.cell(32, 3, f"*{dati['nre_part1']}*", align="C", ln=False)
    pdf.set_x(135)
    pdf.cell(60, 3, f"*{dati['nre_part2']}*", align="C", ln=True)

    pdf.line(10, 29, 200, 29)

    pdf.set_xy(12, 31)
    pdf.set_font("Helvetica", "B", 7.5)
    pdf.cell(110, 4, f"COGNOME E NOME/INIZIALI DELL'ASSISTITO: {dati['nome_assistito']}", ln=True)
    
    pdf.set_x(12)
    pdf.set_font("Helvetica", "", 7)
    pdf.cell(110, 4, f"INDIRIZZO: {dati['indirizzo_assistito']}", ln=True)
    
    pdf.set_x(12)
    pdf.cell(110, 4, f"CAP: {dati['cap']} CITTA': {dati['citta_pura'].upper()}   PROV: {dati['prov']}", ln=True)

    pdf.set_xy(125, 30)
    pdf.set_font("Helvetica", "B", 7.5)
    pdf.cell(70, 3.5, f"*{dati['cf_assistito']}*", align="C", ln=True)
    pdf.image(bc_cf_path, x=125, y=34, w=70, h=9)

    pdf.line(10, 45, 200, 45)
    pdf.set_xy(12, 46)
    pdf.set_font("Helvetica", "", 6.8)
    pdf.cell(65, 4, f"CODICE ASL: {dati['asl_cod']}", ln=False)
    pdf.cell(65, 4, f"SIGLA PROVINCIA: {dati['prov']}", ln=False)
    pdf.cell(55, 4, "ESENZIONE: NON ESENTE", ln=True)

    pdf.set_x(12)
    qta_box = "" if dati["is_ripetibile"] else "1"
    pdf.cell(65, 4, "TIPOLOGIA PRESCRIZIONE(S,H):", ln=False)
    pdf.cell(65, 4, "TIPO RICETTA: Assist. SSN", ln=False)
    pdf.cell(55, 4, f"N.CONFEZIONI/PRESTAZIONI: {qta_box}", ln=True)

    pdf.set_x(12)
    pdf.cell(65, 4, "PRIORITA' PRESCRIZIONE(U,B,D,P):", ln=False)
    pdf.cell(65, 4, "DISPOSIZIONI REGIONALI:", ln=False)
    pdf.cell(55, 4, "ALTRO:", ln=True)

    pdf.line(10, 59, 200, 59)
    pdf.set_xy(12, 60)
    pdf.cell(185, 4, "QUESITO DIAGNOSTICO:", ln=True)

    pdf.line(10, 65, 200, 65)
    pdf.set_xy(12, 66)
    pdf.set_font("Helvetica", "", 7)
    pdf.cell(95, 4, f"COGNOME E NOME DEL MEDICO: {dati['nome_medico_ssn']}", ln=False)
    pdf.cell(90, 4, f"CODICE FISCALE DEL MEDICO: {dati['cf_medico']}", ln=True)

    pdf.set_x(12)
    pdf.cell(95, 4, f"CODICE AUTENTICAZIONE: {dati['cod_autenticazione']}", ln=False)
    pdf.cell(90, 4, f"DATA: {dati['data_emissione']}", ln=True)

    pdf.line(10, 75, 200, 75)
    pdf.set_xy(12, 76)
    pdf.set_font("Helvetica", "B", 7.5)
    pdf.cell(150, 4.5, "PRESCRIZIONE", ln=False)
    pdf.cell(18, 4.5, "QTA", align="C", ln=False)
    pdf.cell(18, 4.5, "NOTA", align="C", ln=True)
    pdf.line(10, 81, 200, 81)

    pdf.set_xy(12, 83)
    pdf.set_font("Helvetica", "", 7.5)
    riga_farmaco = f"{dati['aic_farmaco']} {dati['ssn_str']}: {dati['principio']}; Pos: {dati['posologia']}"
    pdf.cell(150, 5, riga_farmaco, ln=False)
    pdf.cell(18, 5, qta_box, align="C", ln=False)
    pdf.cell(18, 5, "", align="C", ln=True)

    pdf.line(10, 128, 200, 128)
    pdf.set_xy(12, 130)
    pdf.set_font("Helvetica", "", 6)
    pdf.cell(150, 3.5, "Rilasciato ai sensi dell'art. 11, comma 16 del DL 31 mag 2010, n.78 e dell'art. 1, comma 4 del DM 2 nov 2011", ln=False)
    pdf.set_font("Helvetica", "B", 7)
    pdf.cell(35, 3.5, "TICKET", align="R", ln=True)

    pdf.output(pdf_path)

# ==========================================
# MACCHINA A STATI (FSM) E HANDLER TELEGRAM
# ==========================================
class FormPratica(StatesGroup):
    tipo_ricetta = State()
    paziente = State()
    citta = State()
    farmaco = State()
    variante = State()
    posologia = State()

def tastiera_principale() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📄 Nuova Pratica")],
            [KeyboardButton(text="💎 Stato Crediti & VIP")]
        ],
        resize_keyboard=True
    )

@dp.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    uid = message.from_user.id
    is_vip = uid in VIP_USERS
    crediti = carica_crediti().get(str(uid), 0)
    
    await message.answer(
        f"👋 **Benvenuto nel Sistema Prescrizioni Dinamico!**\n\n"
        f"🔹 **Stato VIP:** {'👑 Attivo (Illimitato)' if is_vip else '❌ Non attivo'}\n"
        f"🔹 **Crediti gratuiti:** `{crediti}`\n\n"
        f"Seleziona un'opzione dal menu sottostante (oppure invia in qualsiasi momento un codice promo):",
        reply_markup=tastiera_principale(),
        parse_mode="Markdown"
    )

@dp.message(F.text.lower() == FREE_PASS)
async def sblocca_crediti_global(message: Message):
    aggiungi_crediti_gratuiti(message.from_user.id, 3)
    tot = carica_crediti().get(str(message.from_user.id), 0)
    await message.answer(f"✅ **Codice '{FREE_PASS}' attivato!**\nHai ricevuto +3 crediti gratuiti (Totale: `{tot}`).", parse_mode="Markdown")

@dp.message(F.text.lower() == SECRET_PASS)
async def sblocca_vip_global(message: Message):
    salva_vip(message.from_user.id)
    VIP_USERS.add(message.from_user.id)
    await message.answer("👑 **Licenza Lifetime VIP sbloccata con successo!**\nGenerazioni illimitate attive.", parse_mode="Markdown")

@dp.message(F.text == "💎 Stato Crediti & VIP")
async def stato_crediti_handler(message: Message):
    uid = message.from_user.id
    is_vip = uid in VIP_USERS
    crediti = carica_crediti().get(str(uid), 0)
    await message.answer(
        f"📊 **Riepilogo Account**\n"
        f"• ID Utente: `{uid}`\n"
        f"• Licenza VIP: `{'ATTIVA' if is_vip else 'NON ATTIVA'}`\n"
        f"• Crediti residui: `{crediti}`\n\n"
        f"💰 **Listino Prezzi:**\n"
        f"• Benzodiazepine: `{PREZZO_BENZO}€`\n"
        f"• Oppioidi: `{PREZZO_OPPIOIDI}€`",
        parse_mode="Markdown"
    )

@dp.message(F.text == "📄 Nuova Pratica")
async def scegli_tipo_ricetta(message: Message, state: FSMContext):
    await state.set_state(FormPratica.tipo_ricetta)
    kb = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📋 Ricetta Bianca Classica"), KeyboardButton(text="🌐 Ricetta Elettronica (SSN)")],
            [KeyboardButton(text="❌ Annulla")]
        ],
        resize_keyboard=True
    )
    await message.answer("Seleziona la tipologia di ricetta che vuoi generare:", reply_markup=kb)

@dp.message(F.text == "❌ Annulla")
async def annulla_operazione(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Operazione annullata.", reply_markup=tastiera_principale())

@dp.message(FormPratica.tipo_ricetta, F.text.in_(["📋 Ricetta Bianca Classica", "🌐 Ricetta Elettronica (SSN)"]))
async def ricevi_tipo_ricetta(message: Message, state: FSMContext):
    is_elettronica = "Elettronica" in message.text
    await state.update_data(is_elettronica=is_elettronica)
    await state.set_state(FormPratica.paziente)
    kb = ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="❌ Annulla")]], resize_keyboard=True)
    await message.answer(
        "👤 **Dati Assistito**\nInserisci Nome, Cognome, Comune di nascita e Data di nascita in qualsiasi ordine (es. `Valentina Melchionda Bergamo 24/03/2006`):\n*(Il bot riordina automaticamente Cognome e Nome e calcola il vero Codice Fiscale)*",
        reply_markup=kb,
        parse_mode="Markdown"
    )

@dp.message(FormPratica.paziente)
async def ricevi_paziente(message: Message, state: FSMContext):
    info = analizza_input_paziente_smart(message.text)
    await state.update_data(**info)
    await state.set_state(FormPratica.citta)

    tasti_citta = []
    riga = []
    for k, val in CITTA_DB.items():
        if k not in CITTA_ESCLUSE_BOTTONI:
            riga.append(KeyboardButton(text=val["nome"]))
            if len(riga) == 3:
                tasti_citta.append(riga)
                riga = []
    if riga:
        tasti_citta.append(riga)
    tasti_citta.append([KeyboardButton(text="❌ Annulla")])

    kb = ReplyKeyboardMarkup(keyboard=tasti_citta, resize_keyboard=True)
    await message.answer(
        f"✅ **Assistito (Cognome Nome):** `{info['nome_assistito']}`\n"
        f"📍 **Luogo e Data di nascita:** `{info['luogo_nascita']} ({info['data_nascita']})`\n"
        f"🆔 **CF Calcolato:** `{info['cf_assistito']}`\n\n"
        f"🏥 **Seleziona o digita a mano la città di emissione della ricetta** (determina Medico, ASL, Regione e Logo):",
        reply_markup=kb,
        parse_mode="Markdown"
    )

@dp.message(FormPratica.citta)
async def ricevi_citta(message: Message, state: FSMContext):
    med_info = risolvi_citta_e_medico(message.text)
    await state.update_data(**med_info)
    await state.set_state(FormPratica.farmaco)

    tasti_farmaci = []
    riga = []
    for k in FARMACI_DB.keys():
        riga.append(KeyboardButton(text=k))
        if len(riga) == 3:
            tasti_farmaci.append(riga)
            riga = []
    if riga:
        tasti_farmaci.append(riga)
    tasti_farmaci.append([KeyboardButton(text="❌ Annulla")])

    kb = ReplyKeyboardMarkup(keyboard=tasti_farmaci, resize_keyboard=True)
    await message.answer(
        f"👨‍⚕️ Medico assegnato: `{med_info['nome_medico_bianca']}` ({med_info['citta_pura']} - {med_info['prov']})\n\n"
        f"💊 **Seleziona il farmaco da prescrivere:**",
        reply_markup=kb,
        parse_mode="Markdown"
    )

@dp.message(FormPratica.farmaco)
async def ricevi_farmaco(message: Message, state: FSMContext):
    txt = message.text.strip().upper()
    farmaco_chiave = "XANAX"
    for k in FARMACI_DB:
        if k in txt:
            farmaco_chiave = k
            break

    scheda = FARMACI_DB[farmaco_chiave]
    varianti = scheda["varianti"]

    await state.update_data(
        farmaco_chiave=farmaco_chiave,
        farmaco_nome=scheda["nome"],
        principio=scheda["principio"],
        prezzo_farmaco=scheda["prezzo"]
    )

    if len(varianti) == 1:
        var = varianti[0]
        await state.update_data(
            aic_farmaco=var["aic"],
            variante_label=var["label"],
            ssn_str=var["ssn_str"],
            ripetibilita=var["rip"],
            is_ripetibile=var["is_rip"]
        )
        await state.set_state(FormPratica.posologia)
        kb = ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="1 cpr die"), KeyboardButton(text="1 cpr prima di dormire")],
                [KeyboardButton(text="1 cpr e mezza die"), KeyboardButton(text="20 gocce al bisogno")],
                [KeyboardButton(text="❌ Annulla")]
            ],
            resize_keyboard=True
        )
        await message.answer("📝 **Seleziona o digita la posologia:**", reply_markup=kb, parse_mode="Markdown")
    else:
        await state.set_state(FormPratica.variante)
        tasti_var = [[KeyboardButton(text=v["label"])] for v in varianti]
        tasti_var.append([KeyboardButton(text="❌ Annulla")])
        kb = ReplyKeyboardMarkup(keyboard=tasti_var, resize_keyboard=True)
        await message.answer(f"📦 **Seleziona il dosaggio/formato per {scheda['nome']}:**", reply_markup=kb, parse_mode="Markdown")

@dp.message(FormPratica.variante)
async def ricevi_variante(message: Message, state: FSMContext):
    dati = await state.get_data()
    scheda = FARMACI_DB[dati["farmaco_chiave"]]
    scelta = message.text.strip().upper()
    
    var_scelta = scheda["varianti"][0]
    for v in scheda["varianti"]:
        if v["label"].upper() == scelta or scelta in v["label"].upper():
            var_scelta = v
            break

    await state.update_data(
        aic_farmaco=var_scelta["aic"],
        variante_label=var_scelta["label"],
        ssn_str=var_scelta["ssn_str"],
        ripetibilita=var_scelta["rip"],
        is_ripetibile=var_scelta["is_rip"]
    )
    await state.set_state(FormPratica.posologia)
    kb = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="1 cpr die"), KeyboardButton(text="1 cpr prima di dormire")],
            [KeyboardButton(text="1 cpr e mezza die"), KeyboardButton(text="20 gocce al bisogno")],
            [KeyboardButton(text="❌ Annulla")]
        ],
        resize_keyboard=True
    )
    await message.answer("📝 **Seleziona o digita la posologia:**", reply_markup=kb, parse_mode="Markdown")

@dp.message(FormPratica.posologia)
async def genera_documento_finale(message: Message, state: FSMContext):
    await state.update_data(posologia=message.text.strip())
    dati = await state.get_data()
    uid = message.from_user.id

    if uid not in VIP_USERS:
        if not scala_credito(uid):
            prezzo = dati["prezzo_farmaco"]
            await message.answer(
                f"⛔ **Crediti esauriti!**\n\n"
                f"Per generare la prescrizione per **{dati['farmaco_nome']}** (`{prezzo}€`), invia il pagamento in Bitcoin (BTC) al seguente wallet:\n\n"
                f"`{BTC_WALLET}`\n\n"
                f"💡 *Hai un codice promo? Invialo direttamente in chat per ricaricare i crediti o sbloccare il VIP.*",
                reply_markup=tastiera_principale(),
                parse_mode="Markdown"
            )
            await state.clear()
            return

    ora_attuale = datetime.now()
    dati["data_emissione"] = ora_attuale.strftime("%d/%m/%Y")
    timestamp = ora_attuale.strftime("%Y%m%d_%H%M%S")

    if dati["is_elettronica"]:
        dati["nre_part1"] = dati["prefisso_nre"]
        dati["nre_part2"] = f"{random.randint(1000000000, 9999999999)}"
        dati["cod_autenticazione"] = f"{ora_attuale.strftime('%d%m%Y%H%M%S')}{random.randint(1000000000000000, 9999999999999999)}"

        bc_nre1 = genera_barcode_img(dati["nre_part1"], f"nre1_{timestamp}", module_w=0.25, module_h=7.0)
        bc_nre2 = genera_barcode_img(dati["nre_part2"], f"nre2_{timestamp}", module_w=0.25, module_h=7.0)
        bc_cf = genera_barcode_img(dati["cf_assistito"], f"cf_ssn_{timestamp}", module_w=0.25, module_h=8.0)

        nome_pdf = f"{dati['nre_part1']}{dati['nre_part2']}.pdf"
        pdf_path = os.path.join(OUTPUT_DIR, nome_pdf)
        crea_pdf_ricetta_elettronica(dati, pdf_path, bc_nre1, bc_nre2, bc_cf)

        await message.answer_document(
            FSInputFile(pdf_path),
            caption=(
                f"✅ **Promemoria Ricetta Elettronica (SSN) generato!**\n"
                f"🏛 `{dati['header_regione'].splitlines()[-1]}`\n"
                f"🔢 NRE: `{dati['nre_part1']}{dati['nre_part2']}`\n"
                f"👨‍⚕️ Medico: `{dati['nome_medico_ssn']}`"
            ),
            reply_markup=tastiera_principale(),
            parse_mode="Markdown"
        )
    else:
        bc_cf = genera_barcode_img(dati["cf_assistito"], f"cf_b_{timestamp}", module_w=0.28, module_h=10.0)
        bc_farmaco = genera_barcode_img(dati["aic_farmaco"], f"aic_b_{timestamp}", module_w=0.28, module_h=10.0)

        nome_pdf = f"DOC_{timestamp}.pdf"
        pdf_path = os.path.join(OUTPUT_DIR, nome_pdf)
        crea_pdf_ricetta_bianca(dati, pdf_path, bc_cf, bc_farmaco)

        await message.answer_document(
            FSInputFile(pdf_path),
            caption=(
                f"✅ **Ricetta Bianca Classica generata!**\n"
                f"👨‍⚕️ Medico: `{dati['nome_medico_bianca']}`\n"
                f"💊 Farmaco: `{dati['farmaco_nome']} ({dati['variante_label']})`"
            ),
            reply_markup=tastiera_principale(),
            parse_mode="Markdown"
        )

    await state.clear()

async def health_check(request):
    return web.Response(text="Bot Ricette Service Operational 24/7.")

async def main():
    await aggiorna_cache_comuni()
    app = web.Application()
    app.router.add_get("/", health_check)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 10000))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
