FLOSSbot
========

FLOSSbot is a command-line toolbox for the wikidata `FLOSS project <https://www.wikidata.org/wiki/Wikidata:WikiProject_Informatics/FLOSS>`_

Documentation : http://FLOSSbot.readthedocs.org/
Home page : https://www.wikidata.org/wiki/User:FLOSSbot

Installation
============

* Install Docker http://docs.docker.com/engine/installation/

* Copy the following to ``~/.bashrc``::

    eval "$(docker run dachary/flossbot install)"

* Verify that it works::

    FLOSSbot --help

Hacking
=======

For best results, develop in Ubuntu 16.04 as a normal user (not root).

* Get the code::

   git clone https://gerrit.wikimedia.org/r/pywikibot/bots/FLOSSbot

* Set up the development environment::

   deactivate || true ; source bootstrap

  This creates a virtualenv containing the :code:`FLOSSbot`
  executable and everything it needs to work.

* Activate the development environment and run :code:`FLOSSbot`::

   source virtualenv/bin/activate
   FLOSSbot --help

* Run the tests::

   tox

* Run a single test::

   tox -e py3 -- -s -k test_run tests/test_source_code_repository.py

* Fix import ordering

   pip install flake8-isort
   isort --recursive --diff bin tests FLOSSbot # to display
   isort --recursive --apply bin tests FLOSSbot # to modify
  
* Run FLOSSbot using the dev environment of the current working
  directory in the docker container instead of the installed version::

   eval "$(docker/entrypoint.sh install)"
   FLOSSbot --help # use what is installed in the container
   FLOSSbot-debug --help # use FLOSSbot from the working directory
   FLOSSbot-shell bash # login the container and debug

* Check the documentation : rst2html < README.rst > /tmp/a.html

* pip freeze to compare and update requirements.txt

Release management
==================

* Prepare a new version

 - version=0.1.0 ; perl -pi -e "s/^version.*/version = $version/" setup.cfg ; for i in 1 2 ; do python setup.py sdist ; amend=$(git log -1 --oneline | grep --quiet "version $version" && echo --amend) ; git commit $amend -m "version $version" ChangeLog setup.cfg ; git tag -a -f -m "version $version" $version ; done

* Publish a new version

 - python setup.py sdist upload --sign
 - git push ; git push --tags
 - docker rmi dachary/flossbot
 - docker build --no-cache --tag dachary/flossbot docker
 - docker build --tag dachary/flossbot:0.1.0 docker
 - docker login
 - docker push dachary/flossbot
 - docker push dachary/flossbot:0.1.0

* pypi maintenance

 - python setup.py register # if the project does not yet exist
 - trim old versions at https://pypi.python.org/pypi/FLOSSbot
