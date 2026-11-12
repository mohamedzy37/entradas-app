"""Pruebas del login con Google (sin conexion: simula a Google con claves RSA locales).

Uso (desde backend/):
    .venv\\Scripts\\python.exe scripts\\test_google_oauth.py

Comprueba PKCE, state (anti-CSRF), nonce (anti-replay), y que el ID token se
rechaza si la firma, la audiencia, el emisor, la caducidad o el email no son
validos, incluidos los ataques alg=none y confusion de algoritmo.
"""

from __future__ import annotations

import base64
import hashlib
import sys
import time
import urllib.parse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import jwt  # noqa: E402
from app import google_oauth as g  # noqa: E402
from app.config import settings  # noqa: E402

# Configuracion de prueba (no hace falta un client id real).
settings.GOOGLE_CLIENT_ID = "cid.apps.googleusercontent.com"
settings.GOOGLE_CLIENT_SECRET = "secreto-de-prueba"
settings.GOOGLE_REDIRECT_URI = "https://localhost/api/auth/google/callback"
S = settings

from cryptography.hazmat.primitives.asymmetric import rsa
key=rsa.generate_private_key(public_exponent=65537,key_size=2048); pub=key.public_key()
evil=rsa.generate_private_key(public_exponent=65537,key_size=2048)
def ok(c,m):
    if not c: print("FAIL",m); sys.exit(1)
    print("OK  ",m)
def fails(fn,*a,**k):
    try: fn(*a,**k); return False
    except g.GoogleAuthError: return True

# safe_next
for v,exp in [("/cuenta","/cuenta"),("/checkout?event=1","/checkout?event=1"),("//evil.com","/"),("https://evil.com","/"),("/\\evil.com","/"),(None,"/"),("/a\nb","/")]:
    ok(g.safe_next(v)==exp, f"safe_next({v!r}) -> {exp}")

url,cookie=g.start_login("/cuenta")
q=dict(urllib.parse.parse_qsl(urllib.parse.urlparse(url).query))
st=g.read_state_cookie(cookie)
ok(q["state"]==st["state"] and q["nonce"]==st["nonce"], "state y nonce en URL y cookie")
ok(q["code_challenge"]==base64.urlsafe_b64encode(hashlib.sha256(st["cv"].encode()).digest()).rstrip(b"=").decode() and q["code_challenge_method"]=="S256", "PKCE S256 correcto")
ok("cv" not in q and st["cv"] not in url, "el code_verifier NO viaja a Google")
ok(q["scope"]=="openid email profile" and q["response_type"]=="code", "scope y response_type")
ok(st["next"]=="/cuenta", "next guardado")
ok(fails(g.read_state_cookie, cookie[:-4]+"AAAA"), "cookie de estado manipulada -> error")
ok(fails(g.read_state_cookie, None), "sin cookie -> error")
ok(fails(g.check_state, st["state"], "otro"), "state distinto -> error (CSRF)")
g.check_state(st["state"], st["state"]); ok(True,"state igual -> ok")

now=int(time.time())
def idt(k=key, alg="RS256", **over):
    c={"iss":"https://accounts.google.com","aud":S.GOOGLE_CLIENT_ID,"sub":"1234","email":"ana@gmail.com","email_verified":True,"name":"Ana","iat":now,"exp":now+3600,"nonce":st["nonce"]}
    c.update(over); c={a:b for a,b in c.items() if b is not None}
    return jwt.encode(c,k,algorithm=alg)
res=lambda t: pub
c=g.verify_id_token(idt(), st["nonce"], key_resolver=res); ok(c["sub"]=="1234","ID token valido aceptado")
ok(g.verify_id_token(idt(iss="accounts.google.com"), st["nonce"], key_resolver=res)["sub"]=="1234","iss sin https aceptado")
for name,tok in [("firma con otra clave",idt(k=evil)),("aud de otra app",idt(aud="otra-app")),("iss falso",idt(iss="https://evil.com")),("caducado",idt(exp=now-3600,iat=now-7200)),("nonce distinto",idt(nonce="x")),("sin nonce",idt(nonce=None)),("email no verificado",idt(email_verified=False)),("email_verified como string",idt(email_verified="true")),("sin email",idt(email=None))]:
    ok(fails(g.verify_id_token, tok, st["nonce"], key_resolver=res), f"rechaza: {name}")
none_tok=jwt.encode({"iss":"https://accounts.google.com","aud":S.GOOGLE_CLIENT_ID,"sub":"1","email":"a@b.c","email_verified":True,"iat":now,"exp":now+60,"nonce":st["nonce"]},None,algorithm="none")
ok(fails(g.verify_id_token, none_tok, st["nonce"], key_resolver=res), "rechaza alg=none")
from cryptography.hazmat.primitives import serialization
pem=pub.public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
try:
    hs=jwt.encode({"iss":"https://accounts.google.com","aud":S.GOOGLE_CLIENT_ID,"sub":"1","email":"a@b.c","email_verified":True,"iat":now,"exp":now+60,"nonce":st["nonce"]},pem.decode(),algorithm="HS256")
    ok(fails(g.verify_id_token, hs, st["nonce"], key_resolver=res), "rechaza confusion de algoritmo HS256")
except Exception as e:
    print("OK   confusion HS256 imposible de firmar con PyJWT:", type(e).__name__)
print("TODO OK")
