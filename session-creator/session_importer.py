"""
Скрипт для генерации файла auth.json, совместимого с codex-lb.

Принимает на вход:
1. access_token (JWT токен сессии)
2. refresh_token (sessionToken от веб-версии)
3. email (почта аккаунта)

Что делает:
- Формирует валидную структуру JSON для импорта в codex-lb.
- Создает искусственный (dummy) id_token, внутри которого зашита переданная почта.
  Это необходимо, так как codex-lb парсит email именно из id_token, 
  а не из корневых полей JSON.
- Сохраняет результат в файл с именем 'auth_ДД.ММ.ГГГГ.json' в текущей директории.
"""

import json
import base64
from datetime import datetime, timezone

def create_dummy_id_token(email: str) -> str:
    """Создает фейковый JWT-токен, содержащий email в payload."""
    header = {"alg": "HS256", "typ": "JWT"}
    payload = {"email": email}
    
    # Кодируем header и payload в Base64URL без отступов (padding)
    header_b64 = base64.urlsafe_b64encode(json.dumps(header).encode('utf-8')).decode('utf-8').rstrip('=')
    payload_b64 = base64.urlsafe_b64encode(json.dumps(payload).encode('utf-8')).decode('utf-8').rstrip('=')
    
    signature = "dummy_signature"
    
    return f"{header_b64}.{payload_b64}.{signature}"

def generate_auth_file(access_token: str, refresh_token: str, email: str) -> str:
    """Генерирует JSON-файл и сохраняет его на диск."""
    
    # Получаем текущую дату для имени файла (формат: ДД.ММ.ГГГГ)
    current_date_str = datetime.now().strftime("%d.%m.%Y")
    filename = f"auth_{current_date_str}.json"
    
    # Получаем текущее время в ISO 8601 для поля last_refresh_at
    current_time_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    
    id_token = create_dummy_id_token(email)
    
    data = {
        "tokens": {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "id_token": id_token
        },
        "last_refresh_at": current_time_iso
    }
    
    try:
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print(f"Успех! Файл '{filename}' успешно создан.")
        return filename
    except Exception as e:
        print(f"Ошибка при сохранении файла: {e}")
        return ""

if __name__ == "__main__":
    print("Генератор файла auth.json для codex-lb")
    print("-" * 40)
    
    user_access_token = input("Введите access_token (начинается на eyJ...): ").strip()
    user_refresh_token = input("Введите refresh_token (sessionToken): ").strip()
    user_email = input("Введите email аккаунта: ").strip()
    
    if user_access_token and user_refresh_token and user_email:
        generate_auth_file(user_access_token, user_refresh_token, user_email)
    else:
        print("Ошибка: Все три параметра должны быть заполнены.")