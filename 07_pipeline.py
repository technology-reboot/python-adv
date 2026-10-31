import importlib
from pathlib import Path

import pandas as pd
from pydantic import ValidationError

DATA = Path("data")

clean_orders = importlib.import_module("05_pandas").clean_orders
OrderIn = importlib.import_module("06_pydantic").OrderIn

def build_orders(df: pd.DataFrame):  # turn cleaned rows into validated orders
    """Group rows by order_id -> validated OrderIn objects + a list of rejects."""
    valid, rejected = [], []  # successes and failures
    for order_id, grp in df.groupby("order_id"):  # one group of rows per order
        first = grp.iloc[0]  # header fields are the same on every row, so use the first
        payload = {  # build the dict that pydantic will validate
            "customer_id": int(first["customer_id"]),  # numpy int -> plain int
            "order_date": first["order_date"].date().isoformat(),  # Timestamp -> 'YYYY-MM-DD'
            "status": first["status"],  # already cleaned in session 5
            "items": [  # one item per row in the group
                {"product_id": int(r.product_id), "quantity": int(r.quantity), "unit_price": str(r.unit_price)}  # str keeps Decimal precision
                for r in grp.itertuples()  # fast row iteration
            ],
        }
        try:
            valid.append((int(order_id), OrderIn.model_validate(payload)))  # validated -> keep
        except ValidationError as exc:  # failed a rule
            rejected.append((int(order_id), exc.errors()[0]["msg"]))  # keep id + first error message
    return valid, rejected  # both lists for reporting


if __name__ == "__main__":  # demo only when run directly
    raw = pd.read_csv(DATA / "orders_dirty.csv")  # 1. load raw CSV
    clean = clean_orders(raw)  # 2. clean with pandas
    valid, rejected = build_orders(clean)  # 3. validate with pydantic
    print(f"raw rows={len(raw)}  clean rows={len(clean)}  orders valid={len(valid)}  rejected={len(rejected)}")  # funnel summary
    print("sample order:", valid[0][0], "total", valid[0][1].total)  # first valid order's id and total
    for oid, msg in rejected[:3]:  # show up to three rejects
        print("rejected", oid, msg)  # id and reason