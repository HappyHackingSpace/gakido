import click
from gakido import Client, Session


def show(label: str, resp, color: str) -> None:
    try:
        data = resp.json()
        summary = {
            "status": resp.status_code,
            "ja3": data.get("ja3_hash"),
            "ja4": data.get("ja4"),
            "ua": data.get("user_agent"),
        }
        click.secho(f"{label}: {summary}", fg=color)
    except Exception:
        click.secho(f"{label}: status={resp.status_code} body={resp.text[:120]}", fg=color)


def main() -> None:
    with Client() as c:
        r = c.get("https://tls.browserleaks.com/json")
        show("Default (chrome_120/h1)", r, "yellow")

    with Client(impersonate="chrome_120") as c:
        r = c.get("https://tls.browserleaks.com/json")
        show("Explicit chrome_120", r, "green")

    with Session(impersonate="chrome_120") as s:
        r = s.get("https://tls.browserleaks.com/json")
        show("Session chrome_120", r, "blue")

    q = Client(impersonate="safari_170_ios", force_http1=True)
    r = q.get("https://tls.browserleaks.com/json")
    show("Safari iOS (h1)", r, "magenta")


if __name__ == "__main__":
    main()
