#! /bin/sh

. venv/bin/activate

exec gunicorn -w $(/sbin/sysctl -n hw.ncpu) pkgstatus:app -b unix:/tmp/pkg-status.sock --log-level=debug
