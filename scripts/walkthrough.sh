#!/usr/bin/env bash
# Exercise storefront + comms + AI + security against a running server.
# Usage: BASE=http://127.0.0.1:8000 scripts/walkthrough.sh
set -e
B="${BASE:-http://127.0.0.1:8000}"
say(){ echo; echo "=== $* ==="; }

say "Storefront checkout (smashfat.ca)"
J=$(mktemp)
curl -s -c "$J" -H "Host: smashfat.ca" "$B/" -o /dev/null
CSRF=$(grep csrftoken "$J" | awk '{print $7}')
curl -s -b "$J" -c "$J" -H "Host: smashfat.ca" -H "Content-Type: application/json" -H "X-CSRFToken: $CSRF" -d '{"product_id":3,"qty":2}' "$B/cart/add/"; echo
curl -s -b "$J" -c "$J" -H "Host: smashfat.ca" -H "Content-Type: application/json" -H "X-CSRFToken: $CSRF" -d '{"name":"Lab","email":"lab@test.ca"}' "$B/checkout/"; echo

say "AI assistant"
HDR=(-b "$J" -c "$J" -H "Host: smashfat.ca" -H "Content-Type: application/json" -H "X-CSRFToken: $CSRF")
curl -s "${HDR[@]}" -d '{"question":"Do you ship BPC-157 to Alberta and is there a COA?"}' "$B/ai/ask/"; echo

say "Inbound SMS + STOP opt-out"
curl -s -X POST "$B/webhooks/twilio/sms/" -d "From=+15875559001" -d "To=+15873060001" -d "Body=Is Retatrutide in stock?"; echo
curl -s -X POST "$B/webhooks/twilio/sms/" -d "From=+15875559001" -d "To=+15873060001" -d "Body=STOP"; echo

say "Call -> voicemail TwiML"
curl -s -X POST "$B/webhooks/twilio/voice/?number=%2B15873060001" -d "From=+15875559002" -d "To=+15873060001" -d "CallSid=CA1" | head -c 260; echo

say "Security: honeypot + bot trap + rate limit"
curl -s "${HDR[@]}" -d '{"name":"x","email":"a@b.ca","message":"hi","company_website":"spam"}' "$B/contact/"; echo "  (bot honeypot -> silently accepted, no lead saved)"
curl -s -o /dev/null -w "  /wp-login.php -> HTTP %{http_code} (bot trap)\n" -H "Host: smashfat.ca" "$B/wp-login.php"
for i in $(seq 1 18); do curl -s -o /dev/null "${HDR[@]}" -d '{"question":"hi"}' "$B/ai/ask/"; done
curl -s -o /dev/null -w "  16th+ /ai/ask -> HTTP %{http_code} (rate limited)\n" "${HDR[@]}" -d '{"question":"hi"}' "$B/ai/ask/"

say "SEO endpoints"
curl -s -o /dev/null -w "  /robots.txt  -> %{http_code}\n" -H "Host: smashfat.ca" "$B/robots.txt"
curl -s -o /dev/null -w "  /sitemap.xml -> %{http_code}\n" -H "Host: smashfat.ca" "$B/sitemap.xml"
curl -s -o /dev/null -w "  /llms.txt    -> %{http_code}\n" -H "Host: smashfat.ca" "$B/llms.txt"
