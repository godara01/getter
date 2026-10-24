from __future__ import annotations

import json
import threading
from datetime import UTC, datetime, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from sqlalchemy import select

from getter_api.models import User
from getter_api.settings import Settings


@pytest.fixture
def signing_keys():
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(key.public_key()))
    public.update(kid="test", use="sig", alg="RS256")

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.end_headers()
            self.wfile.write(json.dumps({"keys": [public]}).encode())

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield key, f"http://127.0.0.1:{server.server_port}"
    server.shutdown()
    server.server_close()
    thread.join()


@pytest.mark.parametrize(
    "invalid", [None, "expired", "issuer", "signature", "party", "missing_exp"]
)
async def test_clerk_tokens(make_client, signing_keys, invalid):
    key, url = signing_keys
    client = await make_client(
        auth_mode="clerk",
        clerk_issuer="https://clerk.test",
        clerk_jwks_url=url,
        clerk_authorized_parties=["http://localhost:3000"],
    )
    claims = {
        "sub": "user_test",
        "iss": "https://clerk.test",
        "azp": "http://localhost:3000",
        "exp": datetime.now(UTC) + timedelta(minutes=5),
    }
    if invalid == "expired":
        claims["exp"] = datetime.now(UTC) - timedelta(minutes=5)
    if invalid == "issuer":
        claims["iss"] = "https://attacker.test"
    if invalid == "party":
        claims["azp"] = "https://attacker.test"
    if invalid == "missing_exp":
        del claims["exp"]
    if invalid == "signature":
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    token = jwt.encode(claims, key, algorithm="RS256", headers={"kid": "test"})
    async with client:
        response = await client.get("/sessions", headers={"authorization": f"Bearer {token}"})
        assert response.status_code == (401 if invalid else 200)
        if not invalid:
            assert (
                await client.get("/sessions", headers={"authorization": f"Bearer {token}"})
            ).status_code == 200
        assert (
            await client.get("/sessions", headers={"x-dev-user-email": "dev@test.com"})
        ).status_code == 401
    async with client._transport.app.state.sessionmaker() as db:
        users = list(await db.scalars(select(User)))
        assert len(users) == (0 if invalid else 1)
        if users:
            assert users[0].clerk_user_id == "user_test"
            assert users[0].role == "candidate"


@pytest.mark.parametrize("environment", ["staging", "production"])
def test_deployed_auth_settings(environment):
    with pytest.raises(ValueError, match="dev auth"):
        Settings(environment=environment)
    with pytest.raises(ValueError, match="Clerk issuer"):
        Settings(environment=environment, auth_mode="clerk")
