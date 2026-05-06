# demo_ai business context

This file explains the business meaning of tables in the demo_ai database.

## Tables

### customers

This table stores customer records.

Use this table when the user asks about:
- customers
- clients
- people
- registered users
- customer city
- customer names

Columns:
- id: unique customer id
- name: customer full name
- city: customer city
- created_at: customer creation date

### z9_kx_txn

This table stores product sales transactions.

Even though the physical table name is z9_kx_txn, it should be understood as the sales table.

Use this table when the user asks about:
- sales
- sold products
- product purchases
- who bought what
- revenue
- total sales amount
- best-selling products
- buyers
- purchase history

Columns:
- id: unique sales transaction id
- buyer_name: name of the person who bought the product
- product_name: name of the sold product
- quantity: number of units sold
- unit_price: price for one unit of the product
- sold_at: date and time when the sale happened

Business rules:
- Total line amount is quantity * unit_price
- Revenue means SUM(quantity * unit_price)
- Best-selling product means the product with the highest SUM(quantity)
- Top buyer means the buyer with the highest SUM(quantity * unit_price)