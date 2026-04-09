#!/usr/bin/env bash
# import_account.sh — import OpenAI Codex auth.json into codex-lb
# Usage: ./import_account.sh [codex-lb URL]

set -euo pipefail

CODEX_LB_URL="${1:-http://localhost:2455}"
COOKIE_JAR="$(mktemp /tmp/codex_lb_cookies.XXXXXX)"
trap 'rm -f "$COOKIE_JAR"' EXIT

# ── colors ────────────────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; BOLD='\033[1m'; RESET='\033[0m'

# ── helpers ───────────────────────────────────────────────────────────────────
decode_token_info() {
    local file="$1"
    python3 - "$file" <<'PYEOF'
import sys, json, base64

path = sys.argv[1]
try:
    with open(path) as f:
        d = json.load(f)
except Exception as e:
    print(f"ERROR: {e}")
    sys.exit(1)

tokens = d.get("tokens") or {}
id_token = tokens.get("id_token") or tokens.get("idToken") or ""
last_refresh = d.get("last_refresh") or d.get("lastRefreshAt") or "unknown"
if isinstance(last_refresh, str):
    last_refresh = last_refresh[:19]

email, plan = "unknown", "unknown"
if id_token:
    try:
        seg = id_token.split(".")[1]
        seg += "=" * (-len(seg) % 4)
        claims = json.loads(base64.b64decode(seg))
        email = claims.get("email", "unknown")
        auth = claims.get("https://api.openai.com/auth") or {}
        plan = auth.get("chatgpt_plan_type", "unknown")
    except Exception:
        pass

print(f"{email}|{plan}|{last_refresh}")
PYEOF
}

find_auth_files() {
    local -a candidates=(
        "$HOME/.codex/auth.json"
        "$HOME/.config/codex/auth.json"
        "/root/.codex/auth.json"
    )
    # also search home dirs of all users
    while IFS=: read -r user _ uid _ _ home _; do
        [[ "$uid" -ge 1000 || "$user" == "root" ]] && candidates+=("$home/.codex/auth.json")
    done < /etc/passwd

    local -a found=()
    for f in "${candidates[@]}"; do
        [[ -f "$f" ]] && found+=("$f")
    done

    # deduplicate
    local -a unique=()
    declare -A seen
    for f in "${found[@]}"; do
        real="$(realpath "$f" 2>/dev/null || echo "$f")"
        [[ -z "${seen[$real]+x}" ]] && { unique+=("$real"); seen["$real"]=1; }
    done

    printf '%s\n' "${unique[@]}"
}

check_codex_lb() {
    local resp
    resp="$(curl -sf -c "$COOKIE_JAR" -b "$COOKIE_JAR" \
        "$CODEX_LB_URL/api/dashboard-auth/session" 2>/dev/null)" || {
        echo -e "${RED}✗ Cannot reach codex-lb at $CODEX_LB_URL${RESET}"
        exit 1
    }
    local auth
    auth="$(echo "$resp" | python3 -c "import sys,json; print(json.load(sys.stdin).get('authenticated','false'))" 2>/dev/null)"
    if [[ "$auth" != "True" && "$auth" != "true" ]]; then
        echo -e "${RED}✗ Not authenticated with codex-lb dashboard.${RESET}"
        echo "  If a password is set, export CODEX_LB_PASSWORD=<pass> before running."
        # attempt password login if env var provided
        if [[ -n "${CODEX_LB_PASSWORD:-}" ]]; then
            echo -e "${YELLOW}  Trying password login...${RESET}"
            curl -sf -X POST -c "$COOKIE_JAR" -b "$COOKIE_JAR" \
                -H "Content-Type: application/json" \
                -d "{\"password\":\"$CODEX_LB_PASSWORD\"}" \
                "$CODEX_LB_URL/api/dashboard-auth/password/login" > /dev/null || {
                echo -e "${RED}  Password login failed.${RESET}"; exit 1
            }
            echo -e "${GREEN}  Logged in.${RESET}"
        else
            exit 1
        fi
    fi
}

