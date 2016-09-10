FROM ubuntu:16.04
MAINTAINER Loic Dachary "loic@dachary.org"

# nova.clouds will redirect to the fastest mirror
RUN sed -i -e 's|http://archive.ubuntu|http://nova.clouds.archive.ubuntu|' /etc/apt/sources.list
RUN apt-get update
RUN apt-get install -y python-virtualenv git sudo
RUN echo 'ALL ALL=(ALL) NOPASSWD:ALL' >> /etc/sudoers
RUN cd /opt ; git clone --recursive https://gerrit.wikimedia.org/r/pywikibot/bots/FLOSSbot ######
# install packages
RUN cd /opt/FLOSSbot ; bash -x ./bootstrap
ADD entrypoint.sh /entrypoint.sh
ENTRYPOINT ["/entrypoint.sh"]
