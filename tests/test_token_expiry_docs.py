from app.config import ACCESS_TOKEN_EXPIRE_MINUTES


def test_token_lifetime_exposed_in_openapi(openapi_schema):
    oauth2 = openapi_schema["components"]["securitySchemes"]["OAuth2PasswordBearer"]
    assert oauth2["flows"]["password"]["tokenUrl"] == "token"
    assert str(ACCESS_TOKEN_EXPIRE_MINUTES) in oauth2.get("description", "")
