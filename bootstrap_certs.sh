#!/usr/bin/env bash
set -euo pipefail

###############################################################################
###############################################################################
##                                                                           ##
##   !!!  DEVELOPMENT / TESTING ONLY — DO NOT USE IN DEPLOYMENT  !!!         ##
##                                                                           ##
##   Model: this (local) machine acts as a third-party CA. In 'cloud'        ##
##   mode it provisions BOTH protocol parties over scp. IMPORTANT:           ##
##     - both parties' PRIVATE KEYS are generated here and SHIPPED OVER      ##
##       THE NETWORK (scp). In a real deployment each party generates its    ##
##       own key locally and only a CSR ever leaves the machine;             ##
##   Acceptable ONLY for benchmarking on disposable test machines.           ##
##                                                                           ##
###############################################################################
###############################################################################

CERT_DIR=certs
REMOTE_DIR="~/volepsi/certs"

usage() {
    echo "Usage:"
    echo "  $0 local"
    echo "      Generate CA + receiver + sender certs in ./certs for"
    echo "      single-machine runs (server cert issued for localhost)."
    echo "      All keys stay on this machine."
    echo ""
    echo "  $0 cloud <RECEIVER_SSH_HOST> <SENDER_SSH_HOST>"
    echo "      Run on YOUR LOCAL machine (acts as CA)."
    echo "        1. generates CA key + cert (reused if already present)"
    echo "        2. generates receiver and sender keys + certs locally"
    echo "        3. scp's to each machine ONLY its own key + cert,"
    echo "           plus ca.cert.pem"
    echo "        4. shreds both parties' private keys from this machine"
    echo "      The receiver cert's CN/SAN is derived from RECEIVER_SSH_HOST"
    echo "      (text after the '@'), so pass the real IP there — not an"
    echo "      ssh-config alias."
    echo ""
    echo "Examples:"
    echo "  $0 local"
    echo "  $0 cloud root@176.119.63.198 root@176.119.60.17"
    exit 1
}

[ $# -ge 1 ] || usage
MODE="$1"

mkdir -p "$CERT_DIR"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
make_ca() {
    # Reused across runs so re-provisioning doesn't rotate the trust root.
    if [ ! -f "$CERT_DIR/ca.key.pem" ]; then
        echo "[ca] Generating new CA ..."
        openssl genrsa -out "$CERT_DIR/ca.key.pem" 2048
        openssl req -x509 -new -nodes \
          -key "$CERT_DIR/ca.key.pem" \
          -sha256 -days 3650 \
          -out "$CERT_DIR/ca.cert.pem" \
          -subj "/C=PL/ST=Test/L=Test/O=PSI-CA/CN=PSI-CA"
    else
        echo "[ca] Reusing existing CA in $CERT_DIR/."
    fi
}

make_receiver_cert() {
    # $1 = CN/SAN name for the TLS server (localhost or public IP)
    local SERVER_NAME="$1"
    openssl genrsa -out "$CERT_DIR/receiver.key.pem" 2048
    openssl req -new \
      -key "$CERT_DIR/receiver.key.pem" \
      -out "$CERT_DIR/receiver.csr.pem" \
      -subj "/C=PL/ST=Test/L=Test/O=PSI/CN=$SERVER_NAME"
    # SAN covers the given name plus localhost so the cert also works
    # when testing against 127.0.0.1.
    local SAN="DNS:localhost,IP:127.0.0.1"
    if [[ "$SERVER_NAME" =~ ^[0-9.]+$ ]]; then
        SAN="IP:$SERVER_NAME,$SAN"
    elif [ "$SERVER_NAME" != "localhost" ]; then
        SAN="DNS:$SERVER_NAME,$SAN"
    fi
    openssl x509 -req \
      -in "$CERT_DIR/receiver.csr.pem" \
      -CA "$CERT_DIR/ca.cert.pem" \
      -CAkey "$CERT_DIR/ca.key.pem" \
      -CAcreateserial \
      -out "$CERT_DIR/receiver.cert.pem" \
      -days 365 -sha256 \
      -extfile <(printf "subjectAltName=%s" "$SAN")
}

make_sender_cert() {
    openssl genrsa -out "$CERT_DIR/sender.key.pem" 2048
    openssl req -new \
      -key "$CERT_DIR/sender.key.pem" \
      -out "$CERT_DIR/sender.csr.pem" \
      -subj "/C=PL/ST=Test/L=Test/O=PSI/CN=sender"
    openssl x509 -req \
      -in "$CERT_DIR/sender.csr.pem" \
      -CA "$CERT_DIR/ca.cert.pem" \
      -CAkey "$CERT_DIR/ca.key.pem" \
      -CAcreateserial \
      -out "$CERT_DIR/sender.cert.pem" \
      -days 365 -sha256
}

cleanup_csrs() {
    rm -f "$CERT_DIR"/*.csr.pem
}

case "$MODE" in

  local)
    make_ca
    make_receiver_cert "localhost"
    make_sender_cert
    cleanup_csrs
    echo "[local] All certs in $CERT_DIR/ (server cert CN=localhost)."
    ;;

  cloud)
    [ $# -ge 3 ] || usage
    RECEIVER_HOST="$2"
    SENDER_HOST="$3"
    SERVER_IP="${RECEIVER_HOST#*@}"

    make_ca
    make_receiver_cert "$SERVER_IP"
    make_sender_cert
    cleanup_csrs

    ###########################################################################
    ##  !!! DEV-ONLY SHORTCUT: shipping PRIVATE KEYS over the network.    !!##
    ##  Each machine receives ONLY its own key — the receiver never sees   ##
    ##  the sender's key and vice versa.                                   ##
    ###########################################################################
    echo "[scp] Provisioning receiver: $RECEIVER_HOST ..."
    ssh "$RECEIVER_HOST" "mkdir -p $REMOTE_DIR"
    scp "$CERT_DIR/receiver.key.pem" \
        "$CERT_DIR/receiver.cert.pem" \
        "$CERT_DIR/ca.cert.pem" \
        "$RECEIVER_HOST:$REMOTE_DIR/"

    echo "[scp] Provisioning sender: $SENDER_HOST ..."
    ssh "$SENDER_HOST" "mkdir -p $REMOTE_DIR"
    scp "$CERT_DIR/sender.key.pem" \
        "$CERT_DIR/sender.cert.pem" \
        "$CERT_DIR/ca.cert.pem" \
        "$SENDER_HOST:$REMOTE_DIR/"

    # After provisioning, each party key should exist ONLY on the machine
    # that uses it. (The CA key stays here — this machine is the CA.)
    shred -u "$CERT_DIR/receiver.key.pem" "$CERT_DIR/sender.key.pem" 2>/dev/null \
      || rm -f "$CERT_DIR/receiver.key.pem" "$CERT_DIR/sender.key.pem"
    echo "[cleanup] Party private keys shredded from this machine."

    echo ""
    echo "Done."
    echo "  This machine (CA) : ca.key.pem, ca.cert.pem, receiver.cert.pem, sender.cert.pem"
    echo "  $RECEIVER_HOST : receiver.key.pem, receiver.cert.pem, ca.cert.pem"
    echo "  $SENDER_HOST : sender.key.pem, sender.cert.pem, ca.cert.pem"
    echo "  Receiver cert CN/SAN : $SERVER_IP"
    ;;

  *)
    usage
    ;;

esac
