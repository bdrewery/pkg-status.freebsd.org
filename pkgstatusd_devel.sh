#! /bin/sh

if [ -z "$MONGO_URI" ]; then
	echo "The MONGO_URI variable is not set."
	exit 1
fi

if [ "$1" = "venv" ]; then
	. venv/bin/activate
fi

#export FLASK_APP=pkgstatus:app
#exec python3 manage.py run --debug

# or
exec gunicorn pkgstatus:app -b 127.0.0.1:5000 --log-level=debug --reload
