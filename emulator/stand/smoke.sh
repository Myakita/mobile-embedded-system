#!/usr/bin/env bash
# Infrastructure smoke test for the MQTT stand: TLS handshake, password auth, and
# ACL enforcement -- not the application protocol (there's no C++ MQTT client in
# emulator/ yet). Publishes the raw bytes of protocol/vectors/telemetry-v1.json's
# wireHex and checks a subscriber gets them back unchanged, then checks a second,
# validly-authenticated-but-unauthorized user is denied both directions.
#
# Uses the eclipse-mosquitto image itself as the pub/sub client (it bundles
# mosquitto_pub/sub/passwd) so nothing needs installing on the host or runner.
set -euo pipefail
trap 'echo "smoke.sh: failed at line $LINENO: $BASH_COMMAND" >&2' ERR

cd "$(dirname "${BASH_SOURCE[0]}")"
REPO_ROOT="$(cd ../.. && pwd)"
IMAGE="eclipse-mosquitto:2"
TOPIC="mes/smoke/telemetry-v1"
AUTH_PASS="authorized-test-pw"
STRANGER_PASS="stranger-test-pw"

work="$(mktemp -d)"
trap 'docker compose -f compose.yml down -v >/dev/null 2>&1 || true; rm -rf "$work" generated 2>/dev/null || true' EXIT

echo "==> generating a throwaway CA + server cert"
rm -rf generated && mkdir -p generated/certs
openssl req -x509 -newkey rsa:2048 -days 1 -nodes \
  -keyout generated/certs/ca.key -out generated/certs/ca.crt \
  -subj "/CN=mes-stand-test-ca" >/dev/null 2>&1
openssl req -newkey rsa:2048 -nodes \
  -keyout generated/certs/server.key -out "$work/server.csr" \
  -subj "/CN=broker" >/dev/null 2>&1
# SAN covers both "broker" (the compose service name) and "localhost" (what clients
# actually connect to -- see CLIENT_NET below): without it, hostname verification
# fails for whichever one wasn't used to generate the cert. -extfile/-extensions
# works on both real OpenSSL and LibreSSL (macOS's system openssl); the newer
# -copy_extensions convenience flag doesn't exist on LibreSSL.
printf '[v3_req]\nsubjectAltName = DNS:broker,DNS:localhost,IP:127.0.0.1,IP:::1\n' > "$work/san.cnf"
openssl x509 -req -in "$work/server.csr" -CA generated/certs/ca.crt -CAkey generated/certs/ca.key \
  -CAcreateserial -out generated/certs/server.crt -days 1 \
  -extfile "$work/san.cnf" -extensions v3_req >/dev/null 2>&1

echo "==> generating test-only credentials"
docker run --rm -v "$(pwd)/generated:/out" "$IMAGE" \
  mosquitto_passwd -c -b /out/passwd authorized "$AUTH_PASS" >/dev/null
docker run --rm -v "$(pwd)/generated:/out" "$IMAGE" \
  mosquitto_passwd -b /out/passwd stranger "$STRANGER_PASS" >/dev/null

# Everything above is written by containers running as root (checked: this
# image's entrypoint never drops privileges before exec). Fail loudly and
# immediately if that somehow didn't produce a usable file, instead of letting
# it surface later as mosquitto's much less specific "Unable to open pwfile".
if [ ! -s generated/passwd ]; then
  echo "FAIL: generated/passwd wasn't created by mosquitto_passwd" >&2
  ls -la generated generated/certs >&2
  exit 1
fi

# The mosquitto *daemon* (unlike the entrypoint, and unlike mosquitto_pub/sub)
# drops to an unprivileged 'mosquitto' user internally while it's still parsing
# mosquitto.conf -- cafile/certfile/keyfile are read before that happens,
# password_file after, so a root-only-readable passwd breaks only the second one.
#
# On a native Linux host the file mosquitto_passwd wrote through the bind mount
# is owned by root (container uid 0 == host uid 0), so the host user can't chmod
# it ("Operation not permitted") -- do it from a root container instead. Docker
# Desktop on macOS remaps ownership to the host user, which is why none of this
# ever showed up locally. Throwaway test credentials; world-readable is fine.
docker run --rm -v "$(pwd)/generated:/out" "$IMAGE" chmod -R a+rX /out

echo "==> starting the broker"
docker compose -f compose.yml up -d
BROKER_CID="$(docker compose -f compose.yml ps -q broker)"
CLIENT_NET="container:${BROKER_CID}"

echo "==> waiting for TLS+auth to come up"
broker_ready=false
for _ in $(seq 1 30); do
  if docker run --rm --network "$CLIENT_NET" -v "$(pwd)/generated/certs:/certs:ro" "$IMAGE" \
       mosquitto_pub -h localhost -p 8883 --cafile /certs/ca.crt \
       -u authorized -P "$AUTH_PASS" -t "$TOPIC" -m ready 2>/dev/null; then
    broker_ready=true
    break
  fi
  sleep 1
done

if [ "$broker_ready" != true ]; then
  echo "FAIL: broker never came up (30 attempts) -- see docker compose logs above" >&2
  docker compose -f compose.yml logs broker >&2
  exit 1
