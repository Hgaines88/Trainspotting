# Trainspotting

**Fashion history in motion.**

Trainspotting is a public, structured record of the designers, labels, and
collections that shape fashion history. It began as **Collection Archive
(OneToManys)**, a three-tier learning project built around a designer-to-
collections relationship. Trainspotting carries that working foundation
forward as an independent product with a broader data model and a clearer
discovery mission.

Today, visitors can browse designers and their collections across labels,
seasons, and years through matching React and Vanilla JavaScript clients backed
by FastAPI and SQLite. The public archive is read-only; only a Clerk-authenticated
Trainspotting administrator can change canonical records.

## Why Trainspotting is the next version

Most fashion archives present editorial pages. Trainspotting is designed to
treat fashion history as connected, queryable data: who worked at which label,
when they worked there, what they released, who shared credit, and how one body
of work relates stylistically to another.

The planned model expands the inherited archive with:

- labels as first-class records rather than collection text;
- designer tenures that capture roles and creative-director succession;
- multi-designer credits for collaborations and guest designers;
- collective membership without erasing individual contributors;
- weighted style tags that can power content-based recommendations;
- user favorites and connections for personal discovery; and
- source reconciliation across open datasets and primary records.

These are the product direction, not claims about the current schema. The
current application still uses its proven designer-to-collections model while
the expanded ERD is implemented incrementally.

## Current capabilities

- Browse designer profiles and their related collections.
- View collection details, curated sources, and official runway videos.
- Browse without an account while all archive mutations remain protected.
- Submit sourced additions and corrections from an authenticated account.
- Review proposals through a moderator queue without changing canonical data
  until approval.
- Use either the React client or the matching Vanilla JavaScript client.
- Preserve canonical archive content in reviewable JSON.
- Run locally or as a Docker Compose stack.
- Validate API, data, migration, and frontend parity behavior with tests.

## Technology

- SQLite
- Python
- FastAPI
- Vanilla HTML, CSS, and JavaScript
- React and Vite
- Pytest

## Run locally

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements.txt
python3 -m scripts.init_db
uvicorn app.main:app --reload --env-file .env
```

In a second terminal, start the React client:

```bash
cd react-ui
npm install
npm run dev
```

Vite serves React at `http://localhost:5173` and proxies `/api` requests to
FastAPI at `http://127.0.0.1:8000`. The Vanilla client is served directly by
FastAPI at `http://127.0.0.1:8000`.

## Run with Docker

Build and start the API, React client, and persistent SQLite storage:

```bash
docker compose up --build
```

The React client is available at `http://localhost:5173`, and the FastAPI-served
Vanilla client and API are available at `http://localhost:8000`. Archive changes
are retained in the `archive-data` Docker volume when containers restart.

Stop the app with `docker compose down`. To also remove the persisted database
and recreate it from `data/archive.json` on the next start, run:

```bash
docker compose down --volumes
```

## Run the tests

With the virtual environment active, run the complete suite from the repository
root:

```bash
pytest -q
```

To print the designers currently stored in the archive from the project root,
run the utility script as a Python module:

```bash
python3 -m app.list_designers
```

`init_db.py` creates `data/archive.db` from the canonical `data/archive.json`
snapshot only when the database does not already exist. It never overwrites
live archive records.

After the first Clerk user signs in and synchronizes through `/me`, bootstrap
the first administrator with that user's immutable Clerk ID:

```bash
python3 -m scripts.bootstrap_admin user_your_clerk_user_id
```

The command is deliberately limited to the first administrator. It is
idempotent for that user and refuses to replace an existing administrator.

## Preserve and restore archive content

SQLite is the local runtime database and remains ignored by Git. The canonical,
reviewable content record is `data/archive.json`. After making an approved
administrative content change, refresh that snapshot with:

```bash
python3 -m scripts.archive_data export
```

Restore it into a new database, or merge it into an existing database, with:

```bash
python3 -m scripts.archive_data import --database data/restored.db --replace
```

Designer and collection keys in the JSON are stable text identifiers; generated
SQLite IDs are deliberately not exported. Tests verify that export → import →
export produces identical content and that repeated merge imports are idempotent.

