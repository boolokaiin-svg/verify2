# Boolok backend connection

Deploy this directory as the Python service root. Use `pip install -r requirements.txt`
and `uvicorn app:app --host 0.0.0.0 --port $PORT` (one worker).

Set `VERIFICATION_SERVICE_TOKEN` to the same secret on both Render services.
Keep the AI provider key configured on the Python service and portal credentials
configured for automated portal access. Environment variables take precedence over `.env`.

On the backend, set:

```
VERIFICATION_SERVICE_URL=https://verify2-t5wb.onrender.com
```

Redeploy the verification service and restart/redeploy the backend after changing
environment variables. The local backend `.env` does not update Render settings.
From the backend directory run `node scripts/check-verification.js` to check
authenticated readiness. Then verify a document through the signed-in app to
exercise the AI provider, government portal and MongoDB history together.

The adapter accepts `document` (and legacy `file`), plus optional `manual_ec`
and `manual_patta`. It implements authenticated readiness, verification,
per-account certificate downloads and account cleanup for the backend.

Certificates use `VERIFICATION_STORAGE_DIR` or the local `storage` directory.
Use a persistent disk mounted at that configured directory if certificates must
survive service restarts or redeploys. An ephemeral deployment cannot guarantee
that old audit certificate links remain downloadable.

Adapter test (requires httpx in the test environment):
`python test_integration.py`. This test uses a stub engine and sends no documents
to external AI or portal services.
