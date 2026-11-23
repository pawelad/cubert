#!/bin/sh
# Copy the encrypted OpenTofu state from R2 to B2. Runs in the rclone image from
# .github/workflows/opentofu-state-backup.yml, which never gets the state passphrase.
set -uf

: "${HEALTHCHECKS_PING_URL:?must be set}"
: "${STATE_BUCKET:?must be set}"
: "${BACKUP_BUCKET:?must be set}"

ping_check() {
  # wget errors include the URL. Suppress them to keep the ping token out of logs.
  if ! wget -q -T 30 -O /dev/null "${HEALTHCHECKS_PING_URL}$1" 2>/dev/null; then
    echo "Backup heartbeat request failed." >&2
    return 1
  fi
}

status=0
ping_check /start || status=1

# A plaintext state would put every secret in it into the backup. busybox has no jq,
# and a plaintext state always holds "resources", which base64 ciphertext cannot.
encrypted() {
  grep -Eq '"encrypted_data"[[:space:]]*:[[:space:]]*"[^"]' "$1" \
    && grep -Eq '"encryption_version"[[:space:]]*:[[:space:]]*"[^"]' "$1" \
    && ! grep -q '"resources"' "$1"
}

# Check a local copy, so B2 gets the exact object that passed the check.
if ! work="$(mktemp -d)"; then
  ping_check /fail || true
  exit 1
fi
trap 'rm -rf "$work"' EXIT
state="$work/terraform.tfstate"

# Copy the one object: a missing source must fail, not hide the existing backups.
# --ignore-times uploads on every run, so an equal-size change is never skipped.
if ! rclone copyto "r2:${STATE_BUCKET}/terraform.tfstate" "$state"; then
  status=1
elif ! encrypted "$state"; then
  echo "The state is not encrypted. Refusing to copy it to the backup." >&2
  status=1
elif ! rclone copyto "$state" "b2:${BACKUP_BUCKET}/terraform.tfstate" \
  --ignore-times; then
  status=1
fi

if [ "$status" -eq 0 ]; then
  ping_check "" || status=1
else
  ping_check /fail || true
fi
exit "$status"
