test:
	pypy -m nose --with-coverage --cover-html --cover-package=bread test.py

clean:
	rm -rf cover
