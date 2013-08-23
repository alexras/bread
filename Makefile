test:
	nosetests --with-coverage --cover-html --detailed-errors --cover-package=bread test.py

clean:
	rm -rf cover
