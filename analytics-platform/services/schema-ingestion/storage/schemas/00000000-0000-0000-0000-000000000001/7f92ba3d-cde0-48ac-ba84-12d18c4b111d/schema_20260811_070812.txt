-- Database Name: analytics_db

-- ==================================================
-- TABLE: categories
-- ==================================================
TABLE: categories
- category_id (INTEGER, PK, NOT NULL)
- category_name (VARCHAR(100))

-- ==================================================
-- TABLE: customer_addresses
-- ==================================================
TABLE: customer_addresses
- address_id (INTEGER, PK, NOT NULL)
- customer_id (INTEGER)
- address_type (VARCHAR(30))
- city (VARCHAR(100))
- state (VARCHAR(100))
- country (VARCHAR(100))
- postal_code (VARCHAR(20))

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
-- TABLE: employees
-- ==================================================
TABLE: employees
- employee_id (INTEGER, PK, NOT NULL)
- first_name (VARCHAR(100))
- last_name (VARCHAR(100))
- department (VARCHAR(100))
- designation (VARCHAR(100))
- salary (NUMERIC(12, 2))
- hire_date (DATE)
- store_id (INTEGER)

-- ==================================================
-- TABLE: inventory
-- ==================================================
TABLE: inventory
- inventory_id (INTEGER, PK, NOT NULL)
- product_id (INTEGER)
- warehouse (VARCHAR(100))
- stock_quantity (INTEGER)
- reorder_level (INTEGER)
- last_updated (TIMESTAMP)

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

-- ==================================================
-- TABLE: promotions
-- ==================================================
TABLE: promotions
- promotion_id (INTEGER, PK, NOT NULL)
- promotion_name (VARCHAR(150))
- discount_percent (NUMERIC(5, 2))
- start_date (DATE)
- end_date (DATE)
- promotion_type (VARCHAR(50))

-- ==================================================
-- TABLE: reviews
-- ==================================================
TABLE: reviews
- review_id (INTEGER, PK, NOT NULL)
- customer_id (INTEGER)
- product_id (INTEGER)
- rating (INTEGER)
- review_text (TEXT)
- review_date (DATE)

-- ==================================================
-- TABLE: shipments
-- ==================================================
TABLE: shipments
- shipment_id (INTEGER, PK, NOT NULL)
- order_id (INTEGER)
- courier (VARCHAR(100))
- tracking_number (VARCHAR(255))
- shipped_date (DATE)
- delivered_date (DATE)
- shipping_status (VARCHAR(50))

-- ==================================================
-- TABLE: stores
-- ==================================================
TABLE: stores
- store_id (INTEGER, PK, NOT NULL)
- store_name (VARCHAR(150))
- city (VARCHAR(100))
- state (VARCHAR(100))
- manager_name (VARCHAR(100))

-- ==================================================
-- TABLE: suppliers
-- ==================================================
TABLE: suppliers
- supplier_id (INTEGER, PK, NOT NULL)
- supplier_name (VARCHAR(200))
- city (VARCHAR(100))
- country (VARCHAR(100))
- contact_person (VARCHAR(100))