# WhatsApp one-time codes (LightOTP)

The backend sends one-time codes over WhatsApp with [LightOTP](https://lightotp.com/en/docs)
(QMIND Tech, an official Meta tech provider; works for Syrian numbers). Two features use them:

1. **Verify a phone number** on a signed-in account (mobile registration screen, profile).
2. **Sign in with a WhatsApp code** to a verified number (no password).

LightOTP only **delivers** the code. The backend generates it, keeps it (hashed) in Redis and
checks it. Code: `backend/app/otp/` (`lightotp.py` client, `service.py` codes and limits,
`accounts.py` the two features), routes in `api/v1/users.py`, `api/v1/auth.py`,
`api/v1/admin_otp.py`. Tests: `backend/tests/test_otp.py` (mock LightOTP).

## LightOTP API (as documented on lightotp.com/en/docs/otp-messages, 2026-11-16)

| | |
|---|---|
| Base URL | `https://api.lightotp.com` (`LIGHTOTP_BASE_URL`) |
| Auth | header `X-Api-Key: <key>` (`LIGHTOTP_TOKEN`), key from the LightOTP dashboard |
| Send | `POST /SendMessage` `{"otpCode", "toPhoneE164", "languageCode"?, "idempotencyKey"?}` -> `200 {"id", "messageStatus"}` |
| Status | `POST /CheckMessageStatus` `{"id"}` -> `{"id", "messageStatus", "toPhoneE164", "createdAt", "failureCode", "failureTitle", "failureReason", "failedAt"}` |
| Statuses | `Pending`, `Sent`, `Delivered`, `Read`, `Failed`, `Deleted` |
| Errors | JSON `{"errorMessage": "..."}`, e.g. `ApiKeyNotFound` (404), `ApiKeyExpired`, `InsufficientBalance`, `InvalidphoneNumber`, `SenderNumberNotFound`, `TemplateNotFound`, a cooldown message "Please wait HH:mm:ss", 429 per-IP limit |
| Billing | 1 credit per successful send by default; failed sends are free |

Each send carries a fresh `idempotencyKey` (UUID); the one automatic retry (network error or
5xx) reuses it, so LightOTP replays the first answer instead of sending or charging twice.
`Accept-Language: en` keeps the error codes in English for the mapping below.

## Endpoints

| Endpoint | Who | What |
|---|---|---|
| `POST /api/v1/users/me/phone` `{"phone"}` | signed in | send a code to the number (202 `{"expires_in", "resend_in"}`) |
| `POST /api/v1/users/me/phone/verify` `{"phone", "code"}` | signed in | the code saves `phone_e164` + `phone_verified_at`; returns the user |
| `DELETE /api/v1/users/me/phone` | signed in | remove the number (204) |
| `POST /api/v1/auth/otp/request` `{"phone"}` | anyone | send a login code to a verified number (202, same answer for unknown numbers) |
| `POST /api/v1/auth/otp/login` `{"phone", "code"}` | anyone | token pair, like `/auth/login` |
| `GET /api/v1/admin/otp/status` | admin | configured? + settings (never the key) |
| `GET /api/v1/admin/otp/messages/{id}` | admin | LightOTP delivery status (the id is in the log line "WhatsApp code sent") |

Phone numbers are international E.164 with the country code: `+963944123456`. Spaces, dashes,
dots, brackets and a leading `00` are accepted and normalized. One number belongs to at most
one account (409 `phone_taken`).

### Errors (`detail.code`)

| HTTP | code | when |
|---|---|---|
| 400 | `invalid_code` | wrong, expired or already used code, or too many wrong tries |
| 409 | `phone_taken` | the number is verified on another account |
| 422 | `invalid_phone` | LightOTP says WhatsApp cannot reach the number |
| 429 | `otp_resend_wait` | a code was sent to this number less than `OTP_RESEND_SECONDS` ago (or LightOTP's own cooldown); `Retry-After` |
| 429 | `otp_too_many` | `OTP_PHONE_PER_HOUR` codes to this number this hour; `Retry-After` |
| 429 | `otp_busy` | LightOTP's own rate limit |
| 503 | `otp_not_configured` | `LIGHTOTP_TOKEN` is not set |
| 503 | `otp_unavailable` | LightOTP key wrong/expired, no balance, no sender or template, WhatsApp error, network (logged with LightOTP's code) |

## Rules

- Code: `OTP_LENGTH` (5) random digits, valid `OTP_TTL_SECONDS` (300). Stored in Redis only as
  an HMAC keyed with `JWT_SECRET`; Redis keys use an HMAC of the number, never the number.
- A new code replaces the previous one. A right code works once (atomic delete).
- `OTP_MAX_ATTEMPTS` (5) wrong codes drop the code: a new one must be requested.
- A phone-verification code is bound to the user it was sent for and is never a login code.
- Per number: one code every `OTP_RESEND_SECONDS` (60, the mobile timer), at most
  `OTP_PHONE_PER_HOUR` (5) per hour. Per client IP: `AUTH_OTP_IP_PER_MINUTE` (5) send requests.
  `/auth/otp/login` shares the login per-IP limit.
- `/auth/otp/request` for a number with no (active, verified) account takes the same limits and
  gives the same answer but sends nothing, so it does not reveal who is registered.
- A failed send (bad number, LightOTP down) does not use up the number's wait or hourly count.
- Neither the key, the code nor the number is logged (CI scans the test log for the test key).

## Setting the key

The key never goes in git (the repository is public). Either:

- **On the server by hand:** in `/opt/trading/.env` add the line `LIGHTOTP_TOKEN=<key>`
  (exactly this name, upper case, no quotes or spaces). The backend reads it when its container
  is recreated: the next deploy does it, or at once
  `cd /opt/trading && docker compose -f docker-compose.yml --env-file .env --env-file image.env up -d --force-recreate backend`.
  A value set this way is never overwritten by the deploy.
- **Or as a GitHub secret** `LIGHTOTP_TOKEN` (Settings -> Secrets and variables -> Actions):
  the Deploy workflow writes it into the server `.env` when the key there is missing or empty
  ("LIGHTOTP_TOKEN not set in GitHub: skipped" otherwise).
- **Locally:** `LIGHTOTP_TOKEN=<key>` in the repository's `.env` (ignored by git).

Check: `GET /api/v1/admin/otp/status` shows `"configured": true`.

The LightOTP account needs an active plan with balance; automated payment is not available yet,
so a plan is activated by their team after "Confirm Order" in the dashboard.
