from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from sqlalchemy import create_engine, text
from sqlalchemy.exc import NoResultFound
from datetime import date as dt_date, datetime, timezone
import json
import os
from pathlib import Path
import re
import ssl
import time
import unicodedata
from urllib import error, request
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

app = FastAPI()
BASE_DIR = Path(__file__).resolve().parent
PROJECT_DIR = BASE_DIR.parent
FRONTEND_DIR = PROJECT_DIR / "frontend"

DEFAULT_SQLITE_URL = f"sqlite:///{BASE_DIR / 'dock.db'}"

def normalize_database_url(raw_url: str | None) -> str:
    url = (raw_url or DEFAULT_SQLITE_URL).strip()
    if url.startswith("postgres://"):
        return f"postgresql+psycopg://{url[len('postgres://'):]}"
    if url.startswith("postgresql://"):
        return f"postgresql+psycopg://{url[len('postgresql://'):]}"
    return url

def load_app_timezone(raw_timezone: str | None):
    timezone_name = (raw_timezone or "America/Sao_Paulo").strip() or "America/Sao_Paulo"
    try:
        return ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError:
        return timezone.utc

def resolve_ai_provider(raw_provider: str | None, openai_key: str | None) -> str:
    provider = (raw_provider or "auto").strip().lower()
    if provider in {"", "auto"}:
        return "openai" if openai_key else "disabled"
    if provider == "openai":
        return "openai" if openai_key else "disabled"
    if provider == "ollama":
        return "ollama"
    if provider in {"disabled", "none", "rules", "fallback"}:
        return "disabled"
    return "disabled"

def build_engine(database_url: str):
    engine_kwargs: dict = {}
    if database_url.startswith("sqlite"):
        engine_kwargs["connect_args"] = {"check_same_thread": False}
    else:
        engine_kwargs["pool_pre_ping"] = True
    return create_engine(database_url, **engine_kwargs)

DATABASE_URL = normalize_database_url(os.getenv("DATABASE_URL", DEFAULT_SQLITE_URL))
OLLAMA_URL = "http://127.0.0.1:11434/api/generate"
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:0.5b")
CHAT_HISTORY_LIMIT = 2
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
AI_PROVIDER = resolve_ai_provider(os.getenv("AI_PROVIDER"), OPENAI_API_KEY)
OPENAI_URL = "https://api.openai.com/v1/responses"
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
OPENAI_CHAT_MAX_OUTPUT_TOKENS = 220
CHAT_TIMEOUT_SECONDS = int(os.getenv("CHAT_TIMEOUT_SECONDS", "12"))
AI_TIMEOUT_SECONDS = int(os.getenv("AI_TIMEOUT_SECONDS", "15"))
LIVE_DATA_TIMEOUT_SECONDS = int(os.getenv("LIVE_DATA_TIMEOUT_SECONDS", "8"))
DB_INIT_MAX_ATTEMPTS = int(os.getenv("DB_INIT_MAX_ATTEMPTS", "12"))
DB_INIT_RETRY_SECONDS = float(os.getenv("DB_INIT_RETRY_SECONDS", "2"))
APP_TIMEZONE = load_app_timezone(os.getenv("APP_TIMEZONE"))
APP_TIMEZONE_NAME = getattr(APP_TIMEZONE, "key", "UTC")

SYSTEM_PROMPT = """
Você é Dock, a inteligência pessoal do usuário.
Responda sempre em português do Brasil.
Fale de forma natural, útil, específica e humana.
Nunca fale como chatbot genérico, assistente genérico, sistema ou modelo.
Nunca diga que tem gostos, história pessoal ou preferências próprias.
Se faltarem dados para agir com segurança, faça uma pergunta curta e objetiva.
Quando a pergunta for aberta, responda com clareza prática e próximo passo.
Quando o usuário estiver confuso, ajude a organizar, decidir e executar.
Na maioria dos casos, responda em 2 a 4 frases.
"""

engine = build_engine(DATABASE_URL)
app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")
IS_SQLITE = engine.dialect.name == "sqlite"

def init_db() -> None:
    with engine.begin() as conn:
        if IS_SQLITE:
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS entries (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    text TEXT NOT NULL,
                    category TEXT NOT NULL,
                    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
            """))
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS habits (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    target_frequency INTEGER NOT NULL DEFAULT 7,
                    unit TEXT NOT NULL DEFAULT 'vezes/semana',
                    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
            """))
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS habit_checkins (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    habit_id INTEGER NOT NULL,
                    checkin_date DATE NOT NULL,
                    value INTEGER NOT NULL DEFAULT 1,
                    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE (habit_id, checkin_date)
                )
            """))
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS study_sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    subject TEXT NOT NULL,
                    duration_minutes INTEGER NOT NULL,
                    studied_on DATE NOT NULL,
                    notes TEXT NOT NULL DEFAULT '',
                    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
            """))
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS finance_entries (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    kind TEXT NOT NULL,
                    category TEXT NOT NULL,
                    amount NUMERIC(12,2) NOT NULL,
                    occurred_on DATE NOT NULL,
                    note TEXT NOT NULL DEFAULT '',
                    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
            """))
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS dock_memory (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    entity_type TEXT NOT NULL,
                    canonical_name TEXT NOT NULL,
                    aliases TEXT NOT NULL DEFAULT '[]',
                    metadata TEXT NOT NULL DEFAULT '{}',
                    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE (entity_type, canonical_name)
                )
            """))
        else:
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS entries (
                    id SERIAL PRIMARY KEY,
                    text TEXT NOT NULL,
                    category TEXT NOT NULL,
                    created_at TIMESTAMP NOT NULL DEFAULT NOW()
                )
            """))
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS habits (
                    id SERIAL PRIMARY KEY,
                    name TEXT NOT NULL,
                    target_frequency INTEGER NOT NULL DEFAULT 7,
                    unit TEXT NOT NULL DEFAULT 'vezes/semana',
                    created_at TIMESTAMP NOT NULL DEFAULT NOW()
                )
            """))
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS habit_checkins (
                    id SERIAL PRIMARY KEY,
                    habit_id INTEGER NOT NULL REFERENCES habits(id) ON DELETE CASCADE,
                    checkin_date DATE NOT NULL,
                    value INTEGER NOT NULL DEFAULT 1,
                    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
                    UNIQUE (habit_id, checkin_date)
                )
            """))
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS study_sessions (
                    id SERIAL PRIMARY KEY,
                    subject TEXT NOT NULL,
                    duration_minutes INTEGER NOT NULL,
                    studied_on DATE NOT NULL,
                    notes TEXT NOT NULL DEFAULT '',
                    created_at TIMESTAMP NOT NULL DEFAULT NOW()
                )
            """))
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS finance_entries (
                    id SERIAL PRIMARY KEY,
                    kind TEXT NOT NULL,
                    category TEXT NOT NULL,
                    amount NUMERIC(12,2) NOT NULL,
                    occurred_on DATE NOT NULL,
                    note TEXT NOT NULL DEFAULT '',
                    created_at TIMESTAMP NOT NULL DEFAULT NOW()
                )
            """))
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS dock_memory (
                    id SERIAL PRIMARY KEY,
                    entity_type TEXT NOT NULL,
                    canonical_name TEXT NOT NULL,
                    aliases TEXT NOT NULL DEFAULT '[]',
                    metadata TEXT NOT NULL DEFAULT '{}',
                    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
                    UNIQUE (entity_type, canonical_name)
                )
            """))

def init_db_with_retry() -> None:
    last_error: Exception | None = None
    for attempt in range(1, DB_INIT_MAX_ATTEMPTS + 1):
        try:
            init_db()
            return
        except Exception as exc:
            last_error = exc
            if attempt == DB_INIT_MAX_ATTEMPTS:
                break
            print(
                f"Dock database init failed on attempt {attempt}/{DB_INIT_MAX_ATTEMPTS}. "
                f"Retrying in {DB_INIT_RETRY_SECONDS:.1f}s."
            )
            time.sleep(DB_INIT_RETRY_SECONDS)
    raise RuntimeError("Dock could not initialize the database connection.") from last_error

@app.on_event("startup")
def startup_init() -> None:
    init_db_with_retry()

class Entry(BaseModel):
    text: str

class Message(BaseModel):
    role: str
    content: str

class LocationContext(BaseModel):
    latitude: float
    longitude: float
    city: str | None = None
    region: str | None = None

class ChatRequest(BaseModel):
    message: str
    history: list[Message] = Field(default_factory=list)
    location: LocationContext | None = None

class HabitCreate(BaseModel):
    name: str
    target_frequency: int = 7
    unit: str = "vezes/semana"

class HabitCheckInCreate(BaseModel):
    date: dt_date | None = None
    value: int = 1

class HabitUpdate(BaseModel):
    name: str | None = None
    target_frequency: int | None = None
    unit: str | None = None

class StudySessionCreate(BaseModel):
    subject: str
    duration_minutes: int
    studied_on: dt_date | None = None
    notes: str = ""

class StudySessionUpdate(BaseModel):
    subject: str | None = None
    duration_minutes: int | None = None
    notes: str | None = None

class FinanceEntryCreate(BaseModel):
    kind: str
    category: str
    amount: float
    occurred_on: dt_date | None = None
    note: str = ""

class FinanceEntryUpdate(BaseModel):
    category: str | None = None
    amount: float | None = None
    note: str | None = None

class ChatAction(BaseModel):
    action_type: str
    kind: str | None = None
    category: str | None = None
    amount: float | None = None
    subject: str | None = None
    duration_minutes: int | None = None
    habit_name: str | None = None
    note: str = ""
    target_id: int | None = None
    target_hint: str | None = None

def strip_code_fences(text: str) -> str:
    if text.startswith("```"):
        lines = text.splitlines()
        text = "\n".join(
            line for line in lines
            if not line.strip().startswith("```")
        ).strip()
    return text

def normalize_text(text: str) -> str:
    text = unicodedata.normalize("NFKD", text.strip().lower())
    text = "".join(char for char in text if not unicodedata.combining(char))
    return " ".join(text.split())

def contains_any(text: str, terms: set[str]) -> bool:
    return any(term in text for term in terms)

def titleize_label(text: str) -> str:
    cleaned = " ".join(text.strip().split())
    if not cleaned:
        return cleaned
    return " ".join(part.capitalize() for part in cleaned.split())

def post_json(url: str, payload: dict, headers: dict | None = None, timeout: int = 60) -> dict:
    req = request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", **(headers or {})},
        method="POST",
    )
    with request.urlopen(req, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))

