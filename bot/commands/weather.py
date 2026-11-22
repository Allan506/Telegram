"""Comando /clima usando Open-Meteo (gratis y sin clave de API)."""

from __future__ import annotations

from html import escape

import requests

from .registry import command

WMO_CODES = {
    0: "despejado ☀️",
    1: "mayormente despejado 🌤️",
    2: "parcialmente nublado ⛅",
    3: "nublado ☁️",
    45: "niebla 🌫️",
    48: "niebla con escarcha 🌫️",
    51: "llovizna ligera 🌦️",
    53: "llovizna moderada 🌦️",
    55: "llovizna intensa 🌧️",
    56: "llovizna helada 🌧️",
    57: "llovizna helada intensa 🌧️",
    61: "lluvia ligera 🌦️",
    63: "lluvia moderada 🌧️",
    65: "lluvia intensa 🌧️",
    66: "lluvia helada 🌧️",
    67: "lluvia helada intensa 🌧️",
    71: "nieve ligera 🌨️",
    73: "nieve moderada 🌨️",
    75: "nieve intensa ❄️",
    77: "granos de nieve ❄️",
    80: "chubascos ligeros 🌦️",
    81: "chubascos moderados 🌧️",
    82: "chubascos violentos ⛈️",
    85: "chubascos de nieve 🌨️",
    86: "chubascos de nieve intensos ❄️",
    95: "tormenta ⛈️",
    96: "tormenta con granizo ⛈️",
    99: "tormenta fuerte con granizo ⛈️",
}


class WeatherError(Exception):
    """No se pudo obtener el clima."""


def _get_json(url: str, params: dict) -> dict:
    try:
        response = requests.get(url, params=params, timeout=15)
        response.raise_for_status()
        return response.json()
    except (requests.RequestException, ValueError) as exc:
        raise WeatherError(str(exc)) from exc


def find_city(name: str, geocode_url: str) -> dict:
    data = _get_json(
        geocode_url,
        {"name": name, "count": 1, "language": "es", "format": "json"},
    )
    results = data.get("results") or []
    if not results:
        raise WeatherError(f"No encontré la ciudad «{name}».")
    return results[0]


def current_weather(latitude: float, longitude: float, forecast_url: str) -> dict:
    data = _get_json(
        forecast_url,
        {
            "latitude": latitude,
            "longitude": longitude,
            "current": "temperature_2m,relative_humidity_2m,apparent_temperature,wind_speed_10m,weather_code",
            "timezone": "auto",
        },
    )
    current = data.get("current") or {}
    if not current:
        raise WeatherError("La API del clima no devolvió datos actuales.")
    return current


@command("clima", "Muestra el clima actual de una ciudad", "/clima <ciudad>")
def clima(ctx):
    city = ctx.raw_args.strip()
    if not city:
        return "Uso: <code>/clima &lt;ciudad&gt;</code>\nEjemplo: <code>/clima Madrid</code>"

    try:
        place = find_city(city, ctx.config.weather_geocode_url)
        current = current_weather(place["latitude"], place["longitude"], ctx.config.weather_forecast_url)
    except WeatherError as exc:
        return f"🌦️ No pude obtener el clima: {escape(str(exc))}"

    description = WMO_CODES.get(current.get("weather_code"), "sin datos")
    location = escape(place.get("name", city))
    if place.get("country"):
        location += f", {escape(place['country'])}"

    return (
        f"<b>Clima en {location}</b>\n"
        f"🌡️ Temperatura: <b>{current.get('temperature_2m')} °C</b>\n"
        f"🤔 Sensación: {current.get('apparent_temperature')} °C\n"
        f"💧 Humedad: {current.get('relative_humidity_2m')} %\n"
        f"💨 Viento: {current.get('wind_speed_10m')} km/h\n"
        f"☁️ Estado: {description}"
    )
