"""Shared database setup (SQLAlchemy 2.0 models) used by sessions 10, 11 and 14.

Default is a local SQLite file (zero setup). To use Postgres instead:
    set APP_DATABASE_URL=postgresql+psycopg://orders:orders@localhost:5432/orders
"""
import csv  # read the sample CSV files
import os  # read environment variables
from datetime import date  # date type
from decimal import Decimal  # exact money type
from pathlib import Path  # file paths

from sqlalchemy import ForeignKey, Numeric, String, create_engine, select  # column types, engine factory, select
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, sessionmaker  # ORM building blocks

DATA = Path("data")  # run from the project root
DATABASE_URL = os.getenv("APP_DATABASE_URL", "sqlite:///codealong.db")  # env var or local SQLite file

engine = create_engine(DATABASE_URL)  # the connection source for the whole app
SessionLocal = sessionmaker(engine, expire_on_commit=False)  # session factory; objects stay usable after commit


class Base(DeclarativeBase):  # parent of all models; collects table metadata
    pass


class Customer(Base):  # maps to table "customers"
    __tablename__ = "customers"  # table name
    id: Mapped[int] = mapped_column(primary_key=True)  # primary key
    name: Mapped[str] = mapped_column(String(100))  # up to 100 chars
    email: Mapped[str] = mapped_column(String(200), unique=True)  # must be unique
    tier: Mapped[str] = mapped_column(String(20), default="STANDARD")  # default applied on insert
    orders: Mapped[list["Order"]] = relationship(back_populates="customer")  # one customer -> many orders


class Product(Base):  # maps to table "products"
    __tablename__ = "products"
    id: Mapped[int] = mapped_column(primary_key=True)  # primary key
    sku: Mapped[str] = mapped_column(String(20), unique=True)  # unique stock code
    name: Mapped[str] = mapped_column(String(100))  # product name
    price: Mapped[Decimal] = mapped_column(Numeric(10, 2))  # up to 10 digits, 2 decimals
    stock: Mapped[int]  # plain int column (type inferred from annotation)


class Order(Base):  # maps to table "orders"
    __tablename__ = "orders"
    id: Mapped[int] = mapped_column(primary_key=True)  # primary key
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"))  # link to customers table
    order_date: Mapped[date]  # date column
    status: Mapped[str] = mapped_column(String(20), default="pending")  # defaults to pending
    customer: Mapped[Customer] = relationship(back_populates="orders")  # many orders -> one customer
    items: Mapped[list["OrderItem"]] = relationship(back_populates="order", cascade="all, delete-orphan")  # deleting an order deletes its items

    @property
    def total(self) -> Decimal:  # computed, not stored
        return sum((i.quantity * i.unit_price for i in self.items), Decimal("0"))  # sum of line totals


class OrderItem(Base):  # maps to table "order_items"
    __tablename__ = "order_items"
    id: Mapped[int] = mapped_column(primary_key=True)  # primary key
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"))  # parent order
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"))  # which product
    quantity: Mapped[int]  # how many
    unit_price: Mapped[Decimal] = mapped_column(Numeric(10, 2))  # price at time of purchase
    order: Mapped[Order] = relationship(back_populates="items")  # back to the parent order
    product: Mapped[Product] = relationship()  # navigate to the product


def load_sample_data(limit_orders: int = 300) -> None:  # seed the database
    """Create tables and load customers, products and a few clean orders (idempotent)."""
    import random  # local import: only needed here

    Base.metadata.create_all(engine)  # CREATE TABLE for any missing tables
    with SessionLocal.begin() as s:  # one transaction, commit at the end
        if s.scalar(select(Customer.id).limit(1)):  # any customer exists?
            return  # already loaded
        with open(DATA / "customers.csv", newline="", encoding="utf-8") as f:
            s.add_all(Customer(**r) for r in csv.DictReader(f))  # each CSV row -> Customer(column=value, ...)
        with open(DATA / "products.csv", newline="", encoding="utf-8") as f:
            s.add_all(Product(**r) for r in csv.DictReader(f))  # each CSV row -> Product
        s.flush()  # send INSERTs now so ids exist for the queries below
        rng = random.Random(1)  # seeded -> same random data every run
        cust_ids = list(s.scalars(select(Customer.id)))  # all customer ids
        prods = list(s.scalars(select(Product)))  # all products
        for i in range(limit_orders):  # create N orders
            order = Order(
                customer_id=rng.choice(cust_ids),  # random customer
                order_date=date(2025, rng.randint(1, 12), rng.randint(1, 28)),  # random day in 2025 (28 avoids invalid dates)
                status=rng.choice(["pending", "paid", "shipped", "cancelled"]),  # random status
            )
            for p in rng.sample(prods, rng.randint(1, 4)):  # 1-4 distinct products
                order.items.append(OrderItem(product_id=p.id, quantity=rng.randint(1, 5), unit_price=p.price))  # add a line with current price
            s.add(order)  # stage order (items saved via cascade)