def get_json(url: str, headers: dict | None = None, timeout: int = 30) -> dict:
    req = request.Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": "Dock/1.0 (+https://dock.local)",
            **(headers or {}),
        },
        method="GET",
    )
    try:
        with request.urlopen(req, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except error.URLError as exc:
        ssl_error = getattr(exc, "reason", None)
        if not isinstance(ssl_error, ssl.SSLCertVerificationError):
            raise

        insecure_context = ssl._create_unverified_context()
        with request.urlopen(req, timeout=timeout, context=insecure_context) as response:
            return json.loads(response.read().decode("utf-8"))

def call_ollama(prompt: str, timeout: int = 60) -> str:
    payload = {
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": 0.5,
            "num_predict": 160,
        },
    }
    body = post_json(OLLAMA_URL, payload, timeout=timeout)
    return body["response"].strip()

def call_openai(prompt: str, timeout: int = 60) -> str:
    if not OPENAI_API_KEY:
        raise ValueError("OPENAI_API_KEY not configured")

    payload = {
        "model": OPENAI_MODEL,
        "input": prompt,
    }
    headers = {"Authorization": f"Bearer {OPENAI_API_KEY}"}
    body = post_json(OPENAI_URL, payload, headers=headers, timeout=timeout)
    output = body.get("output", [])
    for item in output:
        if item.get("type") != "message":
            continue
        for content in item.get("content", []):
            if content.get("type") == "output_text":
                return content.get("text", "").strip()
    raise KeyError("OpenAI response had no output_text")

def call_openai_chat(messages: list[dict], timeout: int = CHAT_TIMEOUT_SECONDS) -> str:
    if not OPENAI_API_KEY:
        raise ValueError("OPENAI_API_KEY not configured")

    payload = {
        "model": OPENAI_MODEL,
        "instructions": SYSTEM_PROMPT.strip(),
        "input": messages,
        "max_output_tokens": OPENAI_CHAT_MAX_OUTPUT_TOKENS,
    }
    headers = {"Authorization": f"Bearer {OPENAI_API_KEY}"}
    body = post_json(OPENAI_URL, payload, headers=headers, timeout=timeout)
    output = body.get("output", [])
    for item in output:
        if item.get("type") != "message":
            continue
        for content in item.get("content", []):
            if content.get("type") == "output_text":
                return content.get("text", "").strip()
    raise KeyError("OpenAI response had no output_text")

def generate_text(prompt: str, timeout: int = 60) -> tuple[str, str, str | None]:
    if AI_PROVIDER == "openai":
        return call_openai(prompt, timeout=timeout), "openai", OPENAI_MODEL
    if AI_PROVIDER == "ollama":
        return call_ollama(prompt, timeout=timeout), "ollama", OLLAMA_MODEL
    raise ValueError("AI provider disabled")

def format_brl(value: float) -> str:
    formatted = f"{value:,.2f}"
    return f"R$ {formatted.replace(',', 'X').replace('.', ',').replace('X', '.')}"

def format_usd(value: float) -> str:
    formatted = f"{value:,.2f}"
    return f"US$ {formatted}"

def parse_amount_from_text(text: str) -> float | None:
    matches = re.findall(
        r"(?:r\$\s*)?(\d{1,3}(?:[.,]\d{3})+(?:[.,]\d{1,2})?|\d+(?:[.,]\d{1,2})?)",
        text,
    )
    if not matches:
        return None
    raw = matches[0].strip()
    if "," in raw and "." in raw:
        if raw.rfind(",") > raw.rfind("."):
            raw = raw.replace(".", "").replace(",", ".")
        else:
            raw = raw.replace(",", "")
    elif "," in raw:
        raw = raw.replace(".", "").replace(",", ".")
    elif raw.count(".") > 1:
        raw = raw.replace(".", "")
    try:
        return round(float(raw), 2)
    except ValueError:
        return None

def parse_duration_minutes(text: str) -> int | None:
    hour_match = re.search(r"(\d+)\s*(h|hora|horas)\b", text)
    minute_match = re.search(r"(\d+)\s*(min|minuto|minutos)\b", text)
    total = 0
    if hour_match:
        total += int(hour_match.group(1)) * 60
    if minute_match:
        total += int(minute_match.group(1))
    if total:
        return total
    bare_minutes = re.search(r"(\d+)\s*$", text)
    if bare_minutes and contains_any(text, {"estudei", "estudo", "estudar"}):
        return int(bare_minutes.group(1))
    return None

def infer_finance_category(normalized_message: str) -> str:
    category_map = {
        "ifood": "Ifood",
        "uber": "Uber",
        "mercado": "Mercado",
        "supermercado": "Mercado",
        "aluguel": "Aluguel",
        "farmacia": "Farmácia",
        "remedio": "Farmácia",
        "gasolina": "Transporte",
        "combustivel": "Transporte",
        "restaurante": "Alimentação",
        "lanchonete": "Alimentação",
        "lanche": "Alimentação",
        "academia": "Academia",
        "salario": "Salário",
        "freela": "Freela",
        "pix": "Pix",
    }
    for keyword, label in category_map.items():
        if keyword in normalized_message:
            return label

    merchant_match = re.search(r"\b(?:no|na|em|pro|pra|para|de)\s+([a-z0-9 ]{2,40})$", normalized_message)
    if merchant_match:
        candidate = merchant_match.group(1).strip()
        candidate = re.sub(r"\bhoje\b", "", candidate).strip()
        if candidate:
            return titleize_label(candidate)

    if contains_any(normalized_message, {"recebi", "ganhei"}):
        return "Receita"
    return "Geral"

def infer_study_subject(normalized_message: str) -> str:
    subject_map = {
        "matematica": "Matemática",
        "fisica": "Física",
        "quimica": "Química",
        "historia": "História",
        "geografia": "Geografia",
        "ingles": "Inglês",
        "espanhol": "Espanhol",
        "programacao": "Programação",
        "python": "Python",
        "javascript": "JavaScript",
    }
    for keyword, label in subject_map.items():
        if keyword in normalized_message:
            return label

    match = re.search(r"\b(?:estudei|estudar|estudo)\s+(.+?)(?:\s+\d+\s*(?:h|hora|horas|min|minuto|minutos)\b|$)", normalized_message)
    if match:
        candidate = match.group(1).strip()
        candidate = re.sub(r"\bhoje\b", "", candidate).strip()
        if candidate:
            return titleize_label(candidate)
    return "Estudo"

def infer_habit_name(normalized_message: str) -> str | None:
    habit_map = {
        "academia": "Academia",
        "treinei": "Treino",
        "malhei": "Treino",
        "corri": "Corrida",
        "caminhei": "Caminhada",
        "nadei": "Natação",
        "pedalei": "Bike",
        "meditei": "Meditação",
        "livro": "Leitura",
        "leitura": "Leitura",
        "lembrei de ler": "Leitura",
        "estudei": "Estudo",
        "bebi agua": "Água",
    }
    for keyword, label in habit_map.items():
        if keyword in normalized_message:
            return label
    return None

def build_habit_aliases() -> dict[str, set[str]]:
    return {
        "academia": {"academia", "treino", "malhar", "malhei", "exercicio", "exercicios"},
        "treino": {"treino", "treinei", "academia", "malhei"},
        "corrida": {"corrida", "corri", "correr"},
        "caminhada": {"caminhada", "caminhei", "caminhar"},
        "natacao": {"natacao", "nadei", "nadar"},
        "bike": {"bike", "pedalei", "pedalar", "ciclismo"},
        "meditacao": {"meditacao", "meditei", "meditar"},
        "leitura": {"leitura", "ler", "livro", "li um livro"},
        "estudo": {"estudo", "estudei", "estudar"},
        "agua": {"agua", "bebi agua", "hidratar", "hidratacao"},
    }

def tokenize_normalized_text(text: str) -> set[str]:
    tokens = {token for token in re.split(r"[^a-z0-9]+", normalize_text(text)) if token}
    singular_tokens = set()
    for token in tokens:
        if token.endswith("s") and len(token) > 3:
            singular_tokens.add(token[:-1])
    return tokens | singular_tokens

def aliases_to_json(aliases: set[str]) -> str:
    cleaned = sorted({normalize_text(alias) for alias in aliases if alias and normalize_text(alias)})
    return json.dumps(cleaned, ensure_ascii=True)

def metadata_to_json(metadata: dict) -> str:
    return json.dumps(metadata, ensure_ascii=True)

def load_memory_records(entity_type: str) -> list[dict]:
    with engine.connect() as conn:
        rows = conn.execute(text("""
            SELECT id, entity_type, canonical_name, aliases, metadata, created_at, updated_at
            FROM dock_memory
            WHERE entity_type = :entity_type
            ORDER BY updated_at DESC, id DESC
        """), {"entity_type": entity_type}).mappings().all()
    result = []
    for row in rows:
        item = dict(row)
        try:
            item["aliases"] = json.loads(item.get("aliases") or "[]")
        except json.JSONDecodeError:
            item["aliases"] = []
        try:
            item["metadata"] = json.loads(item.get("metadata") or "{}")
        except json.JSONDecodeError:
            item["metadata"] = {}
        result.append(item)
    return result

def remember_entity(entity_type: str, canonical_name: str, aliases: set[str] | None = None, metadata: dict | None = None) -> None:
    aliases = aliases or set()
    metadata = metadata or {}
    alias_payload = aliases_to_json(set(aliases) | {canonical_name})
    metadata_payload = metadata_to_json(metadata)
    with engine.begin() as conn:
        if IS_SQLITE:
            conn.execute(text("""
                INSERT INTO dock_memory (entity_type, canonical_name, aliases, metadata, updated_at)
                VALUES (:entity_type, :canonical_name, :aliases, :metadata, CURRENT_TIMESTAMP)
                ON CONFLICT (entity_type, canonical_name)
                DO UPDATE SET
                    aliases = excluded.aliases,
                    metadata = excluded.metadata,
                    updated_at = CURRENT_TIMESTAMP
            """), {
                "entity_type": entity_type,
                "canonical_name": canonical_name,
                "aliases": alias_payload,
                "metadata": metadata_payload,
            })
        else:
            conn.execute(text("""
                INSERT INTO dock_memory (entity_type, canonical_name, aliases, metadata, updated_at)
                VALUES (:entity_type, :canonical_name, :aliases, :metadata, NOW())
                ON CONFLICT (entity_type, canonical_name)
                DO UPDATE SET
                    aliases = excluded.aliases,
                    metadata = excluded.metadata,
                    updated_at = NOW()
            """), {
                "entity_type": entity_type,
                "canonical_name": canonical_name,
                "aliases": alias_payload,
                "metadata": metadata_payload,
            })

