#!/bin/sh
# Start as root so a fresh volume can be given to the app user, then drop privileges.
set -eu
if [ "$(id -u)" = "0" ]; then
  mkdir -p /data/models
  chown -R app:app /data
  exec runuser -u app -- "$@"
fi
exec "$@"
