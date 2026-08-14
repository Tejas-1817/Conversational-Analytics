-- Database Name: analytics_db

-- ==================================================
-- TABLE: categories
-- ==================================================
TABLE: categories
- category_id (INTEGER, PK, NOT NULL)
- category_name (VARCHAR(100))

-- ==================================================
-- TABLE: customers
-- ==================================================
TABLE: customers
- customer_id (INTEGER, PK, NOT NULL)
- first_name (VARCHAR(100))
- customer_segment (VARCHAR(50))
- registration_date (DATE)
- status (VARCHAR(30))

-- ==================================================
-- TABLE: order_items
-- ==================================================
TABLE: order_items
- order_item_id (INTEGER, PK, NOT NULL)
- order_id (INTEGER)
- product_id (INTEGER)
- quantity (INTEGER)
- unit_price (NUMERIC(12, 2))
- total_price (NUMERIC(12, 2))

-- ==================================================
-- TABLE: orders
-- ==================================================
TABLE: orders
- order_id (INTEGER, PK, NOT NULL)
- customer_id (INTEGER)
- order_date (DATE)
- order_status (VARCHAR(30))
- total_amount (NUMERIC(12, 2))

-- ==================================================
-- TABLE: payments
-- ==================================================
TABLE: payments
- payment_id (INTEGER, PK, NOT NULL)
- order_id (INTEGER)
- payment_method (VARCHAR(30))
- payment_date (DATE)
- amount (NUMERIC(12, 2))

-- ==================================================
-- TABLE: product_reviews
-- ==================================================
TABLE: product_reviews
- review_id (INTEGER, PK, NOT NULL)
- product_id (INTEGER)
- customer_id (INTEGER)
- rating (INTEGER)
- review_text (TEXT)
- review_date (DATE)

-- ==================================================
-- TABLE: products
-- ==================================================
TABLE: products
- product_id (INTEGER, PK, NOT NULL)
- product_name (VARCHAR(255))
- category_id (INTEGER)
- selling_price (NUMERIC(12, 2))
- status (VARCHAR(30))