def score_memory_match(memory: dict, candidate_name: str, normalized_message: str) -> int:
    candidate_normalized = normalize_text(candidate_name)
    canonical_normalized = normalize_text(memory["canonical_name"])
    aliases = {normalize_text(alias) for alias in memory.get("aliases", [])}
    message_tokens = tokenize_normalized_text(normalized_message)

    score = 0
    if candidate_normalized == canonical_normalized:
        score += 100
    if candidate_normalized in aliases:
        score += 85
    if aliases & message_tokens:
        score += 30
    if canonical_normalized in message_tokens:
        score += 20
    return score

def list_habits_raw() -> list[dict]:
    with engine.connect() as conn:
        rows = conn.execute(text("""
            SELECT id, name, target_frequency, unit, created_at
            FROM habits
            ORDER BY created_at DESC, id DESC
        """)).mappings().all()
    return [dict(row) for row in rows]

def score_habit_match(existing_name: str, candidate_name: str, normalized_message: str) -> int:
    existing_normalized = normalize_text(existing_name)
    candidate_normalized = normalize_text(candidate_name)
    if existing_normalized == candidate_normalized:
        return 100

    aliases = build_habit_aliases()
    existing_aliases = aliases.get(existing_normalized, {existing_normalized})
    candidate_aliases = aliases.get(candidate_normalized, {candidate_normalized})
    message_tokens = tokenize_normalized_text(normalized_message)
    existing_tokens = tokenize_normalized_text(existing_name)

    score = 0
    if existing_aliases & candidate_aliases:
        score += 60
    if message_tokens & existing_aliases:
        score += 30
    if message_tokens & existing_tokens:
        score += 20
    if candidate_normalized in existing_aliases:
        score += 15
    return score

def extract_chat_action(message: str, normalized_message: str) -> ChatAction | None:
    amount = parse_amount_from_text(normalized_message)
    duration_minutes = parse_duration_minutes(normalized_message)

    if contains_any(normalized_message, {"edita", "editar", "corrige", "corrigir", "altera", "alterar", "atualiza", "atualizar"}):
        if amount is not None and contains_any(normalized_message, {"lancamento", "gasto", "despesa", "receita", "ifood", "mercado", "uber"}):
            return ChatAction(
                action_type="finance_edit",
                amount=amount,
                category=infer_finance_category(normalized_message),
                note=message.strip(),
            )

    if contains_any(normalized_message, {"gastei", "paguei", "comprei"}) and amount is not None:
        return ChatAction(
            action_type="finance_entry",
            kind="expense",
            category=infer_finance_category(normalized_message),
            amount=amount,
            note=message.strip(),
        )

    if contains_any(normalized_message, {"recebi", "ganhei"}) and amount is not None:
        return ChatAction(
            action_type="finance_entry",
            kind="income",
            category=infer_finance_category(normalized_message),
            amount=amount,
            note=message.strip(),
        )

    if contains_any(normalized_message, {"estudei", "estudo"}) and duration_minutes is not None:
        return ChatAction(
            action_type="study_session",
            subject=infer_study_subject(normalized_message),
            duration_minutes=duration_minutes,
            note=message.strip(),
        )

    habit_name = infer_habit_name(normalized_message)
    if habit_name is not None and contains_any(normalized_message, {
        "fui pra academia", "fui para academia", "treinei", "treino feito", "malhei",
        "corri", "caminhei", "nadei", "pedalei", "meditei", "bebi agua",
        "fiz exercicio", "fiz exercicios", "li um livro", "fiz leitura"
    }):
        return ChatAction(
            action_type="habit_checkin",
            habit_name=habit_name,
            note=message.strip(),
        )

    return None

def create_habit_record(name: str, target_frequency: int = 7, unit: str = "vezes/semana") -> dict:
    with engine.begin() as conn:
        row = conn.execute(text("""
            INSERT INTO habits (name, target_frequency, unit)
            VALUES (:name, :target_frequency, :unit)
            RETURNING id, name, target_frequency, unit, created_at
        """), {
            "name": name.strip(),
            "target_frequency": target_frequency,
            "unit": unit.strip() or "vezes/semana",
        }).mappings().one()
    record = dict(row)
    remember_entity("habit", record["name"], {name, normalize_text(name)})
    return record

def get_habit_by_name(name: str) -> dict | None:
    desired = normalize_text(name)
    habits = list_habits_raw()
    for habit in habits:
        if normalize_text(habit["name"]) == desired:
            return habit
    return None

def find_matching_habit(name: str, normalized_message: str) -> dict | None:
    habits = list_habits_raw()
    if not habits:
        return None

    scored: list[tuple[int, dict]] = []
    for habit in habits:
        score = score_habit_match(habit["name"], name, normalized_message)
        if score > 0:
            scored.append((score, habit))

    if not scored:
        return None

    scored.sort(key=lambda item: (-item[0], -int(item[1]["id"])))
    best_score, best_habit = scored[0]
    if best_score >= 60:
        return best_habit
    return None

def resolve_habit_candidate(name: str, normalized_message: str) -> tuple[str, dict | None]:
    exact = get_habit_by_name(name)
    if exact is not None:
        return "matched", exact

    matched = find_matching_habit(name, normalized_message)
    if matched is not None:
        return "matched", matched

    memories = load_memory_records("habit")
    scored_memories: list[tuple[int, dict]] = []
    for memory in memories:
        score = score_memory_match(memory, name, normalized_message)
        if score > 0:
            scored_memories.append((score, memory))
    if scored_memories:
        scored_memories.sort(key=lambda item: -item[0])
        best_score, best_memory = scored_memories[0]
        if best_score >= 85:
            memory_habit = get_habit_by_name(best_memory["canonical_name"])
            if memory_habit is not None:
                return "matched", memory_habit
        if best_score >= 45:
            memory_habit = get_habit_by_name(best_memory["canonical_name"])
            if memory_habit is not None:
                return "needs_confirmation", memory_habit

    return "create", None

def ensure_habit_exists(name: str, normalized_message: str = "") -> dict:
    status, habit = resolve_habit_candidate(name, normalized_message)
    if status in {"matched", "needs_confirmation"} and habit is not None:
        return habit
    created = create_habit_record(name)
    remember_entity("habit", created["name"], {name, normalize_text(name)})
    return created

def raise_not_found_error(label: str) -> None:
    raise HTTPException(status_code=404, detail=f"{label} não encontrado.")

def create_habit_checkin_record(habit_id: int, value: int = 1, checkin_date: dt_date | None = None) -> dict:
    checkin_date = checkin_date or today_local()
    with engine.begin() as conn:
        habit_exists = conn.execute(
            text("SELECT 1 FROM habits WHERE id = :habit_id"),
            {"habit_id": habit_id},
        ).first()
        if habit_exists is None:
            raise_not_found_error("Hábito")
        conn.execute(text("""
            INSERT INTO habit_checkins (habit_id, checkin_date, value)
            VALUES (:habit_id, :checkin_date, :value)
            ON CONFLICT (habit_id, checkin_date)
            DO UPDATE SET value = EXCLUDED.value
        """), {
            "habit_id": habit_id,
            "checkin_date": checkin_date,
            "value": value,
        })
    return {"habit_id": habit_id, "checkin_date": checkin_date.isoformat(), "value": value}

def create_study_session_record(subject: str, duration_minutes: int, studied_on: dt_date | None = None, notes: str = "") -> dict:
    studied_on = studied_on or today_local()
    with engine.begin() as conn:
        row = conn.execute(text("""
            INSERT INTO study_sessions (subject, duration_minutes, studied_on, notes)
            VALUES (:subject, :duration_minutes, :studied_on, :notes)
            RETURNING id, subject, duration_minutes, studied_on, notes, created_at
        """), {
            "subject": subject.strip(),
            "duration_minutes": duration_minutes,
            "studied_on": studied_on,
            "notes": notes.strip(),
        }).mappings().one()
    record = dict(row)
    remember_entity("study_subject", record["subject"], {subject, normalize_text(subject)})
    return record

def create_finance_entry_record(kind: str, category: str, amount: float, occurred_on: dt_date | None = None, note: str = "") -> dict:
    kind = kind.strip().lower()
    occurred_on = occurred_on or today_local()
    with engine.begin() as conn:
        row = conn.execute(text("""
            INSERT INTO finance_entries (kind, category, amount, occurred_on, note)
            VALUES (:kind, :category, :amount, :occurred_on, :note)
            RETURNING id, kind, category, amount, occurred_on, note, created_at
        """), {
            "kind": kind,
            "category": category.strip(),
            "amount": round(amount, 2),
            "occurred_on": occurred_on,
            "note": note.strip(),
        }).mappings().one()
    record = dict(row)
    remember_entity("finance_category", record["category"], {category, normalize_text(category)})
    return record

def fetch_latest_finance_entry(category: str | None = None) -> dict | None:
    with engine.connect() as conn:
        rows = conn.execute(text("""
            SELECT id, kind, category, amount, occurred_on, note, created_at
            FROM finance_entries
            ORDER BY occurred_on DESC, id DESC
            LIMIT 50
        """)).mappings().all()
    if not rows:
        return None
    if not category:
        return dict(rows[0])
    desired_category = normalize_text(category)
    for row in rows:
        if normalize_text(row["category"]) == desired_category:
            return dict(row)
    return None

def update_finance_entry_record(entry_id: int, amount: float | None = None, category: str | None = None, note: str | None = None) -> dict:
    try:
        with engine.begin() as conn:
            existing = conn.execute(text("""
                SELECT id, kind, category, amount, occurred_on, note, created_at
                FROM finance_entries
                WHERE id = :entry_id
            """), {"entry_id": entry_id}).mappings().one()
            new_category = category.strip() if category and category != "Geral" else existing["category"]
            new_amount = round(amount if amount is not None else float(existing["amount"]), 2)
            new_note = note.strip() if note else existing["note"]
            row = conn.execute(text("""
                UPDATE finance_entries
                SET category = :category, amount = :amount, note = :note
                WHERE id = :entry_id
                RETURNING id, kind, category, amount, occurred_on, note, created_at
            """), {
                "entry_id": entry_id,
                "category": new_category,
                "amount": new_amount,
                "note": new_note,
            }).mappings().one()
    except NoResultFound as exc:
        raise_not_found_error("Lançamento financeiro")
    record = dict(row)
    remember_entity("finance_category", record["category"], {record["category"], normalize_text(record["category"])})
    return record

