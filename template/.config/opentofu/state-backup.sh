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

# Copy the one object: a missing source must fail, not hide the existing backups.
# --ignore-times uploads on every run, so an equal-size change is never skipped.
rclone copyto "r2:${STATE_BUCKET}/terraform.tfstate" \
  "b2:${BACKUP_BUCKET}/terraform.tfstate" \
  --ignore-times || status=1

if [ "$status" -eq 0 ]; then
  ping_check "" || status=1
else
  ping_check /fail || true
fi
exit "$status"
