"""Session 14 - FastAPI: REST API over the database (reuses db.py from session 10).

Run (from the codealong folder):  uvicorn 14_fastapi:app --app-dir day2 --reload
Open the auto docs:               http://localhost:8000/docs
Observability demo:               watch the console logs; try GET /metrics and the X-Request-ID header
"""
import logging  # standard library logging
import time  # measure request duration
import uuid  # generate request ids
from collections import Counter  # simple in-memory metrics
from contextvars import ContextVar  # per-request value that is safe with async code
from datetime import date  # date type for order_date
from decimal import Decimal  # exact money type
from typing import Annotated, Literal  # Annotated attaches metadata to a type; Literal limits allowed values

from db import Customer, Order, OrderItem, Product, SessionLocal, load_sample_data  # ORM models + session factory
from fastapi import Depends, FastAPI, HTTPException, Query, Request  # framework pieces
from fastapi.responses import JSONResponse  # build a custom error response
from pydantic import BaseModel, ConfigDict, Field  # request/response schemas
from sqlalchemy import select, text  # build SELECT statements / run raw SQL
from sqlalchemy.orm import Session, selectinload  # session type + eager loading

# --- Logging + traceability: every log line carries the id of its request -----
request_id_var: ContextVar[str] = ContextVar("request_id", default="-")  # current request id ("-" outside a request)


class RequestIdFilter(logging.Filter):  # stamps each log record with the current request id
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_var.get()  # read the id for the request being handled
        return True  # keep the record


logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-7s [%(request_id)s] %(name)s: %(message)s")  # one format for all logs
for handler in logging.getLogger().handlers:  # filter goes on the handler so library logs (SQLAlchemy...) get the id too
    handler.addFilter(RequestIdFilter())
# logging.getLogger("sqlalchemy.engine").setLevel(logging.INFO)  # uncomment to log every SQL statement with its request id

logger = logging.getLogger("orders_api")  # our own named logger
metrics: Counter = Counter()  # in-memory counters, reset on restart (a real system would use Prometheus)
latency_ms_total: Counter = Counter()  # total time spent per route

app = FastAPI(title="Orders API")  # the app; title appears in /docs
load_sample_data()  # make sure tables and sample data exist at startup