def update_habit_record(habit_id: int, payload: HabitUpdate) -> dict:
    try:
        with engine.begin() as conn:
            existing = conn.execute(text("""
                SELECT id, name, target_frequency, unit, created_at
                FROM habits
                WHERE id = :habit_id
            """), {"habit_id": habit_id}).mappings().one()
            new_name = payload.name.strip() if payload.name else existing["name"]
            new_target = payload.target_frequency if payload.target_frequency is not None else existing["target_frequency"]
            new_unit = payload.unit.strip() if payload.unit else existing["unit"]
            row = conn.execute(text("""
                UPDATE habits
                SET name = :name, target_frequency = :target_frequency, unit = :unit
                WHERE id = :habit_id
                RETURNING id, name, target_frequency, unit, created_at
            """), {
                "habit_id": habit_id,
                "name": new_name,
                "target_frequency": new_target,
                "unit": new_unit,
            }).mappings().one()
    except NoResultFound as exc:
        raise_not_found_error("Hábito")
    record = dict(row)
    remember_entity("habit", record["name"], {record["name"], normalize_text(record["name"])})
    return record

def delete_habit_record(habit_id: int) -> None:
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM habit_checkins WHERE habit_id = :habit_id"), {"habit_id": habit_id})
        deleted = conn.execute(text("DELETE FROM habits WHERE id = :habit_id"), {"habit_id": habit_id})
        if deleted.rowcount == 0:
            raise_not_found_error("Hábito")

def update_study_session_record(session_id: int, payload: StudySessionUpdate) -> dict:
    try:
        with engine.begin() as conn:
            existing = conn.execute(text("""
                SELECT id, subject, duration_minutes, studied_on, notes, created_at
                FROM study_sessions
                WHERE id = :session_id
            """), {"session_id": session_id}).mappings().one()
            new_subject = payload.subject.strip() if payload.subject else existing["subject"]
            new_duration = payload.duration_minutes if payload.duration_minutes is not None else existing["duration_minutes"]
            new_notes = payload.notes.strip() if payload.notes is not None else existing["notes"]
            row = conn.execute(text("""
                UPDATE study_sessions
                SET subject = :subject, duration_minutes = :duration_minutes, notes = :notes
                WHERE id = :session_id
                RETURNING id, subject, duration_minutes, studied_on, notes, created_at
            """), {
                "session_id": session_id,
                "subject": new_subject,
                "duration_minutes": new_duration,
                "notes": new_notes,
            }).mappings().one()
    except NoResultFound as exc:
        raise_not_found_error("Sessão de estudo")
    record = dict(row)
    remember_entity("study_subject", record["subject"], {record["subject"], normalize_text(record["subject"])})
    return record

def delete_study_session_record(session_id: int) -> None:
    with engine.begin() as conn:
        deleted = conn.execute(text("DELETE FROM study_sessions WHERE id = :session_id"), {"session_id": session_id})
        if deleted.rowcount == 0:
            raise_not_found_error("Sessão de estudo")

def delete_finance_entry_record(entry_id: int) -> None:
    with engine.begin() as conn:
        deleted = conn.execute(text("DELETE FROM finance_entries WHERE id = :entry_id"), {"entry_id": entry_id})
        if deleted.rowcount == 0:
            raise_not_found_error("Lançamento financeiro")

def try_execute_chat_action(message: str, normalized_message: str) -> dict | None:
    action = extract_chat_action(message, normalized_message)
    if action is None:
        return None

    if action.action_type == "finance_edit" and action.amount is not None:
        latest = fetch_latest_finance_entry(action.category if action.category and action.category != "Geral" else None)
        if latest is None:
            return {
                "reply": "Eu não encontrei um lançamento financeiro recente para editar. Me diz qual lançamento você quer corrigir.",
                "source": "dock-action-finance-edit-missing",
                "model": None,
            }
        updated = update_finance_entry_record(latest["id"], amount=action.amount, category=action.category, note=action.note)
        finance = get_finance_summary()
        return {
            "reply": (
                f"Atualizei o lançamento de {updated['category']} para {format_brl(float(updated['amount']))}. "
                f"O saldo do mês agora está em {format_brl(finance['month_balance'])}."
            ),
            "source": "dock-action-finance-edit",
            "model": None,
        }

    if action.action_type == "finance_entry" and action.kind and action.category and action.amount is not None:
        record = create_finance_entry_record(
            kind=action.kind,
            category=action.category,
            amount=action.amount,
            note=action.note,
        )
        finance = get_finance_summary()
        verb = "despesa" if record["kind"] == "expense" else "receita"
        return {
            "reply": (
                f"Registrei uma {verb} de {format_brl(float(record['amount']))} em {record['category']}. "
                f"O saldo do mês agora está em {format_brl(finance['month_balance'])}."
            ),
            "source": "dock-action-finance",
            "model": None,
        }

    if action.action_type == "study_session" and action.subject and action.duration_minutes is not None:
        record = create_study_session_record(
            subject=action.subject,
            duration_minutes=action.duration_minutes,
            notes=action.note,
        )
        study = get_study_summary()
        return {
            "reply": (
                f"Registrei {record['duration_minutes']} minutos de estudo em {record['subject']}. "
                f"Hoje você soma {study['today_minutes']} minutos."
            ),
            "source": "dock-action-study",
            "model": None,
        }

    if action.action_type == "habit_checkin" and action.habit_name:
        resolution_status, resolved_habit = resolve_habit_candidate(action.habit_name, normalized_message)
        if resolution_status == "needs_confirmation" and resolved_habit is not None:
            return {
                "reply": f"Você quer registrar isso em {resolved_habit['name']}? Me manda de novo citando o nome do hábito para eu confirmar sem erro.",
                "source": "dock-action-habit-confirm",
                "model": None,
            }
        habit = resolved_habit if resolved_habit is not None else ensure_habit_exists(action.habit_name, normalized_message)
        create_habit_checkin_record(habit["id"])
        remember_entity("habit", habit["name"], {action.habit_name, normalize_text(action.habit_name)})
        habits = get_habit_summary()
        current = next((item for item in habits if item["id"] == habit["id"]), None)
        progress = current["weekly_progress"] if current else 1
        target = current["target_frequency"] if current else habit["target_frequency"]
        return {
            "reply": (
                f"Registrei um check-in em {habit['name']}. "
                f"Agora você está em {progress}/{target} nesta semana."
            ),
            "source": "dock-action-habit",
            "model": None,
        }

    return None

def current_local_label() -> str:
    return now_local().strftime(f"%Y-%m-%d %H:%M {APP_TIMEZONE_NAME}")

def fetch_currency_quote(base: str, quote: str = "BRL") -> dict:
    url = f"https://api.frankfurter.dev/v1/latest?from={base}&to={quote}"
    body = get_json(url, timeout=LIVE_DATA_TIMEOUT_SECONDS)
    rate = body.get("rates", {}).get(quote)
    if rate is None:
        raise KeyError(f"Missing rate for {base}/{quote}")
    return {
        "base": base,
        "quote": quote,
        "rate": float(rate),
        "date": body.get("date"),
    }

def fetch_bitcoin_quote_brl() -> dict:
    body = get_json("https://api.coinbase.com/v2/prices/BTC-BRL/spot", timeout=LIVE_DATA_TIMEOUT_SECONDS)
    amount = body.get("data", {}).get("amount")
    if amount is None:
        raise KeyError("Missing BTC-BRL amount")
    return {
        "asset": "BTC",
        "quote": "BRL",
        "amount": float(amount),
        "timestamp": current_local_label(),
    }

def fetch_weather_by_coords(latitude: float, longitude: float) -> dict:
    url = (
        "https://api.open-meteo.com/v1/forecast"
        f"?latitude={latitude}&longitude={longitude}"
        "&current=temperature_2m,apparent_temperature,relative_humidity_2m,weather_code,wind_speed_10m"
        "&timezone=auto"
    )
    body = get_json(url, timeout=LIVE_DATA_TIMEOUT_SECONDS)
    current = body.get("current", {})
    if not current:
        raise KeyError("Missing weather current payload")
    return {
        "temperature": current.get("temperature_2m"),
        "apparent_temperature": current.get("apparent_temperature"),
        "humidity": current.get("relative_humidity_2m"),
        "weather_code": current.get("weather_code"),
        "wind_speed": current.get("wind_speed_10m"),
        "time": current.get("time"),
        "timezone": body.get("timezone"),
    }

def weather_code_to_text(code: int | None) -> str:
    mapping = {
        0: "céu limpo",
        1: "quase limpo",
        2: "parcialmente nublado",
        3: "nublado",
        45: "neblina",
        48: "neblina com geada",
        51: "garoa fraca",
        53: "garoa moderada",
        55: "garoa intensa",
        61: "chuva fraca",
        63: "chuva moderada",
        65: "chuva forte",
        71: "neve fraca",
        73: "neve moderada",
        75: "neve forte",
        80: "pancadas de chuva fracas",
        81: "pancadas de chuva moderadas",
        82: "pancadas de chuva fortes",
        95: "trovoadas",
        96: "trovoadas com granizo",
        99: "trovoadas fortes com granizo",
    }
    return mapping.get(code, "condição variável")

def try_live_weather_reply(normalized_message: str, location: LocationContext | None) -> dict | None:
    weather_terms = {"temperatura", "tempo", "clima", "frio", "calor", "chovendo", "chuva"}
    now_terms = {"agora", "hoje", "nesse momento", "neste momento", "em sp", "em sao paulo"}
    if not contains_any(normalized_message, weather_terms):
        return None

    if location is None:
        if contains_any(normalized_message, now_terms):
            return {
                "reply": "Eu consigo responder clima ao vivo, mas preciso da sua localização liberada no app. Ativa a localização e me pergunta de novo.",
                "source": "live-weather-needs-location",
                "model": None,
            }
        return None

    try:
        weather = fetch_weather_by_coords(location.latitude, location.longitude)
        city_label = location.city or "sua região"
        condition = weather_code_to_text(weather.get("weather_code"))
        return {
            "reply": (
                f"Agora em {city_label}, está {weather.get('temperature')}°C, "
                f"com sensação de {weather.get('apparent_temperature')}°C e {condition}. "
                f"Umidade em {weather.get('humidity')}% e vento a {weather.get('wind_speed')} km/h."
            ),
            "source": "live-weather",
            "model": None,
        }
    except (error.URLError, TimeoutError, json.JSONDecodeError, KeyError, ValueError):
        return {
            "reply": "Eu tentei buscar o clima ao vivo, mas a consulta falhou agora. Tenta de novo em instantes.",
            "source": "live-weather-unavailable",
            "model": None,
        }