fi

echo "==> preparing the telemetry-v1 wireHex payload"
python3 -c "
import json, sys
vector = json.load(open('$REPO_ROOT/protocol/vectors/telemetry-v1.json'))
sys.stdout.buffer.write(bytes.fromhex(vector['wireHex']))
" > "$work/payload.bin"

echo "==> subscribing as 'authorized' and publishing the payload"
# A freshly `docker run` subscriber takes an unpredictable moment (container
# create/start, TLS handshake, SUBSCRIBE) before it's actually listening -- a fixed
# sleep before publishing races it. Retry the pair instead of guessing a delay.
roundtrip_ok=false
for attempt in 1 2 3 4 5; do
  docker run --rm --network "$CLIENT_NET" -v "$(pwd)/generated/certs:/certs:ro" -v "$work:/work" "$IMAGE" \
    mosquitto_sub -h localhost -p 8883 --cafile /certs/ca.crt \
    -u authorized -P "$AUTH_PASS" -t "$TOPIC" -C 1 -W 10 -N > "$work/received.bin" &
  sub_pid=$!
  sleep 2

  docker run --rm --network "$CLIENT_NET" -v "$(pwd)/generated/certs:/certs:ro" -v "$work:/work" "$IMAGE" \
    mosquitto_pub -h localhost -p 8883 --cafile /certs/ca.crt \
    -u authorized -P "$AUTH_PASS" -t "$TOPIC" -f /work/payload.bin

  wait "$sub_pid" || true

  if cmp -s "$work/payload.bin" "$work/received.bin"; then
    roundtrip_ok=true
    break
  fi
  echo "   attempt $attempt: subscriber wasn't listening in time, retrying"
done

if [ "$roundtrip_ok" = true ]; then
  echo "PASS: authorized publish/subscribe round-trip matches wireHex byte for byte"
else
  echo "FAIL: received payload does not match what was published after 5 attempts" >&2
  exit 1
fi

# A denied client's own exit code proves nothing here: QoS 0 PUBLISH has no ack, so
# a denied publish still looks like success to mosquitto_pub, and mosquitto_sub
# doesn't hard-fail on a SUBACK failure code either. What actually matters is
# whether a message got delivered -- check that instead of the CLI's exit status.

echo "==> checking 'stranger' (valid login, no ACL grant) cannot subscribe"
docker run --rm --network "$CLIENT_NET" -v "$(pwd)/generated/certs:/certs:ro" "$IMAGE" \
  mosquitto_sub -h localhost -p 8883 --cafile /certs/ca.crt \
  -u stranger -P "$STRANGER_PASS" -t "$TOPIC" -C 1 -W 8 -N > "$work/stranger_received.bin" 2>/dev/null &
stranger_sub_pid=$!
sleep 3
docker run --rm --network "$CLIENT_NET" -v "$(pwd)/generated/certs:/certs:ro" -v "$work:/work" "$IMAGE" \
  mosquitto_pub -h localhost -p 8883 --cafile /certs/ca.crt \
  -u authorized -P "$AUTH_PASS" -t "$TOPIC" -f /work/payload.bin
wait "$stranger_sub_pid" || true

if [ -s "$work/stranger_received.bin" ]; then
  echo "FAIL: stranger received a message despite having no ACL grant" >&2
  exit 1
fi
echo "PASS: stranger's subscribe received nothing while a real message was published on the same topic"

echo "==> checking 'stranger' (valid login, no ACL grant) cannot publish"
docker run --rm --network "$CLIENT_NET" -v "$(pwd)/generated/certs:/certs:ro" "$IMAGE" \
  mosquitto_pub -h localhost -p 8883 --cafile /certs/ca.crt \
  -u stranger -P "$STRANGER_PASS" -t "$TOPIC" -m "stranger-should-not-be-delivered" >/dev/null 2>&1 || true
sleep 1

docker run --rm --network "$CLIENT_NET" -v "$(pwd)/generated/certs:/certs:ro" -v "$work:/work" "$IMAGE" \
  mosquitto_sub -h localhost -p 8883 --cafile /certs/ca.crt \
  -u authorized -P "$AUTH_PASS" -t "$TOPIC" -C 1 -W 10 -N > "$work/received2.bin" &
auth_sub_pid=$!
sleep 3
docker run --rm --network "$CLIENT_NET" -v "$(pwd)/generated/certs:/certs:ro" -v "$work:/work" "$IMAGE" \
  mosquitto_pub -h localhost -p 8883 --cafile /certs/ca.crt \
  -u authorized -P "$AUTH_PASS" -t "$TOPIC" -f /work/payload.bin
wait "$auth_sub_pid" || true

# -C 1 exits on the first message: if stranger's junk had leaked onto the topic,
# it would have arrived first and this compare would catch the mismatch.
if cmp -s "$work/payload.bin" "$work/received2.bin"; then
  echo "PASS: only authorized's payload was ever delivered on the topic"
else
  echo "FAIL: subscriber saw something other than authorized's payload -- stranger's publish may have leaked through" >&2
  exit 1
fi

echo "==> all stand checks passed"
