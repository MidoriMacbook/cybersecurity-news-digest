import ipaddress
import re
from datetime import datetime
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

CYBER = re.compile(
    r"кибер|уязвим|утечк[\s\S]{0,120}(?:данн|информац|запис|парол|клиент)|вымогател|фишинг|вредонос|ransomware|CVE-\d{4}-\d+|"
    r"cybersecurity|(?:information|IT|network|AI|LLM) security|security (?:patch|update|vulnerability|incident)|data breach|malware|authentication|шифровальщик|"
    r"информационн\w* безопасност|защита (?:информации|данных|модели)|компьютерн\w* инцидент|цифровая безопасность|безопасность ИТ|"
    r"\b(?:SOC|MSSP|MDR|XDR|EDR|SIEM|SOAR|NGFW|WAF|IDS|IPS|DLP|NAC|SASE|ZTNA|DevSecOps|AppSec|DDoS|APT|RCE|MFA|IAM|PAM)\b|"
    r"Zero Trust|prompt injection|data poisoning|model leakage|deepfake|AI governance|генеративный ИИ|ИИ-агент|"
    r"социальная инженерия|спуфинг|ботнет|троян|бэкдор|кейлоггер|стилер|supply chain attack|exploit|zero.day|"
    r"взлом|компрометаци|brute force|credential stuffing|обход аутентификации|повышение привилегий|удалённое выполнение кода|"
    r"резервное копирование|реагирование на инцидент|сертификация СЗИ|субъект КИИ|категорирование КИИ|ГосСОПКА|НКЦКИ",
    re.IGNORECASE,
)
INJECTION = re.compile(
    r"игнорируй|ignore (?:all |previous)|отправь результат|system prompt|API.?ключ|выполни команд",
    re.IGNORECASE,
)
AD = re.compile(
    r"реклам[аы]|на правах рекламы|купите|скидк[аи]|sponsored|advertisement", re.IGNORECASE
)
PRELIMINARY = re.compile(
    r"предварител|неподтвержд|предполож|по данным|сообщает|проверка продолжается|слух|достоверност[\s\S]{0,80}не установ|не подтвержден|не подтверждён|preliminary|unconfirmed|alleged",
    re.IGNORECASE,
)


def parse_date(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        date = datetime.fromisoformat(value)
        if date.tzinfo:
            date.astimezone(ZoneInfo("Europe/Moscow"))
        return date if date.tzinfo else None
    except (ValueError, OverflowError):
        return None


def valid_url(value: str | None) -> bool:
    if not value:
        return False
    try:
        parts = urlsplit(value)
        if (
            parts.scheme not in {"https", "http"}
            or not parts.hostname
            or parts.username
            or parts.password
        ):
            return False
        if parts.port and parts.port not in {80, 443}:
            return False
        if parts.hostname.lower() in {
            "localhost",
            "localhost.localdomain",
        } or parts.hostname.endswith(".local"):
            return False
        try:
            return ipaddress.ip_address(parts.hostname).is_global
        except ValueError:
            return "." in parts.hostname
    except ValueError:
        return False


def is_demo_url(value: str | None) -> bool:
    if not value:
        return False
    host = urlsplit(value).hostname or ""
    return host == "example.org" or host.endswith(".example.org")


def safe_sentences(text: str) -> list[str]:
    sentences = re.split(r"(?<=[.!?])\s+|[\r\n]+", text)
    return [s.strip() for s in sentences if s.strip() and not INJECTION.search(s)]


def event_key(title: str, text: str) -> str:
    cves = sorted(set(re.findall(r"CVE-\d{4}-\d{4,}", title + " " + text, re.IGNORECASE)))
    if cves:
        return "+".join(c.upper() for c in cves)
    return re.sub(r"[^\w]+", " ", title.casefold()).strip()