def try_live_finance_reply(normalized_message: str) -> dict | None:
    wants_live_data = contains_any(normalized_message, {
        "agora", "hoje", "neste momento", "nesse momento", "cotacao",
        "valor", "preco", "quanto esta", "quanto ta"
    })
    if not wants_live_data:
        return None

    try:
        if contains_any(normalized_message, {"dolar", "usd"}):
            quote = fetch_currency_quote("USD", "BRL")
            return {
                "reply": f"O dólar está em {format_brl(quote['rate'])} por US$ 1, com base na cotação de {quote['date']}.",
                "source": "live-usd-brl",
                "model": None,
            }

        if contains_any(normalized_message, {"euro", "eur"}):
            quote = fetch_currency_quote("EUR", "BRL")
            return {
                "reply": f"O euro está em {format_brl(quote['rate'])} por EUR 1, com base na cotação de {quote['date']}.",
                "source": "live-eur-brl",
                "model": None,
            }

        if contains_any(normalized_message, {"bitcoin", "btc"}):
            quote = fetch_bitcoin_quote_brl()
            return {
                "reply": f"O Bitcoin está em {format_brl(quote['amount'])}, consulta feita em {quote['timestamp']}.",
                "source": "live-btc-brl",
                "model": None,
            }
    except (error.URLError, TimeoutError, json.JSONDecodeError, KeyError, ValueError):
        return {
            "reply": "Eu tentei buscar um dado ao vivo, mas a consulta falhou neste ambiente. Se quiser, eu posso tentar de novo ou responder sem depender da internet.",
            "source": "live-data-unavailable",
            "model": None,
        }

    return None

def categorize_entry(text: str) -> str:
    text = normalize_text(text)
    if contains_any(text, {
        "gastei", "paguei", "recebi", "ganhei", "dinheiro", "pix",
        "salario", "salario", "mercado", "despesa", "receita", "r$", "$"
    }):
        return "finance"
    elif contains_any(text, {
        "dormi", "sono", "acordei", "fui dormir", "sleep", "slept"
    }):
        return "sleep"
    elif contains_any(text, {
        "estudei", "estudar", "estudo", "leitura", "livro", "read", "studied"
    }):
        return "study"
    else:
        return "general"

def classify_message_intent(normalized_message: str) -> str:
    if normalized_message in {
        "quem e voce?",
        "qual e seu nome?",
        "voce e o qwen?",
        "voce e o chatgpt?",
    }:
        return "identity"

    founder_keywords = {
        "quem e o founder da empresa?",
        "quem e o fundador da empresa?",
        "quem e o founder?",
        "quem e o fundador?",
        "quem fundou a empresa?",
        "quem fundou o dock?",
    }
    if normalized_message in founder_keywords:
        return "founder"

    if contains_any(normalized_message, {"dolar", "usd", "euro", "eur", "bitcoin", "btc"}):
        if contains_any(normalized_message, {"agora", "hoje", "cotacao", "preco", "valor", "quanto esta", "quanto ta"}):
            return "live_finance"

    if contains_any(normalized_message, {"temperatura", "tempo", "clima", "chuva", "frio", "calor"}):
        if contains_any(normalized_message, {"agora", "hoje", "nesse momento", "neste momento", "em sp", "em sao paulo"}):
            return "live_weather"

    if contains_any(normalized_message, {"saldo", "financeiro", "financas", "gastei", "receita", "despesa"}):
        return "dashboard_finance"

    if contains_any(normalized_message, {"estudei", "estudo", "estudos", "quanto estudei", "horas de estudo", "minutos de estudo"}):
        return "dashboard_study"

    if contains_any(normalized_message, {"habitos", "consistencia", "check-in"}):
        return "dashboard_habits"

    if contains_any(normalized_message, {
        "fui pra academia", "fui para academia", "treinei", "treino feito",
        "malhei", "corri", "caminhei", "nadei", "pedalei", "fiz exercicio",
        "fiz exercicios", "fiz atividade fisica", "fui ao treino"
    }):
        return "activity_update"

    if contains_any(normalized_message, {"bom dia", "boa tarde", "boa noite", "oi", "ola"}):
        return "greeting"

    if contains_any(normalized_message, {"organizar meu dia", "organizar o dia", "planejar meu dia", "planejar o dia"}):
        return "day_plan"

    if contains_any(normalized_message, {"3 passos", "tres passos"}) and contains_any(normalized_message, {"dia", "rotina", "organizar", "planejar"}):
        return "three_steps"

    if contains_any(normalized_message, {"focar", "foco", "concentrar", "concentracao"}):
        return "focus"

    if contains_any(normalized_message, {"procrastin", "sem vontade", "desmotivado", "desanimado"}):
        return "procrastination"

    if contains_any(normalized_message, {"resuma", "resume", "resumir"}) and len(normalized_message) < 220:
        return "summary_request"

    return "open_chat"

def now_local() -> datetime:
    return datetime.now(APP_TIMEZONE)

def today_local() -> dt_date:
    return now_local().date()

def serialize_rows(result) -> list[dict]:
    return [dict(row) for row in result.mappings().all()]

def get_habit_summary() -> list[dict]:
    with engine.connect() as conn:
        habits = serialize_rows(conn.execute(text("""
            SELECT id, name, target_frequency, unit, created_at
            FROM habits
            ORDER BY created_at DESC, id DESC
        """)))
        checkins = serialize_rows(conn.execute(text("""
            SELECT habit_id, checkin_date, value
            FROM habit_checkins
        """)))
    week_start = today_local().toordinal() - 6
    progress_map: dict[int, int] = {}
    for row in checkins:
        check_date = row["checkin_date"]
        if isinstance(check_date, str):
            check_date = dt_date.fromisoformat(check_date)
        if check_date.toordinal() < week_start:
            continue
        progress_map[row["habit_id"]] = progress_map.get(row["habit_id"], 0) + int(row["value"] or 0)
    for item in habits:
        item["weekly_progress"] = progress_map.get(item["id"], 0)
        target = int(item["target_frequency"] or 0)
        item["completion_rate"] = round((item["weekly_progress"] / target) * 100, 1) if target else 0.0
    return habits

def get_recent_study_sessions(limit: int = 50) -> list[dict]:
    with engine.connect() as conn:
        rows = serialize_rows(conn.execute(text("""
            SELECT id, subject, duration_minutes, studied_on, notes, created_at
            FROM study_sessions
            ORDER BY studied_on DESC, id DESC
            LIMIT :limit
        """), {"limit": limit}))
    return rows

def get_recent_finance_entries(limit: int = 50) -> list[dict]:
    with engine.connect() as conn:
        rows = serialize_rows(conn.execute(text("""
            SELECT id, kind, category, amount, occurred_on, note, created_at
            FROM finance_entries
            ORDER BY occurred_on DESC, id DESC
            LIMIT :limit
        """), {"limit": limit}))
    return rows

def get_study_summary() -> dict:
    with engine.connect() as conn:
        sessions = serialize_rows(conn.execute(text("""
            SELECT subject, duration_minutes, studied_on
            FROM study_sessions
            ORDER BY studied_on DESC, id DESC
        """)))
    today = today_local()
    week_start = today.toordinal() - 6
    today_minutes = 0
    week_minutes = 0
    subject_map: dict[str, int] = {}
    for row in sessions:
        studied_on = row["studied_on"]
        if isinstance(studied_on, str):
            studied_on = dt_date.fromisoformat(studied_on)
        duration = int(row["duration_minutes"] or 0)
        if studied_on == today:
            today_minutes += duration
        if studied_on.toordinal() >= week_start:
            week_minutes += duration
            subject = row["subject"]
            subject_map[subject] = subject_map.get(subject, 0) + duration
    return {
        "today_minutes": today_minutes,
        "week_minutes": week_minutes,
        "subjects": [
            {"subject": subject, "total_minutes": minutes}
            for subject, minutes in sorted(subject_map.items(), key=lambda item: (-item[1], item[0]))
        ],
    }

def get_finance_summary() -> dict:
    with engine.connect() as conn:
        entries = serialize_rows(conn.execute(text("""
            SELECT kind, category, amount, occurred_on
            FROM finance_entries
            ORDER BY occurred_on DESC, id DESC
        """)))
    income_total = 0.0
    expense_total = 0.0
    month_income = 0.0
    month_expense = 0.0
    category_map: dict[str, float] = {}
    today = today_local()
    for row in entries:
        occurred_on = row["occurred_on"]
        if isinstance(occurred_on, str):
            occurred_on = dt_date.fromisoformat(occurred_on)
        amount = float(row["amount"] or 0)
        kind = row["kind"]
        if kind == "income":
            income_total += amount
        elif kind == "expense":
            expense_total += amount
        if occurred_on.year == today.year and occurred_on.month == today.month:
            if kind == "income":
                month_income += amount
            elif kind == "expense":
                month_expense += amount
                category = row["category"]
                category_map[category] = category_map.get(category, 0.0) + amount
    return {
        "balance_total": round(income_total - expense_total, 2),
        "income_total": round(income_total, 2),
        "expense_total": round(expense_total, 2),
        "month_balance": round(month_income - month_expense, 2),
        "month_income": round(month_income, 2),
        "month_expense": round(month_expense, 2),
        "categories": [
            {"category": category, "total_amount": round(total_amount, 2)}
            for category, total_amount in sorted(category_map.items(), key=lambda item: (-item[1], item[0]))
        ],
    }

def get_dashboard_summary() -> dict:
    habit_summary = get_habit_summary()
    study_summary = get_study_summary()
    finance_summary = get_finance_summary()
    return {
        "habits": habit_summary,
        "study": study_summary,
        "finance": finance_summary,
        "study_sessions": get_recent_study_sessions(),
        "finance_entries": get_recent_finance_entries(),
        "highlights": {
            "habit_count": len(habit_summary),
            "study_today_minutes": study_summary["today_minutes"],
            "finance_month_balance": finance_summary["month_balance"],
        },
    }

def build_dock_context_summary() -> str:
    dashboard = get_dashboard_summary()
    finance = dashboard["finance"]
    study = dashboard["study"]
    return (
        f"Hábitos ativos: {dashboard['highlights']['habit_count']}. "
        f"Estudo hoje: {study['today_minutes']} min. "
        f"Estudo na semana: {study['week_minutes']} min. "
        f"Saldo do mês: {format_brl(finance['month_balance'])}."
    )

def shorten_text(text: str, limit: int = 96) -> str:
    cleaned = " ".join(text.strip().split())
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: limit - 3].rstrip() + "..."

