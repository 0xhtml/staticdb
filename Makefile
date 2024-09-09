.PHONY: build run test

build: env

run: build
	env/bin/uvicorn staticdb:app

env: requirements.txt
	test -d env || python -m venv env
	env/bin/pip install -r requirements.txt
	touch env
