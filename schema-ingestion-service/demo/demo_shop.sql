-- Tiny demo "customer database" for local development.
-- Note: orders.customer_id has NO declared FK on purpose — it exercises the
-- naming + value-overlap detectors. order_items has a declared FK to orders.

CREATE TABLE customers (
    id         serial PRIMARY KEY,
    full_name  text NOT NULL,
    email      text NOT NULL,
    region     text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE products (
    id         serial PRIMARY KEY,
    name       text NOT NULL,
    category   text NOT NULL,
    unit_price numeric(10,2) NOT NULL
);

CREATE TABLE orders (
    id           serial PRIMARY KEY,
    customer_id  integer NOT NULL,          -- intentionally no declared FK
    order_status text NOT NULL DEFAULT 'placed',
    order_date   date NOT NULL,
    net_amt      numeric(12,2) NOT NULL
);
COMMENT ON COLUMN orders.net_amt IS 'Order amount after discounts, before tax';

CREATE TABLE order_items (
    id         serial PRIMARY KEY,
    order_id   integer NOT NULL REFERENCES orders(id),
    product_id integer NOT NULL REFERENCES products(id),
    quantity   integer NOT NULL,
    line_total numeric(12,2) NOT NULL
);

INSERT INTO customers (full_name, email, region)
SELECT 'Customer ' || i, 'user' || i || '@example.com',
       (ARRAY['NE-US','SE-US','EMEA','APAC'])[1 + (i % 4)]
FROM generate_series(1, 200) i;

INSERT INTO products (name, category, unit_price)
SELECT 'Product ' || i, (ARRAY['toys','books','games'])[1 + (i % 3)], (i % 50) + 4.99
FROM generate_series(1, 50) i;

INSERT INTO orders (customer_id, order_status, order_date, net_amt)
SELECT 1 + (i % 200),
       (ARRAY['placed','shipped','delivered','cancelled'])[1 + (i % 4)],
       date '2026-01-01' + (i % 180),
       ((i % 90) + 10) * 3.50
FROM generate_series(1, 2000) i;

INSERT INTO order_items (order_id, product_id, quantity, line_total)
SELECT 1 + (i % 2000), 1 + (i % 50), 1 + (i % 5), ((i % 5) + 1) * 12.75
FROM generate_series(1, 5000) i;
