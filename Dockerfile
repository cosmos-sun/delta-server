FROM jprjr/ubuntu-base:14.04
MAINTAINER hugozheng

# Ensure Apt is fully automatic and installs as little as possible (no need for -y)
ENV DEBIAN_FRONTEND noninteractive
RUN echo '\
APT::Install-Recommends "false";\
APT::Install-Suggests "false";\
APT::Get::Assume-Yes "true";\
APT::Get::Force-Yes "true";\
' >/etc/apt/apt.conf.d/01-auto-minimal

# basic ubuntu packages
RUN apt-get update && apt-get install \
    protobuf-compiler mono-gmcs \
    python python-dev python-distribute python-pip \
    wget

# add couchbase repository
RUN wget -O - http://packages.couchbase.com/ubuntu/couchbase.key | apt-key add -
RUN echo "deb http://packages.couchbase.com/ubuntu trusty trusty/main" > /etc/apt/sources.list.d/couchbase.list
RUN apt-get update

# couchbase client libraries
RUN apt-get install build-essential libcouchbase2-core libcouchbase2-libevent libcouchbase-dev
RUN pip install couchbase

# python packages
RUN pip install gevent pykka protobuf \
    bottle \
    dogpile dogpile.cache \
    dateutils
RUN apt-get install M2Crypto

RUN pip install server-reloader docopt

ADD . /app
WORKDIR /app
EXPOSE 8088

ENTRYPOINT []
CMD ["/app/run"]

# ALTERNATIVE: Set up to run via s6
# - image supports this, but don't do unless really needed
#   (best practice is to keep to one process per docker)
# - below disables cron
#RUN touch /etc/s6/cron/down
#RUN mkdir -p /etc/s6/game ; ln -s /app/* /etc/s6/game
#ENTRYPOINT ["/usr/bin/s6-svscan", "/etc/s6"]
#CMD []
