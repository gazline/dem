import tkinter as tk
from tkinter import messagebox, ttk

from config import BG, STATUS_NAMES

class OrdersFrame(ttk.Frame):
    """Вкладка заказов: менеджер смотрит, администратор управляет."""
    def __init__(self, parent, db, user):
        super().__init__(parent, padding=14)
        self.db = db
        self.user = user
        self.selected_order_id = None
        self.build()
        self.refresh()

    def build(self):
        top = ttk.Frame(self)
        top.pack(fill="x", pady=(0, 10))
        ttk.Label(top, text="Заказы клиентов", font=("Segoe UI", 16, "bold")).pack(side="left")

        # Менеджер только просматривает заказы.
        # Администратор может создавать, редактировать и удалять.
        if self.user["role_name"] == "admin":
            ttk.Button(top, text="Создать заказ", command=self.create_order).pack(side="right", padx=3)
            ttk.Button(top, text="Изменить", command=self.edit_order).pack(side="right", padx=3)
            ttk.Button(top, text="Удалить", command=self.delete_order).pack(side="right", padx=3)

        columns = ("id", "client", "date", "status", "total", "address", "phone")
        self.tree = ttk.Treeview(self, columns=columns, show="headings", height=13)
        for col, text, width in [
            ("id", "№", 60),
            ("client", "Клиент", 170),
            ("date", "Дата", 145),
            ("status", "Статус", 130),
            ("total", "Сумма", 90),
            ("address", "Адрес", 260),
            ("phone", "Телефон", 130),
        ]:
            self.tree.heading(col, text=text)
            self.tree.column(col, width=width, anchor="w")
        self.tree.pack(fill="both", expand=True)
        self.tree.bind("<<TreeviewSelect>>", self.on_select)

        ttk.Label(self, text="Состав заказа", font=("Segoe UI", 11, "bold")).pack(anchor="w", pady=(10, 3))
        self.items = tk.Text(self, height=6, wrap="word", bg="white", relief="solid", borderwidth=1)
        self.items.pack(fill="x")

    def refresh(self):
        self.tree.delete(*self.tree.get_children())
        for row in self.db.orders():
            self.tree.insert(
                "",
                "end",
                iid=str(row["id"]),
                values=(
                    row["id"],
                    row["full_name"],
                    row["order_date"],
                    STATUS_NAMES.get(row["status"], row["status"]),
                    f"{row['total_amount']:.2f}",
                    row["delivery_address"],
                    row["phone"],
                ),
            )
        self.items.delete("1.0", "end")

    def on_select(self, _event=None):
        selected = self.tree.selection()
        if not selected:
            self.selected_order_id = None
            return
        self.selected_order_id = int(selected[0])
        rows = self.db.order_items(self.selected_order_id)
        lines = []
        for row in rows:
            total = row["count"] * row["price_at_order"]
            lines.append(f"{row['article']} - {row['name']}: {row['count']} шт. x {row['price_at_order']:.2f} = {total:.2f} руб.")
        self.items.delete("1.0", "end")
        self.items.insert("1.0", "\n".join(lines))

    def create_order(self):
        OrderDialog(self, self.db, on_save=self.refresh)

    def edit_order(self):
        if not self.selected_order_id:
            messagebox.showwarning("Выбор", "Выберите заказ")
            return
        OrderEditDialog(self, self.db, self.selected_order_id, self.refresh)

    def delete_order(self):
        if not self.selected_order_id:
            messagebox.showwarning("Выбор", "Выберите заказ")
            return
        if messagebox.askyesno("Удаление", "Удалить выбранный заказ?"):
            self.db.delete_order(self.selected_order_id)
            self.db.log(self.user["login"], "Удалён заказ")
            self.refresh()


