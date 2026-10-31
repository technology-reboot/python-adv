from pathlib import Path
import pandas as pd

DATA = Path("data")

def clean_orders(df: pd.DataFrame) -> pd.DataFrame:  # takes raw orders, returns clean orders
    df = df.copy()  # work on a copy so the caller's data is untouched
    df["status"] = df["status"].str.strip().str.lower()  # ' PAID ' -> 'paid'
    df["quantity"] = df["quantity"].replace({"two": 2})  # known typo in the data
    df["quantity"] = pd.to_numeric(df["quantity"], errors="coerce")  # bad -> NaN
    # '$2,242.99' or a rupee-prefixed price -> plain number: keep only digits and '.'
    df["unit_price"] = pd.to_numeric(  # convert the cleaned text to numbers
        df["unit_price"].astype(str).str.replace(r"[^\d.]", "", regex=True), errors="coerce"  # strip symbols; bad -> NaN
    )
    df["order_date"] = pd.to_datetime(df["order_date"], format="mixed")  # 3 date formats
    df = df.drop_duplicates()  # remove exact duplicate rows
    df = df.dropna(subset=["customer_id", "quantity", "unit_price"])  # unusable rows
    df = df.astype({"customer_id": int, "quantity": int})  # NaN gone, so safe to use whole numbers
    df["revenue"] = df["quantity"] * df["unit_price"]  # new column: revenue per row
    return df  # cleaned DataFrame


if __name__ == "__main__":  # demo only when run directly
    raw = pd.read_csv(DATA / "orders_dirty.csv")  # load the messy orders
    customers = pd.read_csv(DATA / "customers.csv")  # load customers
    products = pd.read_csv(DATA / "products.csv")  # load products
    
    orders = clean_orders(raw)

    print(f"raw rows={len(raw)}  clean rows={len(orders)}")  # how many rows survived

    # join: orders + customers + products
    full = orders.merge(customers, left_on="customer_id", right_on="id", suffixes=("", "_c")).merge(  # add customer columns
        products[["id", "name"]], left_on="product_id", right_on="id", suffixes=("", "_p")  # add product name
    )

    print("\nRevenue by status:\n", full.groupby("status")["revenue"].sum().round(2))  # total revenue per status
    print("\nTop 5 customers:\n", full.groupby("name")["revenue"].sum().nlargest(5).round(2))  # 5 biggest spenders
    monthly = full.set_index("order_date").resample("MS")["revenue"].sum().round(2)  # bucket by month start, sum revenue
    print("\nMonthly revenue:\n", monthly.head(6))  # first six months
