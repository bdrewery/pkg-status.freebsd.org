#! /bin/sh

if [ -z "$MONGO_URI" ]; then
	echo "The MONGO_URI variable is not set."
	exit 1
fi

if [ "$1" = "venv" ]; then
	. venv/bin/activate
fi

exec gunicorn -w $(/sbin/sysctl -n hw.ncpu) pkgstatus:app -b unix:/tmp/pkg-status.sock --log-level=debug --reload
