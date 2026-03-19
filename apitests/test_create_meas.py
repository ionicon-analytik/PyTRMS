"""
Test of module pytrms.clients.db_api

"""
import json

import pytest


@pytest.mark.dependency()
def test_db_empty(API):
    assert API.get("/api/recipes/1") is None, "database not empty"


@pytest.mark.dependency(depends=["test_db_empty"])
def test_create_recipe(API):

    API.post("/api/recipes", {"name": "uno"})

    j = API.get("/api/recipes")
    assert j["count"] == 1

    j = API.get("/api/recipes/1")
    assert j["path"] == "/ame/AME/Recipes/uno"

    ## per default, there *must* be a Composition for this to be a "recipe":
    assert API.get("/api/recipes/1/files/meta?name=Composition") is not None


@pytest.mark.dependency(depends=["test_create_recipe"])
def test_recipe_file_api(API):

    j = API.get("/api/recipes/1/files/meta?name=Composition")
    assert "entry" in j
    assert j["entry"]["name"] == "Composition"
    assert j["entry"]["path"] == "/Composition"
    assert j["entry"]["type"] == "file"
    assert j["entry"]["size"] > 0
    assert j["entry"]["etag"].startswith("W/\"")

    body = API.get("/api/recipes/1/files/content?name=Composition")
    assert len(body) == j["entry"]["size"]

    content = body.decode()
    assert len(content) > 0


@pytest.mark.dependency(depends=["test_create_recipe"])
def test_create_measurement(API):

    assert API.get("/api/measurements/last") is None

    r = API.post("/api/measurements", { "recipeDirectory": "/ame/AME/Recipes/uno" })
    j = API.get(r.href)

    assert j["recipeDirectory"] == "/ame/AME/Recipes/uno"

    j = API.get("/api/measurements/last")
    assert j["_links"]["self"]["href"] == "/api/measurements/1"

    ## not yet started
    assert API.get("/api/measurements/current") is None

