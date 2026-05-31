import hashlib

try:
    import psycopg2
    from psycopg2.extras import DictCursor
except Exception:
    psycopg2 = None
    DictCursor = None

from config import PG_DATABASE, PG_HOST, PG_PASSWORD, PG_PORT, PG_USER

DatabaseError = psycopg2.Error if psycopg2 else Exception

def sha256_password(password):
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


class QueryResult:
    def __init__(self, cursor, lastrowid=None):
        self.cursor = cursor
        self.lastrowid = lastrowid

    def fetchone(self):
        return self.cursor.fetchone()

    def fetchall(self):
        return self.cursor.fetchall()


class Database:
    """Работа с PostgreSQL: создание таблиц, тестовые данные и запросы интерфейса."""

    def __init__(self):
        if psycopg2 is None:
            raise RuntimeError(
                "Не установлен драйвер PostgreSQL. Выполните: pip install psycopg2"
            )
        self.conn = psycopg2.connect(
            host=PG_HOST,
            port=PG_PORT,
            dbname=PG_DATABASE,
            user=PG_USER,
            password=PG_PASSWORD,
            cursor_factory=DictCursor,
        )
        self.create_tables()
        self.seed_data()

    def execute(self, sql, params=None):
        # В первой версии проекта были SQLite-плейсхолдеры ?.
        # Здесь они автоматически меняются на формат PostgreSQL %s.
        sql = sql.replace("?", "%s")
        upper_sql = sql.strip().upper()
        needs_id = upper_sql.startswith("INSERT INTO PRODUCTS(") or upper_sql.startswith("INSERT INTO ORDERS(")
        if needs_id and "RETURNING ID" not in upper_sql:
            sql = sql.rstrip() + " RETURNING id"

        cursor = self.conn.cursor()
        cursor.execute(sql, params or ())
        lastrowid = None
        if needs_id:
            lastrowid = cursor.fetchone()[0]
        return QueryResult(cursor, lastrowid)

    def executescript(self, script):
        for statement in script.split(";"):
            statement = statement.strip()
            if statement:
                self.execute(statement)

    def rollback(self):
        self.conn.rollback()

    def create_tables(self):
        # Таблицы создаются при первом запуске. Если таблицы уже есть, данные не стираются.
        self.executescript(
            """
            CREATE TABLE IF NOT EXISTS roles (
                id SERIAL PRIMARY KEY,
                role_name TEXT NOT NULL UNIQUE
            );

            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                login TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                role_id INTEGER NOT NULL,
                full_name TEXT NOT NULL,
                phone TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (role_id) REFERENCES roles(id)
            );

            CREATE TABLE IF NOT EXISTS growing_conditions (
                id SERIAL PRIMARY KEY,
                climate_zone TEXT NOT NULL,
                soil_type TEXT NOT NULL,
                sunlight TEXT NOT NULL,
                watering TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS products (
                id SERIAL PRIMARY KEY,
                article TEXT NOT NULL UNIQUE,
                name TEXT NOT NULL,
                type TEXT NOT NULL,
                brand TEXT NOT NULL,
                price NUMERIC(10,2) NOT NULL CHECK(price > 0),
                quantity INTEGER NOT NULL DEFAULT 0 CHECK(quantity >= 0),
                category TEXT NOT NULL,
                description TEXT,
                image_path TEXT,
                planting_season TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS product_condition_link (
                product_id INTEGER NOT NULL,
                condition_id INTEGER NOT NULL,
                PRIMARY KEY (product_id, condition_id),
                FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE,
                FOREIGN KEY (condition_id) REFERENCES growing_conditions(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS orders (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL,
                order_date TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                status TEXT NOT NULL DEFAULT 'new',
                total_amount NUMERIC(10,2) NOT NULL DEFAULT 0,
                delivery_address TEXT NOT NULL,
                phone TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id)
            );

            CREATE TABLE IF NOT EXISTS order_items (
                id SERIAL PRIMARY KEY,
                order_id INTEGER NOT NULL,
                product_id INTEGER NOT NULL,
                count INTEGER NOT NULL CHECK(count > 0),
                price_at_order NUMERIC(10,2) NOT NULL,
                FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE CASCADE,
                FOREIGN KEY (product_id) REFERENCES products(id)
            );

            CREATE TABLE IF NOT EXISTS logs (
                id SERIAL PRIMARY KEY,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                user_login TEXT,
                action TEXT NOT NULL
            );
            """
        )
        self.conn.commit()

    def seed_data(self):
        # Тестовые данные добавляются только если таблица ролей пустая.
        if self.execute("SELECT COUNT(*) FROM roles").fetchone()[0] > 0:
            return

        for role in ("guest", "client", "manager", "admin"):
            self.execute("INSERT INTO roles(role_name) VALUES (?)", (role,))

        users = [
            ("admin_garden", "GardenAdmin2026!", "admin", "Петрова А.В.", "+7 900 111-22-33"),
            ("manager01", "Manager#789", "manager", "Сидоров Е.К.", "+7 900 222-33-44"),
            ("client_ivanov", "Client@321", "client", "Иванов Д.М.", "+7 900 333-44-55"),
        ]
        for login, password, role, name, phone in users:
            role_id = self.role_id(role)
            self.execute(
                """
                INSERT INTO users(login, password_hash, role_id, full_name, phone)
                VALUES (?, ?, ?, ?, ?)
                """,
                (login, sha256_password(password), role_id, name, phone),
            )

        conditions = [
            ("Умеренный", "Суглинок", "Солнце", "Умеренно"),
            ("Умеренный", "Универсальная", "Полутень", "Редко"),
            ("Тропический", "Питательная", "Полутень", "Ежедневно"),
            ("Южный", "Песчаная", "Солнце", "Редко"),
        ]
        for item in conditions:
            self.execute(
                """
                INSERT INTO growing_conditions(climate_zone, soil_type, sunlight, watering)
                VALUES (?, ?, ?, ?)
                """,
                item,
            )

        products = [
            ("GS-001", "Роза чайная", "plant", "GreenLine", 650, 12, "Цветы", "Нежная роза для сада. Любит солнечные места.", "Весна", [1]),
            ("GS-002", "Томаты Бычье сердце", "seed", "АгроСемена", 95, 80, "Овощи", "Крупноплодный сорт томатов для теплицы и открытого грунта.", "Весна", [1, 4]),
            ("GS-003", "Базилик зелёный", "seedling", "ЭкоРассада", 180, 30, "Зелень", "Ароматная зелень для кухни и балкона.", "Круглый год", [2]),
            ("GS-004", "Фикус Бенджамина", "plant", "HomePlants", 1200, 7, "Комнатные", "Комнатное растение с плотной кроной.", "Круглый год", [3]),
            ("GS-005", "Тюльпан жёлтый", "bulb", "FlowerMix", 70, 120, "Цветы", "Луковица тюльпана с ярким весенним цветением.", "Осень", [1]),
            ("GS-006", "Сосна горная", "seedling", "ЛесПитомник", 900, 5, "Деревья", "Неприхотливая хвойная рассада для участка.", "Весна", [4]),
        ]
        for article, name, ptype, brand, price, quantity, category, desc, season, condition_ids in products:
            cur = self.execute(
                """
                INSERT INTO products(article, name, type, brand, price, quantity, category, description, planting_season)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (article, name, ptype, brand, price, quantity, category, desc, season),
            )
            product_id = cur.lastrowid
            for condition_id in condition_ids:
                self.execute(
                    "INSERT INTO product_condition_link(product_id, condition_id) VALUES (?, ?)",
                    (product_id, condition_id),
                )

        client_id = self.execute("SELECT id FROM users WHERE login='client_ivanov'").fetchone()[0]
        order_id = self.execute(
            """
            INSERT INTO orders(user_id, status, total_amount, delivery_address, phone)
            VALUES (?, 'processing', 745, 'г. Москва, ул. Садовая, 5', '+7 900 333-44-55')
            """,
            (client_id,),
        ).lastrowid
        self.execute(
            "INSERT INTO order_items(order_id, product_id, count, price_at_order) VALUES (?, 1, 1, 650)",
            (order_id,),
        )
        self.execute(
            "INSERT INTO order_items(order_id, product_id, count, price_at_order) VALUES (?, 2, 1, 95)",
            (order_id,),
        )

        self.conn.commit()

    def role_id(self, role_name):
        return self.execute("SELECT id FROM roles WHERE role_name=?", (role_name,)).fetchone()[0]

    def log(self, login, action):
        self.execute("INSERT INTO logs(user_login, action) VALUES (?, ?)", (login, action))
        self.conn.commit()

    def authenticate(self, login, password):
        row = self.execute(
            """
            SELECT users.*, roles.role_name
            FROM users
            JOIN roles ON roles.id = users.role_id
            WHERE login=? AND password_hash=?
            """,
            (login, sha256_password(password)),
        ).fetchone()
        return row

    def register_client(self, login, password, full_name, phone):
        self.execute(
            """
            INSERT INTO users(login, password_hash, role_id, full_name, phone)
            VALUES (?, ?, ?, ?, ?)
            """,
            (login, sha256_password(password), self.role_id("client"), full_name, phone),
        )
        self.conn.commit()

    def products(self, role, search="", category="", ptype="", condition_id="", sort_by="name"):
        sql = """
            SELECT products.*,
                   STRING_AGG(growing_conditions.climate_zone || ', ' ||
                              growing_conditions.soil_type || ', ' ||
                              growing_conditions.sunlight || ', ' ||
                              growing_conditions.watering, '; ') AS conditions
            FROM products
            LEFT JOIN product_condition_link ON product_condition_link.product_id = products.id
            LEFT JOIN growing_conditions ON growing_conditions.id = product_condition_link.condition_id
        """
        params = []
        where = []

        if role in ("manager", "admin"):
            if search:
                where.append("(products.name LIKE ? OR products.article LIKE ?)")
                params.extend([f"%{search}%", f"%{search}%"])
            if category:
                where.append("products.category=?")
                params.append(category)
            if ptype:
                where.append("products.type=?")
                params.append(ptype)
            if condition_id:
                where.append(
                    """
                    products.id IN (
                        SELECT product_id FROM product_condition_link WHERE condition_id=?
                    )
                    """
                )
                params.append(condition_id)

        if where:
            sql += " WHERE " + " AND ".join(where)

        allowed_sort = {
            "name": "products.name",
            "price": "products.price",
            "created_at": "products.created_at DESC",
        }
        sql += " GROUP BY products.id ORDER BY " + allowed_sort.get(sort_by, "products.name")
        return self.execute(sql, params).fetchall()

    def all_categories(self):
        rows = self.execute("SELECT DISTINCT category FROM products ORDER BY category").fetchall()
        return [row[0] for row in rows]

    def conditions(self):
        return self.execute("SELECT * FROM growing_conditions ORDER BY id").fetchall()

    def users_by_role(self, role_name):
        return self.execute(
            """
            SELECT users.*
            FROM users
            JOIN roles ON roles.id = users.role_id
            WHERE roles.role_name=?
            ORDER BY full_name
            """,
            (role_name,),
        ).fetchall()

    def orders(self):
        return self.execute(
            """
            SELECT orders.*, users.full_name, users.login
            FROM orders
            JOIN users ON users.id = orders.user_id
            ORDER BY orders.id DESC
            """
        ).fetchall()

    def order_items(self, order_id):
        return self.execute(
            """
            SELECT order_items.*, products.article, products.name
            FROM order_items
            JOIN products ON products.id = order_items.product_id
            WHERE order_id=?
            """,
            (order_id,),
        ).fetchall()

    def product_by_id(self, product_id):
        return self.execute("SELECT * FROM products WHERE id=?", (product_id,)).fetchone()

    def save_product(self, data, condition_ids, product_id=None):
        if product_id:
            self.execute(
                """
                UPDATE products
                SET article=?, name=?, type=?, brand=?, price=?, quantity=?,
                    category=?, description=?, planting_season=?
                WHERE id=?
                """,
                (*data, product_id),
            )
            self.execute("DELETE FROM product_condition_link WHERE product_id=?", (product_id,))
        else:
            cur = self.execute(
                """
                INSERT INTO products(article, name, type, brand, price, quantity, category, description, planting_season)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                data,
            )
            product_id = cur.lastrowid

        for condition_id in condition_ids:
            self.execute(
                "INSERT INTO product_condition_link(product_id, condition_id) VALUES (?, ?)",
                (product_id, condition_id),
            )
        self.conn.commit()

    def delete_product(self, product_id):
        self.execute("DELETE FROM products WHERE id=?", (product_id,))
        self.conn.commit()

    def save_condition(self, data, condition_id=None):
        if condition_id:
            self.execute(
                """
                UPDATE growing_conditions
                SET climate_zone=?, soil_type=?, sunlight=?, watering=?
                WHERE id=?
                """,
                (*data, condition_id),
            )
        else:
            self.execute(
                """
                INSERT INTO growing_conditions(climate_zone, soil_type, sunlight, watering)
                VALUES (?, ?, ?, ?)
                """,
                data,
            )
        self.conn.commit()

    def delete_condition(self, condition_id):
        self.execute("DELETE FROM growing_conditions WHERE id=?", (condition_id,))
        self.conn.commit()

    def create_order(self, user_id, address, phone, items):
        total = sum(item["count"] * item["price"] for item in items)
        cur = self.execute(
            """
            INSERT INTO orders(user_id, status, total_amount, delivery_address, phone)
            VALUES (?, 'new', ?, ?, ?)
            """,
            (user_id, total, address, phone),
        )
        order_id = cur.lastrowid
        for item in items:
            self.execute(
                """
                INSERT INTO order_items(order_id, product_id, count, price_at_order)
                VALUES (?, ?, ?, ?)
                """,
                (order_id, item["product_id"], item["count"], item["price"]),
            )
        self.conn.commit()

    def update_order(self, order_id, status, address, phone):
        self.execute(
            """
            UPDATE orders
            SET status=?, delivery_address=?, phone=?
            WHERE id=?
            """,
            (status, address, phone, order_id),
        )
        self.conn.commit()

    def delete_order(self, order_id):
        self.execute("DELETE FROM orders WHERE id=?", (order_id,))
        self.conn.commit()

    def stats(self):
        return {
            "products": self.execute("SELECT COUNT(*) FROM products").fetchone()[0],
            "orders": self.execute("SELECT COUNT(*) FROM orders").fetchone()[0],
            "users": self.execute("SELECT COUNT(*) FROM users").fetchone()[0],
            "sum": self.execute("SELECT COALESCE(SUM(total_amount), 0) FROM orders").fetchone()[0],
        }

    def logs(self):
        return self.execute("SELECT * FROM logs ORDER BY id DESC LIMIT 30").fetchall()