def dedupe_phrases(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        normalized_item = normalize_text(item)
        if not normalized_item or normalized_item in seen:
            continue
        seen.add(normalized_item)
        result.append(item)
    return result

def is_actionable_phrase(normalized_text: str) -> bool:
    blocked_prefixes = {
        "to meio", "tô meio", "estou meio", "me sinto", "me sentindo",
        "isso ta", "isso está", "nao sei", "não sei", "como faco",
        "como faço", "o que faco", "o que faço", "quero mudar minha vida",
        "mudar minha vida", "crescer no trabalho", "me sinto perdido",
        "estou perdido", "estou confuso", "to confuso", "tô confuso",
    }
    if any(normalized_text.startswith(prefix) for prefix in blocked_prefixes):
        return False

    action_terms = {
        "terminar", "responder", "organizar", "estudar", "enviar", "ligar",
        "revisar", "pagar", "resolver", "fechar", "falar", "treinar",
        "comprar", "ajustar", "planejar", "escrever", "montar", "criar",
        "limpar", "entregar", "preparar", "priorizar", "separar",
    }
    return contains_any(normalized_text, action_terms)

def extract_action_items(message: str, limit: int = 4) -> list[str]:
    prepared = re.sub(r"[\r\n]+", ", ", message)
    chunks = re.split(r"[;,:]", prepared)
    if len(chunks) == 1 and len(re.findall(r"\s+e\s+", prepared, flags=re.IGNORECASE)) >= 2:
        chunks = re.split(r"\s+e\s+", prepared, flags=re.IGNORECASE)

    noise_prefixes = {
        "estou com muita coisa", "to com muita coisa", "tô com muita coisa",
        "muita coisa", "estou perdido", "to perdido", "tô perdido",
        "estou confuso", "to confuso", "tô confuso", "estou sobrecarregado",
        "to sobrecarregado", "tô sobrecarregado", "estou sobrecarregada",
        "to sobrecarregada", "tô sobrecarregada", "nao sei o que fazer agora",
        "não sei o que fazer agora", "nao sei por onde comecar", "não sei por onde começar",
    }

    items: list[str] = []
    for chunk in chunks:
        subchunks = re.split(r"\s+e\s+", chunk, flags=re.IGNORECASE)
        for subchunk in subchunks:
            cleaned = subchunk.strip(" .,!?:;")
            if not cleaned:
                continue
            cleaned = re.sub(
                r"^(?:eu\s+)?(?:preciso|tenho que|quero|devo|precisava|"
                r"estou precisando de|to precisando de|tô precisando de|"
                r"me ajuda a|me ajude a)\s+",
                "",
                cleaned,
                flags=re.IGNORECASE,
            ).strip(" .,!?:;")
            normalized_cleaned = normalize_text(cleaned)
            if any(normalized_cleaned.startswith(prefix) for prefix in noise_prefixes):
                continue
            if not is_actionable_phrase(normalized_cleaned):
                continue
            if len(normalized_cleaned) < 8 or len(cleaned.split()) < 2:
                continue
            items.append(shorten_text(cleaned, 72))
    return dedupe_phrases(items)[:limit]

def join_readable_list(items: list[str]) -> str:
    cleaned = [item for item in items if item]
    if not cleaned:
        return ""
    if len(cleaned) == 1:
        return cleaned[0]
    if len(cleaned) == 2:
        return f"{cleaned[0]} e {cleaned[1]}"
    return f"{', '.join(cleaned[:-1])} e {cleaned[-1]}"

def pick_dashboard_attention_signal(dashboard: dict) -> str | None:
    finance = dashboard["finance"]
    study = dashboard["study"]
    habits = dashboard["habits"]

    if finance["month_balance"] < 0:
        return f"o financeiro do mês está negativo em {format_brl(abs(finance['month_balance']))}"

    if study["today_minutes"] == 0 and study["week_minutes"] == 0:
        return "o estudo ainda não entrou em tração nesta semana"

    if habits:
        weakest = min(habits, key=lambda item: float(item["completion_rate"]))
        if float(weakest["completion_rate"]) < 50:
            return f"o hábito {weakest['name']} ainda está abaixo da metade da meta semanal"
    else:
        return "você ainda não tem hábitos ativos registrados no painel"

    return None

def build_dashboard_overview_reply(dashboard: dict) -> str:
    habits = dashboard["habits"]
    study = dashboard["study"]
    finance = dashboard["finance"]

    if habits:
        best_habit = max(habits, key=lambda item: float(item["completion_rate"]))
        habit_line = (
            f"Você tem {len(habits)} hábitos ativos, e o melhor ritmo agora é {best_habit['name']} "
            f"com {best_habit['weekly_progress']}/{best_habit['target_frequency']} na semana."
        )
    else:
        habit_line = "Você ainda não tem hábitos ativos no painel."

    study_line = (
        f"De estudo, você soma {study['today_minutes']} minutos hoje "
        f"e {study['week_minutes']} minutos na semana."
    )
    finance_line = (
        f"No financeiro do mês, entraram {format_brl(finance['month_income'])}, "
        f"saíram {format_brl(finance['month_expense'])} e o saldo está em {format_brl(finance['month_balance'])}."
    )

    attention = pick_dashboard_attention_signal(dashboard)
    if attention:
        return f"{habit_line} {study_line} {finance_line} O ponto que mais pede atenção agora é: {attention}."
    return f"{habit_line} {study_line} {finance_line}"

def build_local_plan_reply(message: str, dashboard: dict) -> str:
    tasks = extract_action_items(message)
    attention = pick_dashboard_attention_signal(dashboard)

    if tasks:
        steps = [f"1. Puxa {tasks[0]} para o primeiro bloco de foco."]
        if len(tasks) >= 2:
            steps.append(f"2. Depois fecha {tasks[1]} sem abrir outra frente no meio.")
        else:
            steps.append("2. Depois resolve a pendência curta que mais destrava o restante.")
        if len(tasks) >= 3:
            steps.append(f"3. Antes de encerrar, deixa o próximo passo de {tasks[2]} definido.")
        else:
            steps.append("3. Antes de encerrar, deixa um próximo passo claro para amanhã.")
        reply = f"Vamos reduzir isso ao essencial. {' '.join(steps)}"
    else:
        reply = (
            "Vamos tirar isso do abstrato. 1. Escolhe a frente que muda o resultado de hoje. "
            "2. Reserva um bloco curto sem distração para executar. "
            "3. Fecha o dia deixando a próxima ação escrita, não só pensada."
        )

    if attention:
        reply += f" Sinal do painel: {attention}."
    return reply

def build_local_decision_reply(message: str) -> str:
    match = re.search(
        r"\b(?:devo|melhor|vale|escolho|escolher|entre)\s+(.+?)\s+ou\s+(.+?)(?:[?.!]|$)",
        message,
        flags=re.IGNORECASE,
    )
    if match:
        option_a = shorten_text(match.group(1).strip(" .,!?:;"), 60)
        option_b = shorten_text(match.group(2).strip(" .,!?:;"), 60)
        return (
            f"Se a decisão é entre {option_a} e {option_b}, escolhe o que reduz risco "
            "ou destrava o resto ainda hoje. Meu corte prático: se a primeira opção fecha "
            "uma pendência crítica, vai nela; se não, faz a outra e já deixa a primeira "
            "com um próximo passo definido."
        )

    return (
        "Escolhe pelo que gera mais clareza nas próximas 24 horas. "
        "Se uma opção reduz risco ou fecha pendência crítica, ela vem primeiro; "
        "a outra vira próximo passo agendado, não pendência vaga."
    )

def build_local_history_summary(history: list[Message]) -> str | None:
    last_user_message: str | None = None
    for item in reversed(history):
        if item.role.strip().lower() == "user" and item.content.strip():
            last_user_message = item.content.strip()
            break

    if not last_user_message:
        return None

    tasks = extract_action_items(last_user_message, limit=3)
    if tasks:
        return (
            f"Em resumo: você está tentando lidar com {join_readable_list(tasks)} ao mesmo tempo. "
            "O melhor próximo passo é escolher uma frente e fechar um bloco de execução antes "
            "de reorganizar o restante."
        )

    first_sentence = re.split(r"[.!?]+", last_user_message, maxsplit=1)[0]
    return (
        f"Em resumo: {shorten_text(first_sentence, 140)}. "
        "Se quiser, eu também transformo isso em prioridades ou próximos passos."
    )

def summarize_entry_locally(text: str, category: str) -> tuple[str, float]:
    normalized_text = normalize_text(text)

    if category == "finance":
        amount = parse_amount_from_text(normalized_text)
        category_label = infer_finance_category(normalized_text)
        if contains_any(normalized_text, {"recebi", "ganhei"}):
            if amount is not None:
                return f"Receita em {category_label} de {format_brl(amount)}.", 0.82
            return f"Registro de receita relacionado a {category_label}.", 0.64
        if amount is not None:
            return f"Despesa em {category_label} de {format_brl(amount)}.", 0.8
        return f"Registro financeiro relacionado a {category_label}.", 0.6

    if category == "study":
        subject = infer_study_subject(normalized_text)
        duration = parse_duration_minutes(normalized_text)
        if duration is not None:
            return f"Estudo de {subject} por {duration} minutos.", 0.8
        return f"Registro de estudo em {subject}.", 0.62

    if category == "sleep":
        hours_match = re.search(r"(\d+(?:[.,]\d+)?)\s*(h|hora|horas)\b", normalized_text)
        if hours_match:
            hours = hours_match.group(1).replace(",", ".")
            return f"Registro de sono com cerca de {hours} horas.", 0.74
        return "Registro relacionado a sono e descanso.", 0.56

    return shorten_text(" ".join(text.strip().split()), 120), 0.4

def try_local_brain_reply(message: str, normalized_message: str, history: list[Message]) -> dict | None:
    overview_terms = {
        "como estou", "como eu estou", "me atualiza", "panorama", "visao geral",
        "visão geral", "status geral", "resumo geral", "como ta minha rotina",
        "como ta meu dia", "como esta meu dia", "me da um panorama",
    }
    planning_terms = {
        "prioridade", "prioridades", "organizar", "planejar", "amanha", "amanhã",
        "rotina", "semana", "o que faco agora", "o que fazer agora",
        "por onde comeco", "por onde começar", "proximo passo", "próximo passo",
        "me ajuda", "me ajude",
    }
    overload_terms = {
        "sobrecarregado", "sobrecarregada", "perdido", "perdida", "confuso",
        "confusa", "ansioso", "ansiosa", "atrasado", "atrasada", "muita coisa",
        "sem direcao", "sem direção", "caos",
    }

    if contains_any(normalized_message, overview_terms):
        dashboard = get_dashboard_summary()
        return {
            "reply": build_dashboard_overview_reply(dashboard),
            "source": "dock-data-overview",
            "model": None,
        }

    if contains_any(normalized_message, {"resuma isso", "resume isso", "resuma o que eu disse", "resume o que eu disse", "resuma acima", "resume acima"}):
        summary = build_local_history_summary(history)
        if summary is not None:
            return {
                "reply": summary,
                "source": "dock-local-summary",
                "model": None,
            }

    if " ou " in normalized_message and contains_any(normalized_message, {"devo", "melhor", "vale", "escolho", "escolher", "entre"}):
        return {
            "reply": build_local_decision_reply(message),
            "source": "dock-local-decision",
            "model": None,
        }

    if contains_any(normalized_message, planning_terms | overload_terms):
        dashboard = get_dashboard_summary()
        return {
            "reply": build_local_plan_reply(message, dashboard),
            "source": "dock-local-plan",
            "model": None,
        }

    return None

def infer_focus_area(normalized_message: str) -> str | None:
    area_terms = {
        "trabalho": {"trabalho", "carreira", "profissional", "empresa", "cliente", "proposta", "emprego"},
        "financeiro": {"dinheiro", "financeiro", "financas", "finanças", "gasto", "receita", "despesa", "grana"},
        "estudo": {"estudo", "estudar", "curso", "aprender", "prova", "disciplina"},
        "rotina": {"rotina", "dia", "semana", "agenda", "organizacao", "organização"},
        "saude": {"saude", "saúde", "sono", "treino", "academia", "energia", "alimentacao", "alimentação"},
    }
    for area, terms in area_terms.items():
        if contains_any(normalized_message, terms):
            return area
    return None

def looks_like_question(normalized_message: str) -> bool:
    question_terms = {
        "como", "o que", "qual", "quais", "porque", "por que",
        "vale", "devo", "seria melhor", "faz sentido", "compensa",
    }
    return normalized_message.endswith("?") or contains_any(normalized_message, question_terms)

def build_local_open_chat_reply(message: str, normalized_message: str, history: list[Message]) -> dict:
    dashboard = get_dashboard_summary()
    attention = pick_dashboard_attention_signal(dashboard)
    tasks = extract_action_items(message, limit=3)
    focus_area = infer_focus_area(normalized_message)

    if contains_any(normalized_message, {"mudar minha vida", "melhorar minha vida", "quero evoluir", "quero sair do lugar", "dar uma virada"}):
        reply = (
            "Se você quer mudar de vida, não tenta virar tudo de uma vez. "
            "Escolhe a frente que mais pesa agora, define um resultado concreto para os próximos 7 dias "
            "e corta o que só ocupa cabeça sem mover nada."
        )
        if attention:
            reply += f" Pelo painel, o ponto mais sensível hoje é: {attention}."
        return {"reply": reply, "source": "dock-local-open-chat", "model": None}

    if contains_any(normalized_message, {"crescer no trabalho", "crescer profissionalmente", "evoluir na carreira", "subir de nivel", "subir de nível"}):
        return {
            "reply": (
                "Para crescer no trabalho sem cair em teoria vaga, foca em três alavancas: "
                "entrega visível, comunicação clara e consistência. Escolhe uma entrega que mova resultado nesta semana, "
                "alinha expectativa com quem decide e fecha o ciclo mostrando avanço de forma objetiva."
            ),
            "source": "dock-local-open-chat",
            "model": None,
        }

    if contains_any(normalized_message, {"travado", "travada", "desanimado", "desanimada", "sem energia", "sem vontade", "to meio travado", "tô meio travado"}):
        reply = (
            "Quando você trava, não procura a resposta perfeita antes de agir. "
            "Reduz para uma ação pequena que cria movimento, fecha um bloco curto sem distração "
            "e só depois reavalia o resto."
        )
        if tasks:
            reply += f" Se eu cortasse isso agora, começaria por {tasks[0]}."
        elif attention:
            reply += f" O painel também está sinalizando que {attention}."
        return {"reply": reply, "source": "dock-local-open-chat", "model": None}

    if contains_any(normalized_message, {"nao sei o que fazer agora", "não sei o que fazer agora", "nao sei por onde comecar", "não sei por onde começar"}):
        return {
            "reply": build_local_plan_reply(message, dashboard),
            "source": "dock-local-open-chat",
            "model": None,
        }

    if tasks:
        steps = [f"1. Começa por {tasks[0]}."]
        if len(tasks) >= 2:
            steps.append(f"2. Depois fecha {tasks[1]} sem reabrir a primeira frente.")
        else:
            steps.append("2. Depois resolve a menor pendência que destrava o restante.")
        if len(tasks) >= 3:
            steps.append(f"3. Antes de encerrar, deixa {tasks[2]} com próximo passo definido.")
        reply = f"Isso já dá para transformar em ação. {' '.join(steps)}"
        if attention:
            reply += f" E fica atento porque {attention}."
        return {"reply": reply, "source": "dock-local-open-chat", "model": None}

    if looks_like_question(normalized_message):
        if focus_area == "trabalho":
            reply = (
                "Se a questão é trabalho, eu trataria assim: primeiro define qual resultado precisa sair, "
                "depois reduz isso a uma entrega visível e por fim comunica avanço antes de ficar perfeito. "
                "Isso tende a gerar mais tração do que tentar resolver tudo só no pensamento."
            )
        elif focus_area == "financeiro":
            reply = (
                "Se a questão é financeira, o corte certo é separar decisão de impulso. "
                "Olha o impacto no mês, define um limite claro e só mantém o que preserva caixa ou gera retorno real."
            )
        elif focus_area == "estudo":
            reply = (
                "Se a questão é estudo, pensa menos em volume abstrato e mais em constância. "
                "Define o tema, o tempo do bloco e o critério de saída antes de começar."
            )
        else:
            reply = (
                "Do jeito que você colocou, eu trataria isso transformando a dúvida em decisão prática. "
                "Primeiro identifica o que muda o resultado agora, depois escolhe a ação mais curta que reduz incerteza "
                "e só então decide o restante."
            )
        if attention:
            reply += f" Hoje o painel também mostra que {attention}."
        return {"reply": reply, "source": "dock-local-open-chat", "model": None}

    if history and contains_any(normalized_message, {"isso", "nisso", "assim", "desse jeito", "dessa forma"}):
        summary = build_local_history_summary(history)
        if summary is not None:
            return {
                "reply": f"{summary} Se quiser, eu transformo isso em um plano direto agora.",
                "source": "dock-local-open-chat",
                "model": None,
            }

    area_hint = {
        "trabalho": "trabalho e execução",
        "financeiro": "dinheiro e decisões financeiras",
        "estudo": "estudo e evolução",
        "rotina": "rotina e prioridades",
        "saude": "energia e consistência",
    }.get(focus_area, "clareza e execução")

    reply = (
        f"Pelo que você trouxe, o tema aqui parece ser {area_hint}. "
        "Em vez de deixar isso solto, meu corte prático é escolher uma frente concreta para hoje, "
        "definir um bloco curto de execução e usar o Dock para registrar o que avançou."
    )
    if attention:
        reply += f" O ponto do painel que mais pede cuidado agora é: {attention}."
    reply += " Se quiser, eu também posso transformar essa mensagem em 3 passos objetivos."
    return {"reply": reply, "source": "dock-local-open-chat", "model": None}

def generate_chat_reply(message: str, history: list[Message], location: LocationContext | None = None) -> dict:
    context_summary = build_dock_context_summary()

    if AI_PROVIDER == "openai":
        messages: list[dict] = [
            {
                "role": "system",
                "content": [
                    {"type": "input_text", "text": f"Contexto do Dock: {context_summary}"}
                ],
            }
        ]

        if location is not None:
            location_bits = [f"latitude={location.latitude}", f"longitude={location.longitude}"]
            if location.city:
                location_bits.append(f"cidade={location.city}")
            if location.region:
                location_bits.append(f"regiao={location.region}")
            messages.append({
                "role": "system",
                "content": [{"type": "input_text", "text": f"Contexto de localização: {', '.join(location_bits)}"}],
            })

        for item in history[-CHAT_HISTORY_LIMIT:]:
            role = item.role.strip().lower()
            if role not in {"user", "assistant"}:
                role = "user"
            messages.append({
                "role": role,
                "content": [{"type": "input_text", "text": item.content}],
            })

        messages.append({
            "role": "user",
            "content": [{"type": "input_text", "text": message}],
        })

        reply = call_openai_chat(messages, timeout=CHAT_TIMEOUT_SECONDS)
        return {"reply": reply, "source": "openai", "model": OPENAI_MODEL}

    if AI_PROVIDER == "ollama":
        compact_prompt = (
            f"{SYSTEM_PROMPT.strip()}\n\n"
            f"Contexto do Dock: {context_summary}\n\n"
            f"Usuário: {message}\n"
            "Dock:"
        )
        reply = call_ollama(compact_prompt, timeout=CHAT_TIMEOUT_SECONDS)
        return {"reply": reply, "source": "ollama", "model": OLLAMA_MODEL}

    return build_local_open_chat_reply(message, normalize_text(message), history)

def try_fast_local_reply(normalized_message: str) -> dict | None:
    intent = classify_message_intent(normalized_message)

    if intent == "greeting":
        return {
            "reply": "Estou aqui. Me diz o que você quer destravar agora: foco, rotina, dinheiro, estudo ou uma decisão específica.",
            "source": "dock-fast-greeting",
            "model": None,
        }

    if contains_any(normalized_message, {"quem e voce", "quem e o dock", "explique quem voce e", "me fale quem voce e", "detalh", "profund"}):
        return {
            "reply": "Eu sou o Dock, sua inteligência pessoal. Meu papel é transformar pensamento solto em clareza, direção e execução sobre rotina, estudo, saúde, trabalho e dinheiro. Eu existo para ajudar você a decidir melhor, organizar o que importa e sair da intenção para a ação. Em vez de ser só um chat, eu quero funcionar como uma interface prática de lucidez no seu dia a dia.",
            "source": "dock-fast-identity-detailed",
            "model": None,
        }

    if intent == "day_plan":
        return {
            "reply": "Claro. 1. Define a única entrega principal do dia. 2. Reserva dois blocos curtos sem distração para executar. 3. Fecha o dia revisando o que avançou e o próximo passo de amanhã.",
            "source": "dock-fast-day-plan",
            "model": None,
        }

    if intent == "three_steps":
        return {
            "reply": "1. Escolhe a prioridade que realmente move o dia. 2. Executa antes do resto em um bloco de foco. 3. Reorganiza o restante sem deixar pendência vaga.",
            "source": "dock-fast-3-steps",
            "model": None,
        }

    if intent == "focus":
        return {
            "reply": "Corta o ruído primeiro. Escolhe uma tarefa, define 25 minutos sem interrupção e não abre nada que não empurre essa tarefa para frente.",
            "source": "dock-fast-focus",
            "model": None,
        }

    if intent == "procrastination":
        return {
            "reply": "Não tenta resolver o dia inteiro. Escolhe a menor ação útil possível e começa por 10 minutos. Movimento gera tração; espera gera culpa.",
            "source": "dock-fast-procrastination",
            "model": None,
        }

    if intent == "activity_update":
        return {
            "reply": "Boa. Isso conta como avanço real no dia. Se academia for um hábito seu, registra o check-in na aba Hábitos para o Dock acompanhar sua consistência.",
            "source": "dock-fast-activity-update",
            "model": None,
        }

    if intent == "summary_request":
        return {
            "reply": "Posso resumir, mas para fazer isso direito eu preciso do texto ou do contexto que você quer condensar.",
            "source": "dock-fast-summary-request",
            "model": None,
        }

    return None

def try_fallback_chat_reply(normalized_message: str) -> dict | None:
    if contains_any(normalized_message, {"perdido", "confuso", "sem direcao", "sem direção"}) and contains_any(
        normalized_message, {"rotina", "semana", "dia", "vida"}
    ):
        return {
            "reply": "Vamos simplificar. Escolhe uma prioridade real para esta semana, define o próximo passo concreto e elimina o que não ajuda nisso. Se quiser, eu posso te ajudar a reorganizar a semana em blocos claros.",
            "source": "dock-fallback-clarity",
            "model": None,
        }

    if contains_any(normalized_message, {"prioridade", "organizar", "planejar"}) and contains_any(
        normalized_message, {"dia", "semana", "rotina"}
    ):
        return {
            "reply": "Começa por três coisas: 1. o que mais move o resultado, 2. o que é urgente de verdade, 3. o que pode sair. Se você quiser, me diz tudo que está na cabeça e eu reorganizo em ordem.",
            "source": "dock-fallback-planning",
            "model": None,
        }

    if contains_any(normalized_message, {"cansado", "sobrecarregado", "ansioso", "ansiosa"}):
        return {
            "reply": "Não tenta resolver tudo agora. Reduz para uma ação útil, uma pendência para adiar e um bloco curto de foco. O Dock funciona melhor quando transforma excesso em sequência.",
            "source": "dock-fallback-overload",
            "model": None,
        }

    return {
        "reply": "Entendi. Me dá um pouco mais de contexto ou transforma isso em uma pergunta mais direta que eu te respondo de forma objetiva.",
        "source": "dock-fallback-general",
        "model": None,
    }

def try_data_backed_reply(normalized_message: str) -> dict | None:
    dashboard = get_dashboard_summary()
    intent = classify_message_intent(normalized_message)

    if intent == "dashboard_finance":
        finance = dashboard["finance"]
        return {
            "reply": (
                f"Seu saldo acumulado está em {format_brl(finance['balance_total'])}. "
                f"No mês, entraram {format_brl(finance['month_income'])} e saíram {format_brl(finance['month_expense'])}, "
                f"fechando {format_brl(finance['month_balance'])}."
            ),
            "source": "dock-data-finance",
            "model": None,
        }

    if intent == "dashboard_study":
        study = dashboard["study"]
        hours = round(study["week_minutes"] / 60, 1)
        return {
            "reply": (
                f"Hoje você estudou {study['today_minutes']} minutos. "
                f"Na semana, você acumulou {study['week_minutes']} minutos, ou {hours} horas."
            ),
            "source": "dock-data-study",
            "model": None,
        }

    if intent == "dashboard_habits":
        habits = dashboard["habits"]
        if not habits:
            return {
                "reply": "Você ainda não cadastrou hábitos no Dock. Assim que cadastrar, eu consigo te mostrar consistência e progresso semanal com precisão.",
                "source": "dock-data-habits-empty",
                "model": None,
            }
        best = max(habits, key=lambda item: item["completion_rate"])
        return {
            "reply": (
                f"Você tem {len(habits)} hábitos cadastrados. "
                f"O mais consistente agora é {best['name']}, com {best['weekly_progress']} check-ins na semana e {best['completion_rate']}% da meta."
            ),
            "source": "dock-data-habits",
            "model": None,
        }

    return None

def analyze_entry_with_ai(text: str) -> dict:
    prompt = f"""
You are classifying a Dock user entry.
Do not invent facts. Do not change spending into earning, or vice versa.
Keep the summary faithful to the original text.
Return JSON only with this exact shape:
{{
  "category": "finance|sleep|study|general",
  "summary": "short summary",
  "confidence": 0.0
}}

Entry: {text}
"""

    try:
        model_text, source, model_name = generate_text(prompt, timeout=AI_TIMEOUT_SECONDS)
        parsed = json.loads(strip_code_fences(model_text))
        return {
            "category": parsed.get("category", "general"),
            "summary": parsed.get("summary", ""),
            "confidence": parsed.get("confidence", 0.0),
            "source": source,
            "model": model_name,
        }
    except (error.URLError, TimeoutError, json.JSONDecodeError, KeyError, ValueError):
        fallback_category = categorize_entry(text)
        fallback_summary, fallback_confidence = summarize_entry_locally(text, fallback_category)
        return {
            "category": fallback_category,
            "summary": fallback_summary,
            "confidence": fallback_confidence,
            "source": "dock-local-analysis",
            "model": None,
        }

def chat_with_ai(message: str, history: list[Message], location: LocationContext | None = None) -> dict:
    normalized_message = normalize_text(message)
    intent = classify_message_intent(normalized_message)

    if intent == "identity":
        return {
            "reply": "Eu sou o Dock, a sua interface de inteligência pessoal. Transformo pensamento solto em clareza, direção e execução sobre rotina, estudo, saúde, trabalho e dinheiro.",
            "source": "dock-identity",
            "model": None,
        }

    if intent == "founder":
        return {
            "reply": "O founder da empresa é o Lucas Melo.",
            "source": "dock-founder",
            "model": None,
        }

    action_reply = try_execute_chat_action(message, normalized_message)
    if action_reply is not None:
        return action_reply

    live_finance_reply = try_live_finance_reply(normalized_message)
    if live_finance_reply is not None:
        return live_finance_reply

    live_weather_reply = try_live_weather_reply(normalized_message, location)
    if live_weather_reply is not None:
        return live_weather_reply

    data_backed_reply = try_data_backed_reply(normalized_message)
    if data_backed_reply is not None:
        return data_backed_reply

    local_brain_reply = try_local_brain_reply(message, normalized_message, history)
    if local_brain_reply is not None:
        return local_brain_reply

    fast_local_reply = try_fast_local_reply(normalized_message)
    if fast_local_reply is not None:
        return fast_local_reply

    try:
        return generate_chat_reply(message, history, location)
    except (error.URLError, TimeoutError, json.JSONDecodeError, KeyError, ValueError):
        return build_local_open_chat_reply(message, normalized_message, history)

@app.get("/")
def app_shell():
    return FileResponse(FRONTEND_DIR / "index.html")

@app.get("/health")
def read_root():
    return {
        "message": "Dock API is running",
        "ai_provider": AI_PROVIDER,
        "database": "sqlite" if IS_SQLITE else "postgres",
        "timezone": APP_TIMEZONE_NAME,
    }

@app.get("/dashboard")
def dashboard():
    return get_dashboard_summary()

@app.get("/habits")
def list_habits():
    return {"items": get_habit_summary()}

@app.post("/habits")
def create_habit(habit: HabitCreate):
    return create_habit_record(habit.name, habit.target_frequency, habit.unit)

@app.patch("/habits/{habit_id}")
def update_habit(habit_id: int, payload: HabitUpdate):
    return update_habit_record(habit_id, payload)

@app.delete("/habits/{habit_id}")
def delete_habit(habit_id: int):
    delete_habit_record(habit_id)
    return {"ok": True}

@app.post("/habits/{habit_id}/checkins")
def create_habit_checkin(habit_id: int, payload: HabitCheckInCreate):
    return create_habit_checkin_record(habit_id, payload.value, payload.date)

@app.get("/study-sessions")
def list_study_sessions():
    return {"items": get_recent_study_sessions(), "summary": get_study_summary()}

@app.post("/study-sessions")
def create_study_session(session: StudySessionCreate):
    return create_study_session_record(session.subject, session.duration_minutes, session.studied_on, session.notes)

@app.patch("/study-sessions/{session_id}")
def update_study_session(session_id: int, payload: StudySessionUpdate):
    return update_study_session_record(session_id, payload)

@app.delete("/study-sessions/{session_id}")
def delete_study_session(session_id: int):
    delete_study_session_record(session_id)
    return {"ok": True}

@app.get("/finance-entries")
def list_finance_entries():
    return {"items": get_recent_finance_entries(), "summary": get_finance_summary()}

@app.post("/finance-entries")
def create_finance_entry(entry: FinanceEntryCreate):
    kind = entry.kind.strip().lower()
    if kind not in {"income", "expense"}:
        raise HTTPException(status_code=400, detail="kind must be income or expense")
    return create_finance_entry_record(kind, entry.category, entry.amount, entry.occurred_on, entry.note)

@app.patch("/finance-entries/{entry_id}")
def update_finance_entry(entry_id: int, payload: FinanceEntryUpdate):
    return update_finance_entry_record(entry_id, payload.amount, payload.category, payload.note)

@app.delete("/finance-entries/{entry_id}")
def delete_finance_entry(entry_id: int):
    delete_finance_entry_record(entry_id)
    return {"ok": True}

@app.post("/analyze")
def analyze_entry(entry: Entry):
    return analyze_entry_with_ai(entry.text)

@app.post("/chat")
def chat(request_body: ChatRequest):
    return chat_with_ai(request_body.message, request_body.history, request_body.location)

@app.post("/entries")
def create_entry(entry: Entry):
    ai_result = analyze_entry_with_ai(entry.text)
    category = ai_result["category"]
    with engine.connect() as conn:
        conn.execute(text(
            "INSERT INTO entries (text, category) VALUES (:text, :category)"
        ), {"text": entry.text, "category": category})
        conn.commit()
    return {
        "received": entry.text,
        "category": category,
        "summary": ai_result["summary"],
        "source": ai_result["source"],
    }
