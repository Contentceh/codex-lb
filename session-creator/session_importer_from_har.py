"""
Скрипт для генерации файла auth.json, совместимого с codex-lb, из HAR-файла.

Что делает:
- находит access_token в заголовке Authorization;
- собирает refresh_token из cookie __Secure-next-auth.session-token(.N);
- извлекает email из access_token или cookie oai-client-auth-info;
- сохраняет результат в файл auth_ДД.ММ.ГГГГ.json.

По умолчанию работает с директорией ./sessions:
- ищет HAR там;
- рендерит JSON туда же.

Использование:
    python session_importer_from_har.py
    python session_importer_from_har.py path/to/session.har
"""

from __future__ import annotations

import argparse
import base64
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import unquote


SESSIONS_DIR_NAME = "sessions"


@dataclass(frozen=True)
class SessionData:
    access_token: str
    refresh_token: str
    email: str


def normalize_value(value: str) -> str:
    """Удаляет пробелы и внешние кавычки."""
    cleaned = value.strip()
    if len(cleaned) >= 2 and cleaned[0] == cleaned[-1] and cleaned[0] in {'"', "'"}:
        return cleaned[1:-1].strip()
    return cleaned


def create_dummy_id_token(email: str) -> str:
    """Создает фейковый JWT-токен, содержащий email в payload."""
    header = {"alg": "HS256", "typ": "JWT"}
    payload = {"email": email}

    header_b64 = base64.urlsafe_b64encode(json.dumps(header).encode("utf-8")).decode("utf-8").rstrip("=")
    payload_b64 = base64.urlsafe_b64encode(json.dumps(payload).encode("utf-8")).decode("utf-8").rstrip("=")

    return f"{header_b64}.{payload_b64}.dummy_signature"


def decode_jwt_payload(token: str) -> dict[str, Any]:
    """Декодирует payload JWT без проверки подписи."""
    parts = token.split(".")
    if len(parts) < 2:
        raise ValueError("Некорректный JWT access_token")

    payload_b64 = parts[1]
    payload_b64 += "=" * (-len(payload_b64) % 4)

    try:
        decoded = base64.urlsafe_b64decode(payload_b64.encode("utf-8"))
        payload = json.loads(decoded.decode("utf-8"))
    except (ValueError, json.JSONDecodeError) as exc:
        raise ValueError("Не удалось декодировать payload access_token") from exc

    if not isinstance(payload, dict):
        raise ValueError("Payload access_token имеет неожиданный формат")

    return payload


def extract_access_token(entry: dict[str, Any]) -> str | None:
    request = entry.get("request", {})
    headers = request.get("headers", [])

    for header in headers:
        name = str(header.get("name", "")).lower()
        if name != "authorization":
            continue

        value = normalize_value(str(header.get("value", "")))
        if value.startswith("Bearer "):
            return normalize_value(value.removeprefix("Bearer "))

    return None


def collect_request_cookies(entry: dict[str, Any]) -> dict[str, str]:
    request = entry.get("request", {})
    cookies = request.get("cookies", [])

    collected: dict[str, str] = {}
    for cookie in cookies:
        name = str(cookie.get("name", "")).strip()
        value = normalize_value(str(cookie.get("value", "")))
        if name and value:
            collected[name] = value

    return collected


def extract_refresh_token(cookies: dict[str, str]) -> str | None:
    direct_name = "__Secure-next-auth.session-token"
    if direct_name in cookies:
        return cookies[direct_name]

    prefix = f"{direct_name}."
    parts: list[tuple[int, str]] = []

    for name, value in cookies.items():
        if not name.startswith(prefix):
            continue

        suffix = name.removeprefix(prefix)
        if not suffix.isdigit():
            continue

        parts.append((int(suffix), value))

    if not parts:
        return None

    return "".join(value for _, value in sorted(parts, key=lambda item: item[0]))


def extract_email_from_auth_cookie(cookies: dict[str, str]) -> str | None:
    raw_value = cookies.get("oai-client-auth-info")
    if not raw_value:
        return None

    try:
        decoded_value = unquote(raw_value)
        payload = json.loads(decoded_value)
    except json.JSONDecodeError:
        return None

    user = payload.get("user")
    if not isinstance(user, dict):
        return None

    email = user.get("email")
    if not isinstance(email, str):
        return None

    email = normalize_value(email)
    return email or None


def extract_email_from_access_token(access_token: str) -> str | None:
    payload = decode_jwt_payload(access_token)

    profile_claim = payload.get("https://api.openai.com/profile")
    if isinstance(profile_claim, dict):
        email = profile_claim.get("email")
        if isinstance(email, str):
            normalized = normalize_value(email)
            if normalized:
                return normalized

    email = payload.get("email")
    if isinstance(email, str):
        normalized = normalize_value(email)
        if normalized:
            return normalized

    return None


