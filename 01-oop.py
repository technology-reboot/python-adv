"""Session 1 - OOP: the domain model.

Run (from the codealong folder):  python day1/01_oop.py
"""
from abc import ABC, abstractmethod  # ABC/abstractmethod let us define an interface that subclasses must implement
from dataclasses import dataclass, field  # dataclass auto-generates __init__/__repr__; field customises defaults
from datetime import datetime  # used for the order's creation timestamp
from decimal import ROUND_HALF_UP, Decimal  # Decimal = exact money arithmetic (no float errors)
from enum import Enum  # Enum = a fixed set of named constants


def money(value: Decimal) -> Decimal:  # helper so every amount is rounded the same way
    """Always round money half-up to 2 places (round() uses banker's rounding)."""
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)  # force 2 decimals, 0.005 -> 0.01


# --- Step 1: enum + frozen dataclasses (immutable value objects) -------------
class Tier(str, Enum):  # inherits str so members compare/serialise as plain strings
    STANDARD = "STANDARD"  # default customer level
    GOLD = "GOLD"  # premium customer level


@dataclass(frozen=True)  # frozen = fields cannot be changed after creation (immutable, hashable)
class Customer:
    id: int  # unique customer number
    name: str  # customer's display name
    tier: Tier = Tier.STANDARD  # field with a default value


@dataclass(frozen=True)  # immutable product
class Product:
    id: int  # unique product number
    name: str  # product name
    price: Decimal  # unit price, Decimal for exact money


@dataclass(frozen=True)  # immutable order line (one product + how many)
class OrderLine:
    product: Product  # which product was bought
    quantity: int  # how many units

    def __post_init__(self):  # frozen: we can validate, not assign
        if self.quantity <= 0:  # business rule: must buy at least one
            raise ValueError("quantity must be positive")  # reject invalid object at creation time

    @property  # accessed like an attribute: line.subtotal
    def subtotal(self) -> Decimal:
        return money(self.product.price * self.quantity)  # price x quantity, rounded to 2 places


# --- Step 2: discounts = Strategy pattern behind an abstract base class ------
class DiscountPolicy(ABC):  # abstract base: cannot be instantiated directly
    @abstractmethod  # every subclass MUST override this method
    def apply(self, subtotal: Decimal, lines: list[OrderLine]) -> Decimal: ...  # contract only, no body


class NoDiscount(DiscountPolicy):  # simplest strategy: charge full price
    def apply(self, subtotal, lines):
        return money(subtotal)  # return the subtotal unchanged (just rounded)


class PercentageDiscount(DiscountPolicy):  # strategy: flat % off the whole order
    @staticmethod  # no self/cls: a plain utility function that lives in the class's namespace
    def is_valid_percent(percent: Decimal) -> bool:
        return 0 < percent <= 100  # chained comparison: valid range is (0, 100]

    def __init__(self, percent: Decimal):
        if not self.is_valid_percent(percent):  # reuse the static helper
            raise ValueError("percent must be in (0, 100]")  # fail fast on bad input
        self.percent = percent  # remember the discount percentage

    def apply(self, subtotal, lines):
        return money(subtotal * (100 - self.percent) / 100)  # e.g. 10% off -> multiply by 90/100


class BulkDiscount(PercentageDiscount):  # inherits % logic, adds a condition
    """Percent off only when the total quantity reaches min_quantity."""

    def __init__(self, min_quantity: int, percent: Decimal):
        super().__init__(percent)  # parent validates and stores percent
        self.min_quantity = min_quantity  # threshold of units to qualify

    def apply(self, subtotal, lines):
        if sum(line.quantity for line in lines) >= self.min_quantity:  # total units across all lines
            return super().apply(subtotal, lines)  # qualifies -> reuse parent's % discount
        return money(subtotal)  # does not qualify -> full price


# --- Step 3: Order = mutable, iterable, sortable, hashable -------------------
@dataclass(eq=False)  # eq=False: we write our own __eq__/__hash__ below
class Order:
    id: int  # unique order number
    customer: Customer  # who placed the order
    lines: list[OrderLine]  # the items in the order
    created_at: datetime  # when it was created
    discount: DiscountPolicy = field(default_factory=NoDiscount)  # new NoDiscount per order (avoids shared mutable default)

    
    @classmethod  # receives the class (cls) instead of an instance: an alternative constructor
    def from_products(cls, id: int, customer: Customer, items: list[tuple[Product, int]], discount: DiscountPolicy | None = None) -> "Order":
        lines = [OrderLine(product, qty) for product, qty in items]  # build lines from (product, quantity) pairs
        return cls(id, customer, lines, datetime.now(), discount or NoDiscount())  # cls(...) so subclasses get their own type

    @property
    def subtotal(self) -> Decimal:
        return money(sum((line.subtotal for line in self.lines), Decimal("0")))  # add all lines, start from Decimal 0

    @property
    def total(self) -> Decimal:
        return self.discount.apply(self.subtotal, self.lines)  # delegate to the strategy (polymorphism)

    def __len__(self):  # makes len(order) work
        return len(self.lines)  # number of lines

    def __iter__(self):  # makes "for line in order" work
        return iter(self.lines)  # iterate over the lines

    def __eq__(self, other):  # equal when same id
        return self.id == other.id if isinstance(other, Order) else NotImplemented  # only compare with Orders

    def __hash__(self):  # must agree with __eq__
        return hash(self.id)  # same id -> same hash, so usable in sets/dicts

    def __lt__(self, other):  # sort by (created_at, id)
        return (self.created_at, self.id) < (other.created_at, other.id)  # tuple compare: date first, id breaks ties


def grand_total(orders) -> Decimal:  # sums totals of many orders
    """Duck typing: works with anything that has a .total"""
    return money(sum((o.total for o in orders), Decimal("0")))  # no type check - only needs .total


# --- Demo --------------------------------------------------------------------
if __name__ == "__main__":  # runs only when executed directly, not when imported
    lamp = Product(1, "Lamp", Decimal("17.70"))  # create a product
    pen = Product(2, "Pen", Decimal("2.50"))  # create another product
    kavya = Customer(1, "Kavya", Tier.GOLD)  # a GOLD customer

    lines = [OrderLine(lamp, 3), OrderLine(pen, 10)]  # 3 lamps + 10 pens
    o1 = Order(1, kavya, lines, datetime(2025, 1, 2), BulkDiscount(10, Decimal("10")))  # 10% off if >= 10 units
    o2 = Order(2, kavya, lines[:1], datetime(2025, 1, 1))  # only the lamp line, no discount, earlier date

    print("o1 subtotal / total:", o1.subtotal, o1.total)  # 78.10 / 70.29
    print("lines in o1:", len(o1), [line.product.name for line in o1])  # uses __len__ and __iter__
    print("sorted ids:", [o.id for o in sorted([o1, o2])])  # [2, 1]  (uses __lt__)
    print("grand total:", grand_total([o1, o2]))  # duck-typed sum of both totals
    o3 = Order.from_products(3, kavya, [(lamp, 2), (pen, 4)])  # classmethod: no need to build OrderLines or a timestamp
    print("o3 via classmethod:", len(o3), o3.total)  # 2 lines, 45.40
    print("valid percent?", PercentageDiscount.is_valid_percent(Decimal("10")), PercentageDiscount.is_valid_percent(Decimal("150")))  # staticmethod: called on the class, no instance needed

    try:
        OrderLine(lamp, 0)  # invalid quantity
    except ValueError as e:  # __post_init__ raised
        print("rejected:", e)  # show the validation message