# --- Middleware: runs around every request ------------------------------------
@app.middleware("http")
async def observe(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex[:8]  # reuse caller's id so traces span services
    token = request_id_var.set(request_id)  # make it visible to every log line in this request
    start = time.perf_counter()  # start the timer
    try:
        response = await call_next(request)  # run the endpoint
    except Exception:  # unhandled error: log the stack trace and return a clean 500
        logger.exception("unhandled error on %s %s", request.method, request.url.path)
        response = JSONResponse({"detail": "internal server error", "request_id": request_id}, status_code=500)
    ms = (time.perf_counter() - start) * 1000  # elapsed milliseconds
    route = request.scope.get("route")  # matched route, e.g. /orders/{order_id}
    path = route.path if route else request.url.path  # template keeps metric cardinality low
    metrics[f"{request.method} {path} {response.status_code}"] += 1  # count by method, path, status
    latency_ms_total[f"{request.method} {path}"] += ms  # accumulate latency
    logger.info("%s %s -> %s in %.1f ms", request.method, request.url.path, response.status_code, ms)  # access log
    response.headers["X-Request-ID"] = request_id  # return the id so clients can quote it in bug reports
    response.headers["X-Process-Time"] = f"{ms:.1f}ms"  # expose timing
    request_id_var.reset(token)  # clean up
    return response


# --- Dependency: one DB session per request, closed afterwards -----------------
def get_db():
    with SessionLocal() as session:  # open a session
        yield session  # give it to the endpoint; cleanup runs after the response


DB = Annotated[Session, Depends(get_db)]  # reusable type: "a Session injected by get_db"


# --- Pydantic schemas = request validation + response shape -------------------
class ItemIn(BaseModel):  # one item in a create-order request
    product_id: int  # which product
    quantity: int = Field(gt=0)  # must be positive


class OrderIn(BaseModel):  # body of POST /orders
    customer_id: int  # who orders
    order_date: date  # parsed from 'YYYY-MM-DD'
    items: list[ItemIn] = Field(min_length=1)  # at least one item


class OrderOut(BaseModel):  # shape of order responses
    model_config = ConfigDict(from_attributes=True)  # build from ORM objects
    id: int  # order id
    customer_id: int  # owner
    order_date: date  # date of order
    status: str  # pending/paid/...
    total: Decimal  # computed property on the ORM model


@app.get("/health")  # readiness check: is the app AND its database working?
def health(db: DB):
    db.execute(text("SELECT 1"))  # cheapest possible DB round trip; raises if the DB is down
    return {"status": "ok"}  # returned as JSON


@app.get("/metrics")  # tiny metrics endpoint (Prometheus would expose a similar text format)
def get_metrics():
    return {"requests": dict(metrics), "latency_ms_total": {k: round(v, 1) for k, v in latency_ms_total.items()}}


@app.get("/orders", response_model=list[OrderOut])  # response filtered/validated as a list of OrderOut
def list_orders(
    db: DB,  # injected database session
    status: Literal["pending", "paid", "shipped", "cancelled"] | None = None,  # optional query filter, validated
    limit: int = Query(20, ge=1, le=100),  # page size, between 1 and 100
    offset: int = Query(0, ge=0),  # how many rows to skip
):
    logger.debug("list_orders status=%s limit=%s offset=%s", status, limit, offset)  # debug: hidden at INFO level
    query = select(Order).options(selectinload(Order.items)).order_by(Order.id).limit(limit).offset(offset)  # paged query, eager-load items (avoids N+1)
    if status:  # filter only when provided
        query = query.where(Order.status == status)  # add WHERE clause
    return db.scalars(query).all()  # run and return list of Order objects


@app.get("/orders/{order_id}", response_model=OrderOut)  # path parameter
def get_order(order_id: int, db: DB):
    order = db.scalar(select(Order).options(selectinload(Order.items)).where(Order.id == order_id))  # first match or None
    if order is None:  # no such order
        logger.warning("order %s not found", order_id)  # expected client error -> warning, not error
        raise HTTPException(status_code=404, detail="order not found")  # 404 response
    return order  # serialised via OrderOut


@app.post("/orders", response_model=OrderOut, status_code=201)  # 201 Created on success
def create_order(payload: OrderIn, db: DB):  # body validated into OrderIn automatically
    if db.get(Customer, payload.customer_id) is None:  # primary-key lookup
        logger.warning("create_order rejected: unknown customer %s", payload.customer_id)
        raise HTTPException(status_code=422, detail="unknown customer")  # reject bad reference
    order = Order(customer_id=payload.customer_id, order_date=payload.order_date)  # new order (status defaults to pending)
    for item in payload.items:  # add each requested item
        product = db.get(Product, item.product_id)  # look up the product
        if product is None:  # unknown product
            logger.warning("create_order rejected: unknown product %s", item.product_id)
            raise HTTPException(status_code=422, detail=f"unknown product {item.product_id}")  # reject
        order.items.append(OrderItem(product_id=product.id, quantity=item.quantity, unit_price=product.price))  # snapshot the current price
    db.add(order)  # stage the order (and its items via cascade)
    db.commit()  # write to the database
    db.refresh(order)  # reload generated values such as id
    logger.info("order created id=%s customer=%s items=%d", order.id, order.customer_id, len(order.items))  # business event
    return order  # serialised via OrderOut


@app.delete("/orders/{order_id}", status_code=204)  # 204 No Content on success
def delete_order(order_id: int, db: DB):
    order = db.get(Order, order_id)  # find by primary key
    if order is None:  # nothing to delete
        logger.warning("delete: order %s not found", order_id)
        raise HTTPException(status_code=404, detail="order not found")  # 404 response
    db.delete(order)  # mark for deletion (items too, via cascade)
    db.commit()  # apply the delete
    logger.info("order deleted id=%s", order_id)
