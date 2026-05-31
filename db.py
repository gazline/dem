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
    """Возвращает SHA-256 хеш пароля для хранения в таблице users."""
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


class QueryResult:
    """Маленькая обертка, чтобы в коде было удобно получать fetchone/fetchall и lastrowid."""

    def __init__(self, cursor, lastrowid=None):
        self.cursor = cursor
        self.lastrowid = lastrowid

    def fetchone(self):
        """Возвращает одну строку результата SQL-запроса."""
        return self.cursor.fetchone()

    def fetchall(self):
        """Возвращает все строки результата SQL-запроса."""
        return self.cursor.fetchall()


class Database:
    """Все запросы к PostgreSQL собраны здесь, чтобы интерфейс не смешивался с SQL."""

    def __init__(self):
        """Открывает подключение к PostgreSQL и создает таблицы, если их еще нет."""
        if psycopg2 is None:
            raise RuntimeError("Не установлен драйвер PostgreSQL. Выполните: pip install psycopg2")

        self.conn = psycopg2.connect(
            host=PG_HOST,
            port=PG_PORT,
            dbname=PG_DATABASE,
            user=PG_USER,
            password=PG_PASSWORD,
            cursor_factory=DictCursor,
        )
        self.create_tables()
        self.ensure_roles()

    def execute(self, sql, params=None):
        """Выполняет SQL-запрос и автоматически меняет ? на %s для PostgreSQL."""
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
        """Выполняет несколько SQL-команд, разделенных точкой с запятой."""
        for statement in script.split(";"):
            statement = statement.strip()
            if statement:
                self.execute(statement)

    def rollback(self):
        """Откатывает неудачную операцию, чтобы подключение снова можно было использовать."""
        self.conn.rollback()

    def create_tables(self):
        """Создает таблицы проекта. Данные не добавляет и не очищает."""
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
                role_id INTEGER NOT NULL REFERENCES roles(id),
                full_name TEXT NOT NULL,
                phone TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
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
                product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
                condition_id INTEGER NOT NULL REFERENCES growing_conditions(id) ON DELETE CASCADE,
                PRIMARY KEY (product_id, condition_id)
            );

            CREATE TABLE IF NOT EXISTS orders (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users(id),
                order_date TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                status TEXT NOT NULL DEFAULT 'new',
                total_amount NUMERIC(10,2) NOT NULL DEFAULT 0,
                delivery_address TEXT NOT NULL,
                phone TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS order_items (
                id SERIAL PRIMARY KEY,
                order_id INTEGER NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
                product_id INTEGER NOT NULL REFERENCES products(id),
                count INTEGER NOT NULL CHECK(count > 0),
                price_at_order NUMERIC(10,2) NOT NULL
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

    def ensure_roles(self):
        """Создает только роли. Остальные данные должны прийти из задания или вручную."""
        for role in ("guest", "client", "manager", "admin"):
            self.execute(
                "INSERT INTO roles(role_name) VALUES (?) ON CONFLICT (role_name) DO NOTHING",
                (role,),
            )
        self.conn.commit()

    def role_id(self, role_name):
        """Возвращает id роли по ее системному названию."""
        return self.execute("SELECT id FROM roles WHERE role_name=?", (role_name,)).fetchone()[0]

    def log(self, login, action):
        """Добавляет запись в журнал действий."""
        self.execute("INSERT INTO logs(user_login, action) VALUES (?, ?)", (login, action))
        self.conn.commit()

    def authenticate(self, login, password):
        """Проверяет логин и пароль, возвращает пользователя вместе с ролью."""
        return self.execute(
            """
            SELECT users.*, roles.role_name
            FROM users
            JOIN roles ON roles.id = users.role_id
            WHERE login=? AND password_hash=?
            """,
            (login, sha256_password(password)),
        ).fetchone()

    def register_client(self, login, password, full_name, phone):
        """Создает нового пользователя с ролью client."""
        self.execute(
            """
            INSERT INTO users(login, password_hash, role_id, full_name, phone)
            VALUES (?, ?, ?, ?, ?)
            """,
            (login, sha256_password(password), self.role_id("client"), full_name, phone),
        )
        self.conn.commit()

    def products(self, role, search="", category="", ptype="", condition_id="", sort_by="name"):
        """Возвращает товары. Для manager/admin применяет поиск, фильтры и сортировку."""
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
                where.append("(products.name ILIKE ? OR products.article ILIKE ?)")
                params.extend([f"%{search}%", f"%{search}%"])
            if category:
                where.append("products.category=?")
                params.append(category)
            if ptype:
                where.append("products.type=?")
                params.append(ptype)
            if condition_id:
                where.append("products.id IN (SELECT product_id FROM product_condition_link WHERE condition_id=?)")
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
        """Возвращает список категорий для выпадающего фильтра."""
        rows = self.execute("SELECT DISTINCT category FROM products ORDER BY category").fetchall()
        return [row[0] for row in rows]

    def conditions(self):
        """Возвращает справочник условий выращивания."""
        return self.execute("SELECT * FROM growing_conditions ORDER BY id").fetchall()

    def users_by_role(self, role_name):
        """Возвращает пользователей выбранной роли, например всех клиентов."""
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
        """Возвращает список заказов вместе с ФИО клиента."""
        return self.execute(
            """
            SELECT orders.*, users.full_name, users.login
            FROM orders
            JOIN users ON users.id = orders.user_id
            ORDER BY orders.id DESC
            """
        ).fetchall()

    def order_items(self, order_id):
        """Возвращает состав одного заказа."""
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
        """Возвращает один товар по id."""
        return self.execute("SELECT * FROM products WHERE id=?", (product_id,)).fetchone()

    def save_product(self, data, condition_ids, product_id=None):
        """Добавляет новый товар или обновляет существующий."""
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
        """Удаляет товар по id."""
        self.execute("DELETE FROM products WHERE id=?", (product_id,))
        self.conn.commit()

    def save_condition(self, data, condition_id=None):
        """Добавляет или редактирует условие выращивания."""
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
        """Удаляет условие выращивания."""
        self.execute("DELETE FROM growing_conditions WHERE id=?", (condition_id,))
        self.conn.commit()

    def create_order(self, user_id, address, phone, items):
        """Создает заказ и сохраняет цены товаров на момент покупки."""
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
        """Обновляет статус и контактные данные заказа."""
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
        """Удаляет заказ и его позиции."""
        self.execute("DELETE FROM orders WHERE id=?", (order_id,))
        self.conn.commit()

    def stats(self):
        """Возвращает простую статистику для админской вкладки."""
        return {
            "products": self.execute("SELECT COUNT(*) FROM products").fetchone()[0],
            "orders": self.execute("SELECT COUNT(*) FROM orders").fetchone()[0],
            "users": self.execute("SELECT COUNT(*) FROM users").fetchone()[0],
            "sum": self.execute("SELECT COALESCE(SUM(total_amount), 0) FROM orders").fetchone()[0],
        }

    def logs(self):
        """Возвращает последние записи журнала."""
        return self.execute("SELECT * FROM logs ORDER BY id DESC LIMIT 30").fetchall()