Historically, records added through either client were stored in the same live
database and appeared in both interfaces. The public clients are now read-only;
future authenticated admin tools will preserve the same canonical-data
workflow. SQL files
under `sql/migrations/` contain deliberate database upgrades. FastAPI applies
each migration once at startup and records it in `schema_migrations`; migrations
never recreate the database from seed data.

## Application structure

sql/schema.sql
    #Schema.sql defines the database tables, fields, constraints, foreign key, and index.
data/archive.json
    #The canonical archive content. It is deterministic, human-readable, portable, and committed separately from schema migrations.
sql/seed.sql
    #Legacy instructional seed data retained for the original SQL exercise and tests. Migrations 001 and 003–005 are historical data corrections retained for reproducibility; all new curated content goes through data/archive.json rather than new data migrations.
scripts/init_db.py
    #Init_db.py restores the canonical JSON archive only when the database does not exist.
app/database.py
    #Database.py opens and configures connections used during normal API reads and writes.
app/schemas.py
    #Schemas.py defines the accepted structure and validation rules for designer and collection data received by the API. The SQL tables remain defined separately in schema.sql.
app/main.py
    #Main.py defines the middle-tier FastAPI application. Public read routes query SQLite, while every mutation route passes through the centralized administrator guard that will be connected to Clerk authentication.
web/
    #The web/ directory contains the read-only Vanilla client. Legacy form files remain unlinked until an authenticated administrative interface replaces them.
tests/
    #The tests verify API functionality by sending predefined input and comparing the response with expected output. Each test uses a temporary database so the real archive data is not changed.
react-ui/src/App.jsx
    #App.jsx is the public React routing map. It exposes list and detail views inside the shared layout; mutation forms are deliberately absent.
react-ui/src/pages/DesignerList.jsx
    #DesignerList.jsx requests designers from FastAPI when it first loads, stores the result in React state, and maps each designer record into a linked card on the home page.
react-ui/src/pages/DesignerDetail.jsx
    #DesignerDetail reads a designer ID from the React route, requests the designer and related collections from FastAPI, and renders the one-to-many relationship without public mutation controls.
react-ui/src/pages/DesignerForm.jsx
    #DesignerForm retains the former create/edit implementation for reuse by a future authenticated admin interface, but no public React route exposes it.
react-ui/src/pages/CollectionDetail.jsx
    #CollectionDetail requests one collection, displays its joined designer and optional media, and links back to the designer without public mutation controls.
react-ui/src/pages/CollectionForm.jsx
    #CollectionForm retains the former create/edit implementation for reuse by a future authenticated admin interface, but no public React route exposes it.
react-ui/src/api.js
    #Api.js centralizes communication between React and FastAPI. It prefixes API requests so Vite can proxy them to the backend, adds the JSON content header when a request has a body, parses successful JSON responses, handles empty deletion responses, and converts unsuccessful HTTP responses into JavaScript errors that page components can display.

## Moderation workflow

Authenticated members can create sourced additions and corrections from the
React client. Proposals remain separate from canonical designers and
collections while they are drafted or reviewed. Moderators may approve,
reject, or request changes, but cannot review their own submissions.

Approval validates the proposal again and promotes it in the same SQLite
transaction as the decision, promotion snapshot, and audit event. Retrying a
successful approval is idempotent. Administrators may perform a controlled
rollback only when the canonical record has not changed since approval. See
[`docs/SUBMISSION_FIELD_REQUIREMENTS.md`](docs/SUBMISSION_FIELD_REQUIREMENTS.md)
for field rules and state transitions.

# OnesToManys (ListDetails)

The point of this project is to explore what a 3-tier web application is like.
You can implment it in either Java (and Java frameworks) or Python (and Python frameworks).

Choosing one possible project relations below, you need to create a ListDetails application that allows users to manage their data in a 3-tier architecture.

This means it will have a REST API middle-end, with a relational database backend.

It has three phases.

### Phase 1 (days 1-2)

