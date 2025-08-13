import pytest


def pytest_addoption(parser):
    parser.addoption(
        "--real-request", action="store_true", help="perform real HTTP requests"
    )


@pytest.fixture
def real_request(request):
    return request.config.getoption("--real-request")
