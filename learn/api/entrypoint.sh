#!/bin/sh
# Bind the API ONLY to this container's address on the internal network (alias "inspector-api").
# The container is also attached to the egress network (to reach anvil and RPC_URL), but nothing listens
# there, so neither the host nor any other network can open a connection to port 8000.
set -eu
alias_name="${INSPECTOR_BIND_ALIAS:-inspector-api}"
ip="$(getent hosts "$alias_name" | awk '{ print $1; exit }')"
if [ -z "$ip" ]; then
  echo "inspector: cannot resolve '$alias_name' on the internal network; refusing to fall back to 0.0.0.0" >&2
  exit 1
fi
echo "inspector: listening on $ip:8000 (internal network only)" >&2
exec uvicorn inspector.main:app --host "$ip" --port 8000 --no-server-header --no-date-header
