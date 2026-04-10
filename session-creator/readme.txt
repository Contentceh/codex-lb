Как пользоваться:
cd /home/vgoro/codex-lb/session-creator
./import_session.sh

Логика:
- кладёшь .har в session-creator/sessions/
- запускаешь ./import_session.sh
- получаешь session-creator/sessions/auth_ДД.ММ.ГГГГ.json

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