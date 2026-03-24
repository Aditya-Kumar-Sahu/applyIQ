#!/bin/sh
set -eu

if [ ! -d node_modules/vue ]; then
  npm install
fi

exec "$@"
