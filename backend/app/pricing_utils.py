import os
import requests
from flask import request

GEOIP_API_URL = os.getenv("GEOIP_API_URL", "https://ipapi.co/{ip}/json/")
GEOIP_API_TOKEN = os.getenv("GEOIP_API_TOKEN")
DEFAULT_REGION_KEY = os.getenv("DEFAULT_REGION_KEY", "INTL")


def get_client_ip():
    fly_ip = request.headers.get("Fly-Client-IP")
    if fly_ip:
        return fly_ip.split(",")[0].strip()

    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        parts = [part.strip() for part in forwarded_for.split(",") if part.strip()]
        if parts:
            return parts[0]

    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip.strip()

    return request.remote_addr


def _geoip_url_for(ip):
    url = GEOIP_API_URL.format(ip=ip, token=GEOIP_API_TOKEN or "")
    if GEOIP_API_TOKEN and "{token}" not in GEOIP_API_URL:
        separator = "&" if "?" in url else "?"
        url = f"{url}{separator}token={GEOIP_API_TOKEN}"
    return url


def _extract_country_code(payload):
    if not isinstance(payload, dict):
        return None
    return payload.get("country") or payload.get("country_code")


def resolve_region_key():
    ip = get_client_ip()
    if not ip:
        return DEFAULT_REGION_KEY

    try:
        url = _geoip_url_for(ip)
        response = requests.get(url, timeout=2)
        if response.status_code != 200:
            return DEFAULT_REGION_KEY
        country_code = _extract_country_code(response.json())
    except Exception as e:
        print(f"Warning: geo lookup failed for ip {ip}: {e}")
        return DEFAULT_REGION_KEY

    if country_code == "US":
        return "US"
    return "INTL"
