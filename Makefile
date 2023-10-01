
PY ?= python

test:
	PYTHONPATH=. $(PY) -m pytest tests/ --capture=no

lint:
	PYTHONPATH=. $(PY) -m pylint tk/

install:
	$(PY) -m pip install -e .

