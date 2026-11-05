from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from urllib.parse import urljoin
import os
import unittest

from xingyuan_sis.web import create_app


class SubpathDeploymentTests(unittest.TestCase):
    def test_proxy_prefix_assets_redirect_and_cookie_are_consistent(self):
        with TemporaryDirectory() as tmp, patch.dict(os.environ, {
            "XINGYUAN_HOME": str(Path(tmp) / "auth"),
            "XINGYUAN_DB_PATH": str(Path(tmp) / "campus.db"),
            "XINGYUAN_URL_PREFIX": "/xingyuan",
            "XINGYUAN_TRUST_PROXY": "1",
            "XINGYUAN_HTTPS": "1",
        }):
            app = create_app(demo=False)
            client = app.test_client()
            headers = {"X-Forwarded-Prefix": "/xingyuan", "X-Forwarded-Proto": "https"}
            response = client.get("/login", headers=headers)
            self.assertEqual(response.status_code, 200)
            self.assertIn(b'/xingyuan/static/app.css', response.data)
            cookie = response.headers["Set-Cookie"]
            self.assertIn("Path=/xingyuan", cookie)
            self.assertIn("Secure", cookie)
            with client.session_transaction() as session:
                token = session["_csrf_token"]
            response = client.post("/login", headers=headers, data={
                "_csrf_token": token, "username": "Administrator", "password": "12345678",
            })
            self.assertEqual(response.headers["Location"], "/xingyuan/")
            self.assertTrue((Path(tmp) / "campus.db").is_file())
            with client.get("/static/app.css", headers=headers) as stylesheet:
                css = stylesheet.get_data(as_text=True)
            self.assertIn('../assets/fonts/', css)
            self.assertEqual(urljoin('https://example.test/xingyuan/static/app.css', '../assets/fonts/test.ttf'),
                             'https://example.test/xingyuan/assets/fonts/test.ttf')

    def test_default_does_not_trust_forwarded_prefix(self):
        with TemporaryDirectory() as tmp, patch.dict(os.environ, {
            "XINGYUAN_HOME": str(Path(tmp) / "auth"), "XINGYUAN_TRUST_PROXY": "0",
            "XINGYUAN_URL_PREFIX": "",
        }):
            app = create_app(Path(tmp) / "campus.db", demo=False)
            response = app.test_client().get("/students", headers={"X-Forwarded-Prefix": "/fake"})
            self.assertTrue(response.headers["Location"].startswith('/login'))
