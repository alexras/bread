test:
	nosetests --with-coverage --cover-html --cover-package=bread test.py

clean:
	rm -rf cover
