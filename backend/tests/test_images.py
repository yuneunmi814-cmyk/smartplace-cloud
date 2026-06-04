def test_upload_image(client, user_token, auth, fakes):
    r = client.post(
        "/api/v1/images/upload",
        headers=auth(user_token),
        files={"file": ("photo.png", b"\x89PNG fake bytes", "image/png")},
    )
    assert r.status_code == 201
    body = r.json()
    assert body["originalFilename"] == "photo.png"
    assert body["sizeBytes"] > 0
    assert body["url"].startswith("memory://")
    # Object actually landed in (fake) storage.
    assert len(fakes.storage._objects) == 1


def test_upload_multiple_images(client, user_token, auth, fakes):
    r = client.post(
        "/api/v1/images/upload-batch",
        headers=auth(user_token),
        files=[
            ("files", ("a.png", b"aaa", "image/png")),
            ("files", ("b.jpg", b"bbbb", "image/jpeg")),
            ("files", ("c.webp", b"ccccc", "image/webp")),
        ],
    )
    assert r.status_code == 201
    body = r.json()
    assert len(body) == 3
    assert {i["originalFilename"] for i in body} == {"a.png", "b.jpg", "c.webp"}
    assert len(fakes.storage._objects) == 3


def test_list_images(client, user_token, auth):
    client.post(
        "/api/v1/images/upload",
        headers=auth(user_token),
        files={"file": ("a.png", b"abc", "image/png")},
    )
    images = client.get("/api/v1/images", headers=auth(user_token)).json()
    assert len(images) == 1
