test-pypy:
	pypy -m nose --with-coverage --cover-html --cover-package=bread test.py

test:
	python -m nose --with-coverage --cover-html --cover-package=bread test.py
clean:
	rm -rf cover
