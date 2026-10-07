"""
Offline tests for load_lesson_file. The HTTP session is replaced by a fake, so
no login or network is needed.
"""
import base64

import pytest

from studieplus_api import requests_scraper
from studieplus_api.requests_scraper import StudiePlusRequestsScraper


class FakeResponse:
    def __init__(self, body, content_type, declared_size=True, encoding=None):
        self.status_code = 200
        self.body = body
        self.encoding = encoding
        self.headers = {"content-type": content_type}
        if declared_size:
            self.headers["content-length"] = str(len(body))
        self.bytes_read = 0
        self.closed = False

    def iter_content(self, chunk_size):
        for start in range(0, len(self.body), chunk_size):
            chunk = self.body[start:start + chunk_size]
            self.bytes_read += len(chunk)
            yield chunk

    def close(self):
        self.closed = True


class FakeSession:
    def __init__(self, response):
        self.response = response

    def get(self, url, **kwargs):
        return self.response


def scraper_with(response):
    s = StudiePlusRequestsScraper(username="u", password="p", school="s")
    s.login = lambda: True
    s.session = FakeSession(response)
    return s


@pytest.fixture
def small_limit(monkeypatch):
    monkeypatch.setattr(requests_scraper, "MAX_LOAD_BYTES", 1000)


async def test_text_file_is_returned_as_text():
    s = scraper_with(FakeResponse("Opgave: læs side 3".encode("utf-8"), "text/plain", encoding="utf-8"))
    result = await s.load_lesson_file("https://x", "noter.txt")
    assert result["success"]
    assert result["is_text"]
    assert result["content"] == "Opgave: læs side 3"


async def test_binary_file_is_returned_as_base64():
    body = b"%PDF-1.4 binary \x00\xff"
    s = scraper_with(FakeResponse(body, "application/pdf"))
    result = await s.load_lesson_file("https://x", "opgave.pdf")
    assert result["success"]
    assert not result["is_text"]
    assert base64.b64decode(result["content"]) == body
    assert result["size"] == len(body)


async def test_file_over_declared_limit_is_refused_without_reading_it(small_limit):
    # The 291 MB assignment zip was read fully into memory before the limit existed.
    response = FakeResponse(b"x" * 5000, "application/zip")
    result = await scraper_with(response).load_lesson_file("https://x", "stor.zip")
    assert not result["success"]
    assert result["too_large"]
    assert result["size"] == 5000
    assert response.bytes_read == 0
    assert response.closed


async def test_file_over_limit_without_content_length_stops_reading(small_limit):
    # Without Content-Length the limit must still stop the download partway.
    response = FakeResponse(b"x" * 500_000, "application/zip", declared_size=False)
    result = await scraper_with(response).load_lesson_file("https://x", "stor.zip")
    assert not result["success"]
    assert result["too_large"]
    assert response.bytes_read < 500_000
    assert response.closed


async def test_file_exactly_at_limit_is_loaded(small_limit):
    s = scraper_with(FakeResponse(b"x" * 1000, "application/octet-stream"))
    result = await s.load_lesson_file("https://x", "grænse.bin")
    assert result["success"]
    assert result["size"] == 1000
