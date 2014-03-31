from setuptools import setup

setup(name='bread',
      version='1.5.1',
      description='Binary format parsing made easier',
      url='https://github.com/alexras/bread',
      author='Alex Rasmussen',
      author_email='alexras@acm.org',
      classifiers = [
          "Development Status :: 4 - Beta",
          "Environment :: Other Environment",
          "Intended Audience :: Developers",
          "License :: OSI Approved :: MIT License",
          "Natural Language :: English",
          "Operating System :: OS Independent",
          "Programming Language :: Python",
          "Programming Language :: Python :: 2.7",
          "Topic :: Software Development :: Libraries :: Python Modules"],
      license='MIT',
      packages=['bread'],
      requires=['bitstring'])
