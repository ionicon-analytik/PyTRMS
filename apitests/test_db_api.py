"""
Test of module pytrms.clients.db_api

"""
import pytest


def test_status(API):
    j = API.get("/api/status")

    assert j["_links"]["self"]["href"] == "/api/status"


