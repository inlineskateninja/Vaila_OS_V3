# Vaila OS Remote Access Setup

This guide starts Vaila as a private web app first. Build the Android app only
after the mobile web surface proves which workflows matter.

## Recommended path

Use the existing FastAPI web app as the remote client:

1. Run Vaila locally.
2. Protect API requests with a long token.
3. Expose `http://127.0.0.1:8765` through a private tunnel such as Tailscale Serve.
4. Open the tunnel URL from Android and save it to the home screen.

## Configure Vaila

Copy `.env.example` to `.env` if needed, then set:

```env
VAILA_REMOTE_ACCESS_ENABLED=true
VAILA_WEB_AUTH_TOKEN=replace-with-a-long-random-token
VAILA_ALLOWED_ORIGINS=
VAILA_SERVER_HOST=127.0.0.1
VAILA_SERVER_PORT=8765
```

Keep `VAILA_SERVER_HOST=127.0.0.1` when using a local proxy/tunnel. Use
`0.0.0.0` only for a trusted LAN test, and only with token protection enabled.

## Start the web app

```powershell
python Core_System_Files\app.py
```

Choose Web GUI mode. The app will open at:

```text
http://127.0.0.1:8765
```

The browser UI stores the token in `localStorage` on each device. If the token is
missing or wrong, the UI asks for it after the first protected API request.

## Tailscale private access

Install Tailscale on the Vaila machine and Android device, sign both into the
same tailnet, then use Tailscale Serve to publish the local Vaila port privately:

```powershell
tailscale serve http://127.0.0.1:8765
```

Use the HTTPS URL Tailscale prints on your Android device. This avoids router
port forwarding and keeps Vaila off the public internet.

When the same root URL is opened from an Android browser, Vaila serves the
phone-focused interface automatically. You can also force either surface:

```text
https://your-machine.your-tailnet.ts.net/mobile
https://your-machine.your-tailnet.ts.net/desktop
```

## Cloudflare Access option

Use Cloudflare Tunnel only when you need access from devices that cannot join
your private tailnet. Put Cloudflare Access in front of the tunnel so login
happens before requests reach Vaila.

## Android app later

Flutter is optional. If the web UI is not enough, build a Flutter client that
calls the same FastAPI endpoints:

- `/chat`
- `/api/memory/*`
- `/api/files/*`
- `/api/artifacts/*`
- `/api/advanced/*`

The backend should remain the source of truth either way.
