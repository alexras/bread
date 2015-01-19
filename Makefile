test-nose:
	nosetests --with-coverage --cover-package=bread test.py

test:
	tox

clean:
	rm -rf cover