- build a plan for the project
- design the database schema by building out data objects
- write a SQL file with the schema
- generate another SQL file filled with synthetic generated data that can be loaded into the database
- create a REST server to create, read, update, and delete data objects
  - start with `curl` and doing a GET of your _master_ table
  - continue with `curl` and doing a GET of your _detail_ table
  - add the other CRUD operations for both master and detail tables

### Phase 2 (days 3-4)

- add a one to many relationship between your master and detail tables
- add REST API endpoints for the one to many relationship
- use a GUI based REST API client to test your endpoints
  - you might use Postman or Insomnia, or even Everest.
- add a means to dump and load your data to either SQL and/or JSON files

### Phase 3 (days 5-7)

- create a simple Vanilla JavaScript application to interact with your REST API
- do the same with React
- add web pages for CRUD operations for both master and detail tables
- add web pages for the one to many relationship, designing a UI that shows some dynamic data from the database

### Overall ListDetails Stacks

A basic SQL lab: tables, schema, selects, and crud in SQL repl; simple API access
Java: ListDetail phase 1,2 REST/DB app https://spring.io/guides/gs/accessing-data-rest Spring; Data: ListDetail phase 1,2 REST/DB app (fastapi, flask, sqlite3
https://zcw.guru/kristofer/ae5cb89250b14a6da2903a9cc613390b

## Understanding Master-Detail Relationships in Data Modeling


## What is a Master-Detail Relationship?

A master-detail relationship (sometimes called parent-child relationship) is a fundamental data modeling concept where:

- **Master (Parent) Entity**: Contains primary information and can exist independently
- **Detail (Child) Entity**: Contains secondary information that depends on the master entity and cannot exist without it

## Why Master-Detail Relationships Matter

Understanding master-detail relationships is crucial for several reasons:

1. **Data Integrity**: Ensures related data remains consistent and valid
2. **Efficient Data Organization**: Provides logical structure to complex information
3. **Improved User Experience**: Enables intuitive navigation through hierarchical data
4. **Optimized Queries**: Allows for more efficient database operations
5. **Scalable Application Design**: Creates maintainable, extensible software architecture

## Real-World Examples Across Domains

### E-Commerce
- **Master**: Order
- **Detail**: Order Items

An order can contain multiple items, but each order item belongs to exactly one order.

### Finance
- **Master**: Invoice
- **Detail**: Line Items

An invoice contains multiple line items, but each line item is associated with exactly one invoice.

### Healthcare
- **Master**: Patient
- **Detail**: Medical Records

A patient has multiple medical records, but each record belongs to one patient.

### Education
- **Master**: Course
- **Detail**: Lectures/Assignments

A course consists of multiple lectures and assignments, but each lecture/assignment belongs to one course.

## Database Implementation

In relational databases, master-detail relationships are typically implemented using foreign keys:

```/dev/null/example-schema.sql#L1-10
CREATE TABLE orders (
    order_id INT PRIMARY KEY,
    customer_id INT,
    order_date DATE
);

CREATE TABLE order_items (
    item_id INT PRIMARY KEY,
    order_id INT REFERENCES orders(order_id),
    product_id INT,
    quantity INT
);
```

## Implementing in Java and Python

### Java Example (Spring Boot)

```/dev/null/Order.java#L1-15
@Entity
public class Order {
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    private Date orderDate;

    @OneToMany(mappedBy = "order", cascade = CascadeType.ALL)
    private List<OrderItem> items = new ArrayList<>();

    // Getters and setters
}
```

```/dev/null/OrderItem.java#L1-15
@Entity
public class OrderItem {
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @ManyToOne
    @JoinColumn(name = "order_id")
    private Order order;

    private String productName;
    private int quantity;

    // Getters and setters
}
```

### Python Example (SQLAlchemy)

```/dev/null/models.py#L1-20
from sqlalchemy import Column, Integer, String, ForeignKey, Date
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

Base = declarative_base()

class Order(Base):
    __tablename__ = 'orders'
    id = Column(Integer, primary_key=True)
    order_date = Column(Date)
    items = relationship("OrderItem", back_populates="order")

class OrderItem(Base):
    __tablename__ = 'order_items'
    id = Column(Integer, primary_key=True)
    order_id = Column(Integer, ForeignKey('orders.id'))
    product_name = Column(String)
    quantity = Column(Integer)
    order = relationship("Order", back_populates="items")
```

