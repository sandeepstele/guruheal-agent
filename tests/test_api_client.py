import json
import logging

import requests

BASE_URL = "http://localhost:8000"

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def load_test_data(filename):
    with open(filename, 'r') as f:
        return json.load(f)


## API

def get_ping(**kwargs):
    response = requests.get(f"{BASE_URL}/api/v1/ping", headers={"accept": "application/json"})
    return response


def get_asycapi(**kwargs):
    response = requests.get(f"{BASE_URL}/asyncapi")
    return response


def get_sse(**kwargs):
    params = {}
    params.update(kwargs)
    response = requests.get(f"{BASE_URL}/api/v1/sse", params=params)
    return response


def get_error(**kwargs):
    logger.info(f"{BASE_URL}/api/v1/error")
    response = requests.get(f"{BASE_URL}/api/v1/error")
    return response

def get_metrics(**kwargs):
    response = requests.get(f"{BASE_URL}/metrics")
    return response

## Test case
def test_ping():
    response = get_ping()
    logger.info(response.headers)
    assert response.status_code == 200, "Status code is not 200"
    assert "x-correlation-id" in response.headers, "x-correlation-id header is missing"
    data = response.json()
    assert data["message"] == "pong", "Message is not 'pong'"
    assert "version" in data, "Version key is missing"
    # Optionally, you can add a regex check for the version to match semver
    # import re
    # assert re.match(r'^\d+\.\d+\.\d+$', data["version"]), "Version is not in semver format"


def test_asyncapi():
    response = get_asycapi()
    assert response.status_code == 200, "Status code is not 200"
    assert "AsyncAPI" in response.text, "Title does not contain 'AsyncAPI'"


def test_sse():
    response = get_sse(max_second=5, period=1)
    assert response.status_code == 200

    events = response.text.split("\r\n")

    for event in events:
        if event.startswith("data: "):
            logger.info(event)


def test_error():
    response = get_error()
    assert response.status_code == 500, "Status code is not 500"
    assert "x-correlation-id" in response.headers, "x-correlation-id header is missing"

    content_type = response.headers["Content-Type"]
    assert content_type == "application/json", "Content type is not application/json"

    data = response.json()
    assert "correlation_id" in data, "'correlation_id' is not in response body"
    assert response.headers["x-correlation-id"] == data["correlation_id"], "x-correlation-id is not match with body.correlation_id"


def test_prometheus():
    response = get_metrics()
    assert response.status_code == 200

    isPrometheus = False
    metrics = response.text.split("\n")
    for metric in metrics:
        if metric.startswith('# HELP python_gc'):
            isPrometheus=True

    assert isPrometheus , "Prometheus signature is missing"
 