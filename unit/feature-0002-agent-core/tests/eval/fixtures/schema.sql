-- ITEM-01 NL→SQL 평가 harness — 결정적 fixture datasource (합성, prod 무관, PII 없음).
--
-- 폐쇄망/PII 가드: 본 스키마는 완전 합성 데이터이며 운영 데이터와 무관하다. golden
-- 질문은 이 fixture 만 평가 대상으로 한다(runner 가 datasource=eval_fixture 강제).
--
-- 멱등: DROP+CREATE 로 매 provision 시 결정적 재구성(같은 시드 → 같은 정답 결과셋).
-- 작은 e-commerce 도메인(customers/products/orders/order_items) — 집계·조인·필터·
-- 시간범위·정렬·GROUP BY 등 NL→SQL 의 대표 패턴을 20+ 질문으로 커버 가능.

CREATE DATABASE IF NOT EXISTS eval_fixture
  CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE eval_fixture;

DROP TABLE IF EXISTS order_items;
DROP TABLE IF EXISTS orders;
DROP TABLE IF EXISTS products;
DROP TABLE IF EXISTS customers;

CREATE TABLE customers (
  id          INT PRIMARY KEY,
  name        VARCHAR(64)  NOT NULL,
  country     VARCHAR(32)  NOT NULL,
  signup_date DATE         NOT NULL,
  is_active   TINYINT      NOT NULL DEFAULT 1
) ENGINE=InnoDB;

CREATE TABLE products (
  id        INT PRIMARY KEY,
  name      VARCHAR(64)    NOT NULL,
  category  VARCHAR(32)    NOT NULL,
  price     DECIMAL(10,2)  NOT NULL,
  stock     INT            NOT NULL
) ENGINE=InnoDB;

CREATE TABLE orders (
  id          INT PRIMARY KEY,
  customer_id INT          NOT NULL,
  order_date  DATE         NOT NULL,
  status      VARCHAR(16)  NOT NULL,   -- placed | shipped | delivered | cancelled
  total       DECIMAL(10,2) NOT NULL,
  CONSTRAINT fk_orders_customer FOREIGN KEY (customer_id) REFERENCES customers(id)
) ENGINE=InnoDB;

CREATE TABLE order_items (
  id         INT PRIMARY KEY,
  order_id   INT           NOT NULL,
  product_id INT           NOT NULL,
  quantity   INT           NOT NULL,
  unit_price DECIMAL(10,2) NOT NULL,
  CONSTRAINT fk_items_order   FOREIGN KEY (order_id)   REFERENCES orders(id),
  CONSTRAINT fk_items_product FOREIGN KEY (product_id) REFERENCES products(id)
) ENGINE=InnoDB;

-- ── 결정적 시드 ────────────────────────────────────────────────────────────
INSERT INTO customers (id, name, country, signup_date, is_active) VALUES
  (1, 'Alice',   'KR', '2023-01-15', 1),
  (2, 'Bob',     'US', '2023-03-22', 1),
  (3, 'Carol',   'KR', '2023-06-10', 0),
  (4, 'Dave',    'JP', '2023-09-05', 1),
  (5, 'Eve',     'US', '2024-01-02', 1);

INSERT INTO products (id, name, category, price, stock) VALUES
  (1, 'Keyboard',  'electronics', 45.00, 100),
  (2, 'Mouse',     'electronics', 25.00, 200),
  (3, 'Desk',      'furniture',   150.00, 30),
  (4, 'Chair',     'furniture',   90.00, 50),
  (5, 'Notebook',  'stationery',  5.00,  500);

-- orders: 의도된 분포 — KR 고객 주문, 다양한 status, 2024 주문 포함.
INSERT INTO orders (id, customer_id, order_date, status, total) VALUES
  (1, 1, '2024-02-01', 'delivered', 95.00),
  (2, 1, '2024-02-15', 'shipped',   25.00),
  (3, 2, '2024-03-01', 'delivered', 150.00),
  (4, 2, '2024-03-20', 'cancelled', 90.00),
  (5, 3, '2023-12-25', 'delivered', 50.00),
  (6, 4, '2024-04-10', 'placed',    180.00),
  (7, 5, '2024-05-05', 'delivered', 10.00),
  (8, 1, '2024-06-01', 'placed',    45.00);

INSERT INTO order_items (id, order_id, product_id, quantity, unit_price) VALUES
  (1,  1, 1, 1, 45.00),
  (2,  1, 4, 1, 90.00),  -- 주문1 total 은 시드상 95.00 으로 고정(정합성은 질문이 강요하지 않음)
  (3,  2, 2, 1, 25.00),
  (4,  3, 3, 1, 150.00),
  (5,  4, 4, 1, 90.00),
  (6,  5, 5, 10, 5.00),
  (7,  6, 3, 1, 150.00),
  (8,  6, 4, 1, 30.00),  -- 할인가
  (9,  7, 5, 2, 5.00),
  (10, 8, 1, 1, 45.00);