import_file() {
    local file="$1"
    local resp
    resp="$(curl -sf -X POST -c "$COOKIE_JAR" -b "$COOKIE_JAR" \
        -F "auth_json=@$file" \
        "$CODEX_LB_URL/api/accounts/import" 2>/dev/null)" || {
        echo -e "${RED}✗ Import request failed (curl error)${RESET}"
        return 1
    }

    local code
    code="$(echo "$resp" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('error',{}).get('code',''))" 2>/dev/null)"

    if [[ -n "$code" ]]; then
        local msg
        msg="$(echo "$resp" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('error',{}).get('message','unknown error'))" 2>/dev/null)"
        echo -e "${RED}✗ Import failed: $msg${RESET}"
        return 1
    fi

    python3 - "$resp" <<'PYEOF'
import sys, json
resp = sys.argv[1]
d = json.loads(resp)
print(f"\033[1;32m✓ Account imported successfully\033[0m")
print(f"  Email   : {d.get('email', 'n/a')}")
print(f"  Plan    : {d.get('planType', 'n/a')}")
print(f"  Status  : {d.get('status', 'n/a')}")
print(f"  ID      : {d.get('accountId', 'n/a')}")
PYEOF
}

# ── main ──────────────────────────────────────────────────────────────────────
echo -e "${BOLD}${CYAN}codex-lb account importer${RESET}"
echo -e "Target: ${CYAN}$CODEX_LB_URL${RESET}"
echo

echo -e "${YELLOW}Checking codex-lb connection...${RESET}"
check_codex_lb
echo -e "${GREEN}✓ Connected${RESET}"
echo

echo -e "${YELLOW}Searching for auth.json files...${RESET}"
mapfile -t AUTH_FILES < <(find_auth_files)

if [[ ${#AUTH_FILES[@]} -eq 0 ]]; then
    echo -e "${RED}No auth.json files found.${RESET}"
    echo "Looked in: ~/.codex/auth.json, ~/.config/codex/auth.json"
    echo "You can specify a path manually:"
    echo "  $0 $CODEX_LB_URL /path/to/auth.json"
    # if a file was passed as second arg, use it directly
    if [[ -n "${2:-}" && -f "${2}" ]]; then
        AUTH_FILES=("$2")
    else
        exit 1
    fi
fi

# parse info for each file
declare -a INFOS=()
for f in "${AUTH_FILES[@]}"; do
    info="$(decode_token_info "$f")"
    INFOS+=("$info")
done

# display menu
echo -e "${BOLD}Available accounts:${RESET}"
echo
for i in "${!AUTH_FILES[@]}"; do
    IFS='|' read -r email plan last_refresh <<< "${INFOS[$i]}"
    printf "  ${BOLD}[%d]${RESET} ${GREEN}%-35s${RESET} plan=%-8s refreshed=%s\n" \
        "$((i+1))" "$email" "$plan" "$last_refresh"
    printf "      ${CYAN}%s${RESET}\n" "${AUTH_FILES[$i]}"
    echo
done

# if only one file and no tty, import automatically
if [[ ${#AUTH_FILES[@]} -eq 1 && ! -t 0 ]]; then
    SELECTED=0
else
    if [[ ${#AUTH_FILES[@]} -eq 1 ]]; then
        echo -e "  ${BOLD}[a]${RESET} Import all"
        echo -e "  ${BOLD}[q]${RESET} Quit"
        echo
        read -rp "Select [1/a/q]: " choice
    else
        echo -e "  ${BOLD}[a]${RESET} Import all"
        echo -e "  ${BOLD}[q]${RESET} Quit"
        echo
        read -rp "Select [1-${#AUTH_FILES[@]}/a/q]: " choice
    fi

    case "$choice" in
        q|Q) echo "Aborted."; exit 0 ;;
        a|A) SELECTED="all" ;;
        ''|*[!0-9]*) echo -e "${RED}Invalid choice${RESET}"; exit 1 ;;
        *) SELECTED="$((choice - 1))" ;;
    esac
fi

echo
if [[ "${SELECTED}" == "all" ]]; then
    for i in "${!AUTH_FILES[@]}"; do
        echo -e "${BOLD}Importing ${AUTH_FILES[$i]}...${RESET}"
        import_file "${AUTH_FILES[$i]}" || true
        echo
    done
else
    if [[ "$SELECTED" -lt 0 || "$SELECTED" -ge ${#AUTH_FILES[@]} ]]; then
        echo -e "${RED}Invalid selection${RESET}"; exit 1
    fi
    echo -e "${BOLD}Importing ${AUTH_FILES[$SELECTED]}...${RESET}"
    import_file "${AUTH_FILES[$SELECTED]}"
fi