class OrderDialog(tk.Toplevel):
    """Создание заказа с фиксацией цены товара на момент покупки."""
    def __init__(self, parent, db, on_save=None):
        super().__init__(parent)
        self.db = db
        self.on_save = on_save
        self.items = []
        self.client_map = {}
        self.product_map = {}
        self.title("Создание заказа")
        self.geometry("560x560")
        self.configure(bg=BG)
        self.build()

    def build(self):
        frame = ttk.Frame(self, padding=18)
        frame.pack(fill="both", expand=True)

        ttk.Label(frame, text="Клиент").grid(row=0, column=0, sticky="w", pady=4)
        self.client_var = tk.StringVar()
        clients = []
        for row in self.db.users_by_role("client"):
            label = f"{row['id']}: {row['full_name']} ({row['login']})"
            self.client_map[label] = row["id"]
            clients.append(label)
        ttk.Combobox(frame, textvariable=self.client_var, values=clients, state="readonly", width=43).grid(row=0, column=1, sticky="we", pady=4)

        ttk.Label(frame, text="Адрес").grid(row=1, column=0, sticky="w", pady=4)
        self.address_var = tk.StringVar()
        ttk.Entry(frame, textvariable=self.address_var, width=46).grid(row=1, column=1, sticky="we", pady=4)

        ttk.Label(frame, text="Телефон").grid(row=2, column=0, sticky="w", pady=4)
        self.phone_var = tk.StringVar()
        ttk.Entry(frame, textvariable=self.phone_var, width=46).grid(row=2, column=1, sticky="we", pady=4)

        ttk.Separator(frame).grid(row=3, column=0, columnspan=2, sticky="we", pady=12)

        ttk.Label(frame, text="Товар").grid(row=4, column=0, sticky="w", pady=4)
        self.product_var = tk.StringVar()
        products = []
        for row in self.db.products("admin"):
            label = f"{row['id']}: {row['article']} - {row['name']} ({row['price']:.2f})"
            self.product_map[label] = dict(row)
            products.append(label)
        ttk.Combobox(frame, textvariable=self.product_var, values=products, state="readonly", width=43).grid(row=4, column=1, sticky="we", pady=4)

        ttk.Label(frame, text="Количество").grid(row=5, column=0, sticky="w", pady=4)
        self.count_var = tk.StringVar(value="1")
        ttk.Entry(frame, textvariable=self.count_var, width=12).grid(row=5, column=1, sticky="w", pady=4)
        ttk.Button(frame, text="Добавить позицию", command=self.add_item).grid(row=6, column=1, sticky="w", pady=5)

        self.listbox = tk.Listbox(frame, height=9)
        self.listbox.grid(row=7, column=0, columnspan=2, sticky="nsew", pady=8)

        ttk.Button(frame, text="Сохранить заказ", style="Accent.TButton", command=self.save).grid(row=8, column=1, sticky="e", pady=12)

    def add_item(self):
        # Цена берется из товара сейчас и сохраняется в order_items как price_at_order.
        # Поэтому будущие изменения цены товара не ломают старые заказы.
        product = self.product_map.get(self.product_var.get())
        if not product:
            messagebox.showwarning("Проверка", "Выберите товар")
            return
        try:
            count = int(self.count_var.get())
            if count <= 0:
                raise ValueError
        except ValueError:
            messagebox.showerror("Ошибка", "Количество должно быть больше 0")
            return

        item = {"product_id": product["id"], "name": product["name"], "count": count, "price": product["price"]}
        self.items.append(item)
        self.listbox.insert("end", f"{product['name']} - {count} шт. x {product['price']:.2f}")

    def save(self):
        user_id = self.client_map.get(self.client_var.get())
        if not user_id or not self.address_var.get().strip() or not self.phone_var.get().strip():
            messagebox.showwarning("Проверка", "Заполните клиента, адрес и телефон")
            return
        if not self.items:
            messagebox.showwarning("Проверка", "Добавьте хотя бы один товар")
            return
        self.db.create_order(user_id, self.address_var.get().strip(), self.phone_var.get().strip(), self.items)
        if self.on_save:
            self.on_save()
        self.destroy()


class OrderEditDialog(tk.Toplevel):
    """Изменение статуса, адреса и телефона заказа."""
    def __init__(self, parent, db, order_id, on_save):
        super().__init__(parent)
        self.db = db
        self.order_id = order_id
        self.on_save = on_save
        self.title("Изменение заказа")
        self.geometry("420x260")
        self.configure(bg=BG)
        row = self.db.execute("SELECT * FROM orders WHERE id=?", (order_id,)).fetchone()

        frame = ttk.Frame(self, padding=18)
        frame.pack(fill="both", expand=True)
        ttk.Label(frame, text=f"Заказ №{order_id}", font=("Segoe UI", 15, "bold")).pack(anchor="w", pady=(0, 12))

        self.status_var = tk.StringVar(value=row["status"])
        self.address_var = tk.StringVar(value=row["delivery_address"])
        self.phone_var = tk.StringVar(value=row["phone"])

        ttk.Label(frame, text="Статус").pack(anchor="w")
        ttk.Combobox(frame, textvariable=self.status_var, values=list(STATUS_NAMES.keys()), state="readonly").pack(fill="x", pady=(3, 8))
        ttk.Label(frame, text="Адрес").pack(anchor="w")
        ttk.Entry(frame, textvariable=self.address_var).pack(fill="x", pady=(3, 8))
        ttk.Label(frame, text="Телефон").pack(anchor="w")
        ttk.Entry(frame, textvariable=self.phone_var).pack(fill="x", pady=(3, 12))
        ttk.Button(frame, text="Сохранить", style="Accent.TButton", command=self.save).pack(anchor="e")

    def save(self):
        self.db.update_order(
            self.order_id,
            self.status_var.get(),
            self.address_var.get().strip(),
            self.phone_var.get().strip(),
        )
        self.on_save()
        self.destroy()
