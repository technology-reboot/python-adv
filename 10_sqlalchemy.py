"""Session 10 - SQLAlchemy ORM: models (see db.py), queries, relationships, N+1.

Run (from the codealong folder):  python day2/10_sqlalchemy.py
"""
from db import Customer, Order, OrderItem, Product, SessionLocal, engine, load_sample_data  # models + session factory from db.py
from sqlalchemy import event, func, select  # event hooks, SQL functions (sum), select statements
from sqlalchemy.orm import selectinload  # eager-loading strategy

if __name__ == "__main__":  # demo only when run directly
    load_sample_data()  # create tables and fill them (skipped if already loaded)

    # count SQL statements so we can SEE the N+1 problem
    queries = {"n": 0}  # mutable counter
    event.listen(engine, "before_cursor_execute", lambda *a: queries.update(n=queries["n"] + 1))  # +1 for every SQL statement sent

    with SessionLocal() as s:  # open a session, closed at the end of the block
        # 1. basic select
        gold = s.scalars(select(Customer).where(Customer.tier == "GOLD").limit(3)).all()  # first 3 GOLD customers as objects
        print("gold customers:", [c.name for c in gold])  # print their names

        # 2. aggregate: revenue per status
        rev = s.execute(  # execute returns rows (not single objects)
            select(Order.status, func.sum(OrderItem.quantity * OrderItem.unit_price))  # status + total revenue
            .join(OrderItem).group_by(Order.status)  # join items to orders, one row per status
        ).all()
        print("revenue by status:", [(st, float(v)) for st, v in rev])  # Decimal -> float for display

        # 3. N+1 problem: 1 query for orders + 1 lazy query per order's items
        queries["n"] = 0  # reset the counter
        orders = s.scalars(select(Order).limit(20)).all()  # 1 query: 20 orders
        _ = [o.total for o in orders]  # .total touches o.items -> lazy load, 1 query per order
        print("lazy loading ->", queries["n"], "queries (N+1!)")  # expect 21

        # 4. fix: eager load with selectinload -> 2 queries total
        s.expunge_all()  # forget loaded objects so they are fetched again
        queries["n"] = 0  # reset the counter
        orders = s.scalars(select(Order).options(selectinload(Order.items)).limit(20)).all()  # orders + all their items in one extra query
        _ = [o.total for o in orders]  # items already loaded -> no more queries
        print("selectinload ->", queries["n"], "queries")  # expect 2

    # 5. write: Session.begin() commits on success, rolls back on error
    with SessionLocal.begin() as s:  # transaction: commit at end, rollback on exception
        p = s.scalars(select(Product).limit(1)).one()  # fetch exactly one product
        p.stock += 10  # change tracked automatically by the ORM
        print("restocked", p.name, "->", p.stock)  # UPDATE is sent on commit
