import requests
import db


def base_url():
    host = db.get("ec2_host")
    port = db.get("ec2_port")
    return f"http://{host}:{port}"


def headers():
    return {"X-API-Key": db.get("ec2_api_key")}


def is_configured():
    return bool(db.get("ec2_host")) and bool(db.get("ec2_api_key"))




def _json_response(response, endpoint):
    try:
        response.raise_for_status()
    except Exception as exc:
        body = response.text[:500] if response.text else "<empty response>"
        raise RuntimeError(f"EC2 {endpoint} HTTP {response.status_code}: {body}") from exc
    if not response.text.strip():
        raise RuntimeError(f"EC2 {endpoint} returned an empty response (HTTP {response.status_code})")
    try:
        return response.json()
    except ValueError as exc:
        body = response.text[:500]
        raise RuntimeError(f"EC2 {endpoint} returned non-JSON (HTTP {response.status_code}): {body}") from exc

def health():
    r = requests.get(f"{base_url()}/health", timeout=5)
    r.raise_for_status()
    return _json_response(r, "health")


def connect():
    payload = {
        "login": int(db.get("mt5_login")),
        "password": db.get("mt5_password"),
        "server": db.get("mt5_server"),
    }
    r = requests.post(f"{base_url()}/connect", json=payload, headers=headers(), timeout=15)
    return _json_response(r, "connect")


def push_config():
    payload = {
        "symbol": db.get("symbol"),
        "direction": db.get("direction"),
        "lot": float(db.get("lot")),
        "target_type": db.get("target_type"),
        "target_value": float(db.get("target_value")),
        "sl_type": db.get("sl_type"),
        "sl_value": float(db.get("sl_value")),
    }
    r = requests.post(f"{base_url()}/config", json=payload, headers=headers(), timeout=10)
    return _json_response(r, "config")


def start():
    r = requests.post(f"{base_url()}/start", headers=headers(), timeout=10)
    return _json_response(r, "start")


def stop(close_position=False):
    r = requests.post(f"{base_url()}/stop", json={"close_position": close_position}, headers=headers(), timeout=15)
    return _json_response(r, "stop")


def status():
    r = requests.get(f"{base_url()}/status", headers=headers(), timeout=10)
    return _json_response(r, "status")
