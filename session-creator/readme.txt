Как пользоваться:
cd /home/vgoro/codex-lb/session-creator
./import_session.sh

Скрипт спросит источник:
1) HAR файл — как раньше, разбор через session_importer_from_har.py
2) JSON с https://chatgpt.com/api/auth/session — ответ API сохранённый в файл

Дальше можно указать путь к файлу или нажать Enter: тогда подставится единственный
подходящий файл из session-creator/sessions/ (для HAR — один *.har; для JSON —
один *.json, имя не начинается с auth_, чтобы не путать с уже готовым импортом).

Результат: session-creator/sessions/auth_<email>_ДД.ММ.ГГГГ.json
(или путь из опции -o при запуске Python напрямую).

Без меню (автоматизация):
  ./import_session.sh path/to/session.har
  ./import_session.sh --from-session-json path/to/session.json

Вариант B — только Python:
  python3 session_importer_from_har.py
  python3 session_importer_from_har.py sessions/export.har
  python3 session_importer_from_har.py --from-session-json sessions/chatgpt-session.json
  python3 session_importer_from_har.py -o ./sessions/auth.json --from-session-json ~/session.json

JSON сессии: в браузере на chatgpt.com открой DevTools → Network, найди запрос к
api/auth/session, открой Response → Save / копируй в файл UTF-8. Нужны поля
accessToken, sessionToken и при необходимости user.email (иначе email возьмётся
из JWT accessToken).


Включить не‑sanitized HAR в Chrome
1. Открой DevTools: F12 или Ctrl+Shift+I.
2. Перейди на вкладку Network.
3. Открой настройки DevTools:
    либо иконка шестерёнки в правом верхнем углу панели DevTools,
    либо клавиша F1, когда DevTools в фокусе.
4. В разделе Preferences → Network включи чекбокс Allow to generate HAR with sensitive data (или по‑русски что‑то вроде «Разрешить создание HAR‑файлов с конфиденциальными данными»).

После этого:
    На вкладке Network воспроизведи нужную сессию.
    Нажми кнопку Export HAR (иконка стрелки) и выбери вариант экспорта с конфиденциальными данными / “with sensitive data” (а не sanitized).
