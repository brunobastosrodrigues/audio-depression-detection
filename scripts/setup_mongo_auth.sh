#!/usr/bin/env bash
# Create the Mongo root user ONCE on an existing (pre-auth) data volume so that --auth can be
# enabled without locking everyone out. On a FRESH volume the compose entrypoint creates this
# user automatically and this script is unnecessary. Idempotent: no-ops if the user exists.
# Run with the mongodb container up (auth may already be on -- localhost exception allows the
# first user creation; if a user already exists this just reports it).
set -euo pipefail
cd "$(dirname "$0")/.."
set -a; [ -f .env ] && . ./.env; set +a
: "${MONGO_USER:?set MONGO_USER in .env}"; : "${MONGO_PASS:?set MONGO_PASS in .env}"
docker exec -i mongodb mongosh --quiet admin --eval "
  try { if (db.getUser('${MONGO_USER}')) { print('user already exists'); quit(0); } } catch (e) {}
  db.createUser({user: '${MONGO_USER}', pwd: '${MONGO_PASS}', roles: [{role: 'root', db: 'admin'}]});
  print('root user ${MONGO_USER} created');
"
