
1) Caso OK (Receiving):
HOST="http://<odoo_host>:8069"
APIKEY="<api_key>"
UUID="$(uuidgen)"
curl -s -X POST "$HOST/api/scan/transfer" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $APIKEY" \
  -d "{
    \"event_uuid\": \"$UUID\",
    \"station_code\": \"RCV-01\",
    \"qr\": \"LOT:ABC123\"
  }" | jq

2) Duplicate (mismo event_uuid):
curl -s -X POST "$HOST/api/scan/transfer" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $APIKEY" \
  -d "{
    \"event_uuid\": \"$UUID\",
    \"station_code\": \"RCV-01\",
    \"qr\": \"LOT:ABC123\"
  }" | jq

3) QR inválido:
UUID2="$(uuidgen)"
curl -s -X POST "$HOST/api/scan/transfer" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $APIKEY" \
  -d "{
    \"event_uuid\": \"$UUID2\",
    \"station_code\": \"RCV-01\",
    \"qr\": \"ABC123\"
  }" | jq

4) Estación inexistente:
UUID3="$(uuidgen)"
curl -s -X POST "$HOST/api/scan/transfer" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $APIKEY" \
  -d "{
    \"event_uuid\": \"$UUID3\",
    \"station_code\": \"NO-EXISTE\",
    \"qr\": \"LOT:ABC123\"
  }" | jq

5) Reproceso (PT cualquiera → WIP):
UUID4="$(uuidgen)"
curl -s -X POST "$HOST/api/scan/transfer" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $APIKEY" \
  -d "{
    \"event_uuid\": \"$UUID4\",
    \"station_code\": \"RWK-01\",
    \"qr\": \"LOT:ABC123\"
  }" | jq
