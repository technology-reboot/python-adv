import csv
from pathlib import Path

DATA = Path("data")

class AppError(Exception):
    pass

class RowError(AppError):
    def __init__(self, line_no, message):
        super().__init__(f"line {line_no}: {message}")
        self.line_no = line_no

class ImportFailed(AppError):
    pass

def parse_row(line_no, row):  # validate and convert one CSV row
    try:
        qty = int(row["quantity"])  # text -> int (may raise ValueError)
        price = float(row["unit_price"])  # text -> float (may raise ValueError)
    except (ValueError, TypeError) as exc:  # bad text, or None for a missing value
        raise RowError(line_no, f"bad number ({exc})") from exc  # 'from' keeps the cause
    if qty <= 0:  # business rule check
        raise RowError(line_no, "quantity must be positive")  # reject the row
    return {"order_id": int(row["order_id"]), "quantity": qty, "unit_price": price}  # clean typed dict



def import_orders(path):  # import a whole file, tolerating bad rows
    good, errors = [], []  # valid rows and collected errors
    try:
        f = open(path, newline="", encoding="utf-8")  # open the file manually
    except FileNotFoundError as exc:  # file missing
        raise ImportFailed(f"cannot open {path}") from exc  # translate to our own error, keep cause
    with f:  # file is closed even if something below raises
        for line_no, row in enumerate(csv.DictReader(f), start=2):  # line 1 is the header, data starts at 2
            try:
                good.append(parse_row(line_no, row))  # keep valid rows
            except RowError as exc:  # invalid row
                errors.append(exc)  # collect, don't stop the whole import
    return good, errors  # caller decides what to do with both lists

if __name__ == "__main__":  # demo only when run directly
    good, errors = import_orders(DATA / "orders_dirty.csv")  # run the import
    print(f"good={len(good)} bad={len(errors)}")  # summary counts
    for e in errors[:3]:  # show the first three errors
        print(" ", e, "| cause:", repr(e.__cause__))  # __cause__ = the original exception
    try:
        import_orders(DATA / "missing.csv")  # file does not exist
    except AppError as e:  # one except catches any of our errors
        print("caught:", e, "| cause:", type(e.__cause__).__name__)  # FileNotFoundError

    # try / except / else / finally in one picture
    try:
        value = int("42")  # code that might fail
    except ValueError:  # runs only if it failed
        print("not a number")
    else:  # runs only if no exception
        print("parsed", value)
    finally:  # always runs
        print("cleanup done")