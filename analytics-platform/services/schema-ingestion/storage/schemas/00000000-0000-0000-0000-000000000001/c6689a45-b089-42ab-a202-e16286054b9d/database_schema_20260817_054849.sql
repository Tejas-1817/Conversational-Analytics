-- Database Name: ecommerce

-- ==================================================
-- TABLE: categories
-- ==================================================
TABLE: categories
- category_id (INTEGER, PK, NOT NULL)
- category_name (VARCHAR(100), NOT NULL)
- parent_category_id (INTEGER)

-- ==================================================
-- TABLE: customers
-- ==================================================
TABLE: customers
- customer_id (BIGINT, PK, NOT NULL)
- first_name (VARCHAR(60), NOT NULL)
- last_name (VARCHAR(60), NOT NULL)
- email (VARCHAR(150), NOT NULL)
- city (VARCHAR(80), NOT NULL)
- state (VARCHAR(50), NOT NULL)
- country (VARCHAR(50), NOT NULL)
- signup_date (DATE, NOT NULL)
- customer_segment (VARCHAR(30), NOT NULL)

-- ==================================================
-- TABLE: inventory_movements
-- ==================================================
TABLE: inventory_movements
- movement_id (BIGINT, PK, NOT NULL)
- product_id (BIGINT, NOT NULL)
- movement_date (TIMESTAMP, NOT NULL)
- movement_type (VARCHAR(20), NOT NULL)
- quantity (INTEGER, NOT NULL)
- reference_id (BIGINT)

-- ==================================================
-- TABLE: order_items
-- ==================================================
TABLE: order_items
- order_item_id (BIGINT, PK, NOT NULL)
- order_id (BIGINT, NOT NULL)
- product_id (BIGINT, NOT NULL)
- quantity (INTEGER, NOT NULL)
- unit_price (NUMERIC(12, 2), NOT NULL)
- discount (NUMERIC(5, 2), NOT NULL)

-- ==================================================
-- TABLE: orders
-- ==================================================
TABLE: orders
- order_id (BIGINT, PK, NOT NULL)
- customer_id (BIGINT, NOT NULL)
- order_date (TIMESTAMP, NOT NULL)
- order_status (VARCHAR(30), NOT NULL)
- shipping_city (VARCHAR(80), NOT NULL)
- shipping_state (VARCHAR(50), NOT NULL)
- shipping_fee (NUMERIC(10, 2), NOT NULL)
- coupon_code (VARCHAR(30))
- coupon_discount (NUMERIC(10, 2), NOT NULL)

-- ==================================================
-- TABLE: payments
-- ==================================================
TABLE: payments
- payment_id (BIGINT, PK, NOT NULL)
- order_id (BIGINT, NOT NULL)
- payment_date (TIMESTAMP, NOT NULL)
- payment_method (VARCHAR(30), NOT NULL)
- payment_status (VARCHAR(20), NOT NULL)
- amount (NUMERIC(12, 2), NOT NULL)
- transaction_ref (VARCHAR(80))

-- ==================================================
-- TABLE: products
-- ==================================================
TABLE: products
- product_id (BIGINT, PK, NOT NULL)
- product_name (VARCHAR(180), NOT NULL)
- category_id (INTEGER, NOT NULL)
- seller_id (BIGINT, NOT NULL)
- unit_price (NUMERIC(12, 2), NOT NULL)
- cost_price (NUMERIC(12, 2), NOT NULL)
- stock_quantity (INTEGER, NOT NULL)
- launch_date (DATE, NOT NULL)
- is_active (BOOLEAN, NOT NULL)

-- ==================================================
-- TABLE: reviews
-- ==================================================
TABLE: reviews
- review_id (BIGINT, PK, NOT NULL)
- order_id (BIGINT, NOT NULL)
- product_id (BIGINT, NOT NULL)
- customer_id (BIGINT, NOT NULL)
- rating (INTEGER, NOT NULL)
- review_title (VARCHAR(150))
- review_text (TEXT)
- review_date (DATE, NOT NULL)

-- ==================================================
-- TABLE: sellers
-- ==================================================
TABLE: sellers
- seller_id (BIGINT, PK, NOT NULL)
- seller_name (VARCHAR(120), NOT NULL)
- city (VARCHAR(80), NOT NULL)
- state (VARCHAR(50), NOT NULL)
- country (VARCHAR(50), NOT NULL)
- rating (NUMERIC(3, 2))
- join_date (DATE, NOT NULL)