## REST API Design for Master-Detail

A well-designed REST API should reflect the master-detail relationship in its endpoints:

### Resource Structure
- `/orders` - Get all orders
- `/orders/{id}` - Get a specific order
- `/orders/{id}/items` - Get all items for a specific order
- `/orders/{id}/items/{itemId}` - Get a specific item from a specific order

### Java Example (Spring Boot)

```/dev/null/OrderController.java#L1-22
@RestController
@RequestMapping("/api/orders")
public class OrderController {
    @Autowired
    private OrderService orderService;

    @GetMapping
    public List<Order> getAllOrders() {
        return orderService.findAll();
    }

    @GetMapping("/{id}")
    public Order getOrderById(@PathVariable Long id) {
        return orderService.findById(id);
    }

    @GetMapping("/{id}/items")
    public List<OrderItem> getOrderItems(@PathVariable Long id) {
        Order order = orderService.findById(id);
        return order.getItems();
    }
}
```

### Python Example (Flask)

```/dev/null/app.py#L1-25
from flask import Flask, jsonify
from models import Order, OrderItem
from database import db_session

app = Flask(__name__)

@app.route('/api/orders', methods=['GET'])
def get_all_orders():
    orders = Order.query.all()
    return jsonify([{'id': o.id, 'order_date': o.order_date} for o in orders])

@app.route('/api/orders/<int:order_id>', methods=['GET'])
def get_order(order_id):
    order = Order.query.get_or_404(order_id)
    return jsonify({
        'id': order.id,
        'order_date': order.order_date,
        'items': [{'id': item.id, 'product_name': item.product_name} for item in order.items]
    })

@app.route('/api/orders/<int:order_id>/items', methods=['GET'])
def get_order_items(order_id):
    order = Order.query.get_or_404(order_id)
    return jsonify([{'id': item.id, 'product_name': item.product_name} for item in order.items])
```

## Administration Best Practices

1. **Cascade Operations**: Properly configure delete/update cascades
2. **Indexes**: Create appropriate indexes on foreign keys
3. **Constraints**: Implement referential integrity constraints
4. **Transactions**: Use transactions for operations involving both master and detail records
5. **Pagination**: Implement pagination for large detail collections
6. **Caching**: Consider caching frequently accessed master records

## Conclusion

Master-detail relationships are the backbone of effective data modeling and application development. Understanding these relationships enables beginners to:

1. Design intuitive and efficient data models
2. Create scalable database schemas
3. Develop user-friendly applications
4. Build RESTful APIs that accurately represent business domains

As you progress in your Java or Python development journey, mastering this concept will significantly enhance your ability to model real-world problems and create robust solutions. Whether you're building a simple to-do app or an enterprise-grade system, the master-detail pattern will be a constant companion in your development toolkit.

## But wait...DTO?

What's a DTO? Why? https://zcw.guru/kristofer/dtointro

## Possible project relations

These are some possible projrct relations for your ListDetail app.
You can also propose your own project relations, but it must be approved by an
instructor.

- Customer (master) - Orders (detail)
- Department (master) - Employees (detail)
- Course (master) - Students (detail)
- Author (master) - Books (detail)
- Invoice (master) - Line Items (detail)
- Product Category (master) - Products (detail)
- Blog Post (master) - Comments (detail)
- Playlist (master) - Songs (detail)
- Movie (master) - Actors (detail)
- University (master) - Departments (detail)
- Project (master) - Tasks (detail)
- Manufacturer (master) - Products (detail)
- Warehouse (master) - Inventory Items (detail)
- Email (master) - Attachments (detail)
- Country (master) - States/Provinces (detail)
- Hospital (master) - Patients (detail)
- Album (master) - Photos (detail)
- Survey (master) - Questions (detail)

---

*(h)gaines.*
