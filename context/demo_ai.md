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

<!-- discovered-context:start -->
## Table: support_tickets

This table represents the database of support tickets managed by a company, capturing details such as customer information, issue descriptions, priority levels, status, and handling team.

### Important columns

- `id`: A unique identifier for each ticket.
- `customer_name`: The name of the person who submitted the ticket.
- `customer_city`: The city where the customer resides.
- `subject`: A brief description of the problem or issue raised in the ticket.
- `priority`: An indication of how urgent the issue is (e.g., high, medium, low).
- `status`: The current state of the ticket (e.g., open, resolved, closed).
- `created_at`: The date and time when the ticket was created.
- `resolved_at`: The date and time when the ticket was last updated to indicate resolution or closure.

### Example questions

- What is the status of the ticket with ID 2?
- How many tickets have been assigned to the "Customer Support" team?
- What are the latest statuses for all open tickets created in May?
- Which city has submitted the most support tickets this year?
- Can you provide details on a specific ticket, such as Ticket ID 5?
<!-- discovered-context:end -->
