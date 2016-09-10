#!/bin/bash

CONF_DIR='/opt/.FLOSSbot'

function run() {
    adduser --disabled-password --gecos FLOSSbot --quiet --uid $USER_ID $USER_NAME
    if ! test -d /home/$USER_NAME/.FLOSSbot ; then
        ln -s /opt/.FLOSSbot /home/$USER_NAME/.FLOSSbot
    fi
    if ! test -e /home/$USER_NAME/.FLOSSbot/user-config.py ; then
        cp /opt/FLOSSbot/user-config.py /home/$USER_NAME/.FLOSSbot/user-config.py
    fi
    sed -i -e '/Defaults	env_reset/d' /etc/sudoers
    sed -i -e '/Defaults	secure_path/d'  /etc/sudoers
    sudo --set-home --preserve-env PATH=/opt/FLOSSbot/virtualenv/bin:$PATH --user $USER_NAME "$@"
}

if test "$1" = install ; then
    cat <<'EOF'
function FLOSSbot() {
   mkdir -p $HOME/.FLOSSbot
   sudo docker run --rm -ti \
       -v $HOME/.FLOSSbot:/opt/.FLOSSbot \
       -w /opt/.FLOSSbot \
       --env USER_ID=$(id -u) --env USER_NAME=$(id -un) \
       dachary/flossbot \
       /opt/FLOSSbot/virtualenv/bin/FLOSSbot "$@"
}

function FLOSSbot-debug() {
   mkdir -p $HOME/.FLOSSbot
   sudo docker run --rm -ti \
       -v $HOME:$HOME \
       -v $HOME/.FLOSSbot:/opt/.FLOSSbot \
       -v $(pwd):$(pwd) \
       -w $(pwd) \
       --env USER_ID=$(id -u) --env USER_NAME=$(id -un) \
       dachary/flossbot \
       bin/FLOSSbot "$@"
}

function FLOSSbot-shell() {
   mkdir -p $HOME/.FLOSSbot
   sudo docker run --rm -ti \
       -v $HOME:$HOME \
       -v $HOME/.FLOSSbot:/opt/.FLOSSbot \
       -v $(pwd):$(pwd) \
       -w $(pwd) \
       --env USER_ID=$(id -u) --env USER_NAME=$(id -un) \
       dachary/flossbot \
       "$@"
}
EOF
else
    run "$@"
fi
