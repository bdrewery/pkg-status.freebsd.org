#! /bin/sh
source venv/bin/activate

while :; do
	python gather_to_mongo.py
	sleep 60
done
