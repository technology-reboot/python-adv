from datetime import date  # calendar date type
from decimal import Decimal  # exact decimal numbers for money
from typing import Literal  # restrict a value to a fixed set of strings

from pydantic import BaseModel, Field, ValidationError, field_validator, model_validator  # validation tools
from pydantic_settings import BaseSettings, SettingsConfigDict  # config loaded from environment

class OrderItem(BaseModel):  # one line item; BaseModel validates on creation
    product_id: int  # must be an int (numeric strings are converted)
    quantity: int = Field(gt=0)  # must be greater than 0
    unit_price: Decimal = Field(ge=0)  # must be >= 0

class OrderIn(BaseModel):  # incoming order payload
    customer_id: int  # who is ordering
    order_date: date  # the string '2025-03-01' is parsed for you
    status: Literal["pending", "paid", "shipped", "cancelled"] = "pending"  # only these values allowed
    items: list[OrderItem] = Field(min_length=1)  # at least one item, each validated as OrderItem

    @field_validator("status", mode="before")  # runs BEFORE the Literal check
    @classmethod
    def normalise(cls, v):
        return v.strip().lower() if isinstance(v, str) else v  # ' PAID ' -> 'paid'

    @model_validator(mode="after")  # runs after all fields are validated
    def not_in_future(self):
        if self.order_date > date.today():  # cross-field/business rule
            raise ValueError("order_date is in the future")  # becomes a ValidationError
        return self  # must return the model

    @property
    def total(self) -> Decimal:
        return sum((i.quantity * i.unit_price for i in self.items), Decimal("0"))  # sum of line totals


class Settings(BaseSettings):  # app configuration
    """Reads APP_DATABASE_URL etc. from environment variables or a .env file."""

    model_config = SettingsConfigDict(env_prefix="APP_", env_file=".env", extra="ignore")  # APP_ prefix, .env support, ignore unknown vars
    database_url: str = "sqlite:///codealong.db"  # default if APP_DATABASE_URL not set
    mock_api_url: str = "http://localhost:8001"  # default mock API address

if __name__ == "__main__":  # demo only when run directly
    ok = OrderIn.model_validate(  # validate a plain dict -> OrderIn object
        {
            "customer_id": 1,  # valid customer
            "order_date": "2025-03-01",  # string, parsed to a date
            "status": " PAID ",  # messy, normalised by the validator
            "items": [{"product_id": 1, "quantity": 2, "unit_price": "17.70"}],  # price string -> Decimal
        }
    )
    print(ok.status, ok.total, ok.model_dump_json())  # 'paid', 35.40, then the object as JSON

    try:
        OrderIn.model_validate({"customer_id": 1, "order_date": "nope", "status": "weird", "items": []})  # everything wrong
    except ValidationError as e:  # pydantic collects ALL errors, not just the first
        for err in e.errors():  # each error is a dict
            print(" -", ".".join(map(str, err["loc"])), "->", err["msg"])  # field path -> message

    print(Settings())  # show the loaded configuration