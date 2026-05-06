import sys
import requests
from datetime import datetime

try:
    import RPi.GPIO as GPIO
    ON_PI = True
except (ImportError, RuntimeError):
    ON_PI = False
    print("[WARNING] RPi.GPIO not found - running in simulation mode\n")

LED_PIN       = 25
POP_THRESHOLD = 30
NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
FORECAST_URL  = "https://api.open-meteo.com/v1/forecast"
TIMEOUT_SEC   = 10
HEADERS       = {"User-Agent": "umbrella-indicator/1.0"}


def geocode(city: str) -> tuple[float, float, str]:
    resp = requests.get(
        NOMINATIM_URL,
        params={"q": city, "format": "json", "limit": 5},
        headers=HEADERS,
        timeout=TIMEOUT_SEC,
    )
    resp.raise_for_status()
    results = resp.json()

    if not results:
        raise ValueError(f"Location '{city}' not found.")

    if len(results) > 1:
        print("\nMultiple results found:")
        for i, r in enumerate(results):
            print(f"  [{i+1}] {r['display_name']} (lat={r['lat']}, lon={r['lon']})")
        while True:
            choice = input(f"\nSelect [1-{len(results)}]: ").strip()
            if choice.isdigit() and 1 <= int(choice) <= len(results):
                selected = results[int(choice) - 1]
                break
            print("Invalid choice, try again.")
    else:
        selected = results[0]

    return float(selected["lat"]), float(selected["lon"]), selected["display_name"]


def get_max_pop(lat: float, lon: float) -> tuple[int, str]:
    resp = requests.get(
        FORECAST_URL,
        params={
            "latitude":      lat,
            "longitude":     lon,
            "hourly":        "precipitation_probability",
            "timezone":      "Asia/Ho_Chi_Minh",
            "forecast_days": 1,
        },
        timeout=TIMEOUT_SEC,
    )
    resp.raise_for_status()
    data = resp.json()

    times = data["hourly"]["time"]
    pops  = data["hourly"]["precipitation_probability"]
    now   = datetime.now().strftime("%Y-%m-%dT%H:00")

    future = [(t, p) for t, p in zip(times, pops) if t >= now]
    max_pop  = max(p for _, p in future)
    max_hour = next(t for t, p in future if p == max_pop)
    return max_pop, max_hour


def setup_gpio():
    GPIO.setmode(GPIO.BCM)
    GPIO.setwarnings(False)
    GPIO.setup(LED_PIN, GPIO.OUT)
    GPIO.output(LED_PIN, GPIO.LOW)


def set_led(state: bool):
    if ON_PI:
        GPIO.output(LED_PIN, GPIO.HIGH if state else GPIO.LOW)
    else:
        print(f"  [SIM] LED GPIO {LED_PIN} ? {'ON' if state else 'OFF'}")


def main():
    print("=" * 50)
    print("   UMBRELLA INDICATOR - Open-Meteo + Nominatim")
    print("=" * 50 + "\n")

    while True:
        city = input("Enter city name (or 'q' to quit): ").strip()
        if city.lower() in ("q", "quit", "exit"):
            print("Goodbye!")
            break
        if not city:
            print("City name cannot be empty.\n")
            continue

        try:
            print(f"\n[1/3] Geocoding '{city}' ...")
            lat, lon, display_name = geocode(city)
            print(f"      ? {display_name}")

            print("[2/3] Fetching weather data ...")
            max_pop, max_hour = get_max_pop(lat, lon)

            print("[3/3] Results:\n")
            print(f"  Location    : {display_name}")
            print(f"  Checked at  : {datetime.now().strftime('%d/%m/%Y %H:%M')}")
            print(f"  Max POP     : {max_pop}% at {max_hour[11:16]}")
            print(f"  Threshold   : {POP_THRESHOLD}%\n")

            if ON_PI:
                setup_gpio()

            if max_pop >= POP_THRESHOLD:
                print(f"  POP {max_pop}% >= {POP_THRESHOLD}% ? Bring an umbrella!")
                set_led(True)
            else:
                print(f"  POP {max_pop}% < {POP_THRESHOLD}% ? No rain expected.")
                set_led(False)

            if ON_PI:
                input("\n  [Press Enter to continue...] ")
                set_led(False)

        except requests.exceptions.ConnectionError:
            print("\nNetwork error. Check your connection.")
        except requests.exceptions.Timeout:
            print("\nAPI timeout. Try again later.")
        except requests.exceptions.HTTPError as e:
            print(f"\nHTTP error: {e}")
        except ValueError as e:
            print(f"\n{e}")
        except KeyboardInterrupt:
            print("\n\n[Ctrl+C] Exiting.")
            break
        finally:
            if ON_PI:
                GPIO.cleanup()

        print()


if __name__ == "__main__":
    main()
