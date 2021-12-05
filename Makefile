
test:
	# Let me print out things if necessary
	PYTHONPATH=. pytest tests/ --capture=no

lint:
	PYTHONPATH=. pylint tk/

install:
	pip install -e .

