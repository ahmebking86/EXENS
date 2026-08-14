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


def health():
    r = requests.get(f"{base_url()}/health", timeout=5)
    r.raise_for_status()
    return r.json()


def connect():
    payload = {
        "login": int(db.get("mt5_login")),
        "password": db.get("mt5_password"),
        "server": db.get("mt5_server"),
    }
    r = requests.post(f"{base_url()}/connect", json=payload, headers=headers(), timeout=15)
    return r.json()


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
    return r.json()


def start():
    r = requests.post(f"{base_url()}/start", headers=headers(), timeout=10)
    return r.json()


def stop(close_position=False):
    r = requests.post(f"{base_url()}/stop", json={"close_position": close_position}, headers=headers(), timeout=15)
    return r.json()


def status():
    r = requests.get(f"{base_url()}/status", headers=headers(), timeout=10)
    return r.json()
