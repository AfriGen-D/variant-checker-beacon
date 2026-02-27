#!/bin/bash
#
# secrets.sh — Save/restore .env files to/from macOS Keychain
#
# Secrets are stored base64-encoded in Keychain under the
# account "beacon-v2". iCloud Keychain syncs them across
# your Macs automatically.
#
# Usage:
#   ./scripts/secrets.sh save      # save all .env files to Keychain
#   ./scripts/secrets.sh restore   # restore all .env files from Keychain
#   ./scripts/secrets.sh list      # show which secrets are stored
#   ./scripts/secrets.sh delete    # remove all secrets from Keychain

set -eo pipefail

KEYCHAIN_ACCOUNT="beacon-v2"

# Pairs of: keychain-service-name  file-path (relative to repo root)
SECRET_NAMES=( "env-boolean"              "env-production"    "frontend-env-production"    "frontend-env-local"  )
SECRET_FILES=( ".env.boolean"             ".env.production"   "frontend/.env.production"   "frontend/.env.local" )

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"

save_secret() {
    local name="$1"
    local file="$REPO_ROOT/$2"

    if [[ ! -f "$file" ]]; then
        echo "  SKIP  $2 (file not found)"
        return
    fi

    local encoded
    encoded="$(base64 < "$file")"

    security add-generic-password \
        -a "$KEYCHAIN_ACCOUNT" \
        -s "$name" \
        -w "$encoded" \
        -U 2>/dev/null

    echo "  SAVED $2 → Keychain ($name)"
}

restore_secret() {
    local name="$1"
    local file="$REPO_ROOT/$2"

    local encoded
    if ! encoded=$(security find-generic-password \
        -a "$KEYCHAIN_ACCOUNT" \
        -s "$name" \
        -w 2>/dev/null); then
        echo "  SKIP  $2 (not in Keychain)"
        return
    fi

    mkdir -p "$(dirname "$file")"
    echo "$encoded" | base64 -d > "$file"
    chmod 600 "$file"

    echo "  RESTORED $2 ← Keychain ($name)"
}

list_secrets() {
    echo "Checking Keychain for stored secrets..."
    echo ""
    local i
    for i in "${!SECRET_NAMES[@]}"; do
        local name="${SECRET_NAMES[$i]}"
        local file="${SECRET_FILES[$i]}"

        if security find-generic-password \
            -a "$KEYCHAIN_ACCOUNT" \
            -s "$name" -w &>/dev/null; then
            local kc_status="STORED"
        else
            local kc_status="NOT FOUND"
        fi

        if [[ -f "$REPO_ROOT/$file" ]]; then
            local local_status="exists locally"
        else
            local local_status="missing locally"
        fi

        printf "  %-10s  %-35s  (%s)\n" "$kc_status" "$file" "$local_status"
    done
}

delete_secrets() {
    echo "Removing secrets from Keychain..."
    echo ""
    local i
    for i in "${!SECRET_NAMES[@]}"; do
        local name="${SECRET_NAMES[$i]}"
        local file="${SECRET_FILES[$i]}"
        if security delete-generic-password \
            -a "$KEYCHAIN_ACCOUNT" \
            -s "$name" &>/dev/null; then
            echo "  DELETED $name ($file)"
        else
            echo "  SKIP    $name (not in Keychain)"
        fi
    done
}

usage() {
    echo "Usage: $0 {save|restore|list|delete}"
    echo ""
    echo "Commands:"
    echo "  save     Save all .env files to macOS Keychain"
    echo "  restore  Restore all .env files from Keychain"
    echo "  list     Check which secrets are stored"
    echo "  delete   Remove all secrets from Keychain"
    echo ""
    echo "Managed files:"
    local i
    for i in "${!SECRET_FILES[@]}"; do
        echo "  ${SECRET_FILES[$i]}"
    done
}

run_all() {
    local action="$1"
    local i
    for i in "${!SECRET_NAMES[@]}"; do
        "$action" "${SECRET_NAMES[$i]}" "${SECRET_FILES[$i]}"
    done
}

case "${1:-}" in
    save)
        echo "Saving secrets to Keychain..."
        echo ""
        run_all save_secret
        echo ""
        echo "Done. Secrets will sync to your other Mac via iCloud Keychain."
        ;;
    restore)
        echo "Restoring secrets from Keychain..."
        echo ""
        run_all restore_secret
        echo ""
        echo "Done. Files have mode 600 (owner read/write only)."
        ;;
    list)
        list_secrets
        ;;
    delete)
        read -rp "Are you sure? This removes secrets from Keychain. [y/N] " confirm
        if [[ "$confirm" =~ ^[Yy]$ ]]; then
            delete_secrets
        else
            echo "Cancelled."
        fi
        ;;
    *)
        usage
        exit 1
        ;;
esac