def parse_har_file(har_path: Path) -> SessionData:
    try:
        har_payload = json.loads(har_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"HAR-файл '{har_path}' содержит некорректный JSON") from exc

    log = har_payload.get("log")
    if not isinstance(log, dict):
        raise ValueError("HAR-файл не содержит секцию log")

    entries = log.get("entries")
    if not isinstance(entries, list) or not entries:
        raise ValueError("HAR-файл не содержит записей log.entries")

    access_token: str | None = None
    refresh_token: str | None = None
    email: str | None = None

    for entry in reversed(entries):
        if not isinstance(entry, dict):
            continue

        cookies = collect_request_cookies(entry)

        if access_token is None:
            access_token = extract_access_token(entry)

        if refresh_token is None:
            refresh_token = extract_refresh_token(cookies)

        if email is None:
            email = extract_email_from_auth_cookie(cookies)

        if access_token and refresh_token and email:
            break

    if access_token and email is None:
        email = extract_email_from_access_token(access_token)

    missing_fields = [
        field_name
        for field_name, field_value in (
            ("access_token", access_token),
            ("refresh_token", refresh_token),
            ("email", email),
        )
        if not field_value
    ]

    if missing_fields:
        missing = ", ".join(missing_fields)
        raise ValueError(f"Не удалось извлечь из HAR: {missing}")

    if access_token is None or refresh_token is None or email is None:
        raise ValueError("Не удалось извлечь полные данные сессии из HAR")

    return SessionData(
        access_token=access_token,
        refresh_token=refresh_token,
        email=email,
    )


def sanitize_email_for_filename(email: str) -> str:
    sanitized = email.strip().lower().replace("@", "_at_")
    sanitized = re.sub(r"[^a-z0-9._-]+", "_", sanitized)
    sanitized = sanitized.strip("._-")
    return sanitized or "unknown"


def default_output_path(directory: Path, email: str) -> Path:
    current_date_str = datetime.now().strftime("%d.%m.%Y")
    safe_email = sanitize_email_for_filename(email)
    return directory / f"auth_{safe_email}_{current_date_str}.json"


def default_sessions_dir(working_directory: Path) -> Path:
    return working_directory / SESSIONS_DIR_NAME


def write_auth_file(session_data: SessionData, output_path: Path) -> Path:
    current_time_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    id_token = create_dummy_id_token(session_data.email)

    payload = {
        "tokens": {
            "access_token": session_data.access_token,
            "refresh_token": session_data.refresh_token,
            "id_token": id_token,
        },
        "last_refresh_at": current_time_iso,
    }

    output_path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return output_path


def resolve_har_path(raw_path: str | None, search_directory: Path) -> Path:
    if raw_path:
        har_path = Path(raw_path).expanduser().resolve()
        if not har_path.is_file():
            raise ValueError(f"HAR-файл не найден: {har_path}")
        return har_path

    har_files = sorted(path for path in search_directory.glob("*.har") if path.is_file())

    if not har_files:
        raise ValueError(f"В директории '{search_directory}' не найдено ни одного HAR-файла")

    if len(har_files) > 1:
        file_list = ", ".join(path.name for path in har_files)
        raise ValueError(
            "Найдено несколько HAR-файлов. Укажите путь явно: "
            f"{file_list}"
        )

    return har_files[0]


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Создает auth_ДД.ММ.ГГГГ.json для codex-lb из HAR-файла.",
    )
    parser.add_argument(
        "har_file",
        nargs="?",
        help="Путь до HAR-файла. Если не указан, будет использован единственный *.har в ./sessions.",
    )
    parser.add_argument(
        "-o",
        "--output",
        help="Путь до выходного JSON-файла. По умолчанию: ./sessions/auth_email_ДД.ММ.ГГГГ.json",
    )
    return parser


def main() -> int:
    parser = build_argument_parser()
    args = parser.parse_args()
    working_directory = Path.cwd()
    sessions_dir = default_sessions_dir(working_directory)

    try:
        har_path = resolve_har_path(args.har_file, sessions_dir)
        session_data = parse_har_file(har_path)

        if args.output:
            output_path = Path(args.output).expanduser().resolve()
        else:
            sessions_dir.mkdir(parents=True, exist_ok=True)
            output_path = default_output_path(sessions_dir, session_data.email)

        created_file = write_auth_file(session_data, output_path)
    except ValueError as exc:
        print(f"Ошибка: {exc}")
        return 1
    except OSError as exc:
        print(f"Ошибка записи файла: {exc}")
        return 1

    print(f"Успех! Файл '{created_file}' успешно создан.")
    print(f"Email: {session_data.email}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
