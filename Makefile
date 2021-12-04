
test:
	# Let me print out things if necessary
	PYTHONPATH=./src/tkukurin pytest tests/ --capture=no

lint:
	PYTHONPATH=./src/tkukurin pylint src/tkukurin

install:
	pip install -e .

