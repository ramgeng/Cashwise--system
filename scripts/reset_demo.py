"""Reload the demo business's records from the CSV files in data/ (e.g. after trying uploads).

    python -m scripts.reset_demo
"""
from app.db import tenant
from app.services import demo
from scripts._pick import parser, pick


def main():
    b = pick(parser(__doc__).parse_args().business)
    counts = demo.load(tenant.engine_for(b["id"]))
    print(f"{b['name']}: demo data reloaded. Cash today Rs {counts['books']['cash_today']:,}")


if __name__ == "__main__":
    main()
