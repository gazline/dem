import tkinter as tk
from tkinter import messagebox, ttk

from config import BG, TYPE_NAMES
from db import DatabaseError

class CatalogFrame(ttk.Frame):
    """Каталог товаров. Для гостя/клиента только просмотр, для менеджера/админа фильтры."""
    def __init__(self, parent, db, user):
        super().__init__(parent, padding=14)
        self.db = db
        self.user = user
        self.selected_product_id = None
        self.search_var = tk.StringVar()
        self.category_var = tk.StringVar()
        self.type_var = tk.StringVar()
        self.condition_var = tk.StringVar()
        self.sort_var = tk.StringVar(value="name")
        self.condition_map = {}
        self.build()
        self.refresh()

    def build(self):
        role = self.user["role_name"]

        top = ttk.Frame(self)
        top.pack(fill="x", pady=(0, 10))
        ttk.Label(top, text="Каталог растений и семян", font=("Segoe UI", 16, "bold")).pack(side="left")

        # По заданию гость и клиент только смотрят каталог.
        # Поиск, сортировка и фильтры показываются только менеджеру и администратору.
        if role in ("manager", "admin"):
            filter_frame = ttk.Frame(self)
            filter_frame.pack(fill="x", pady=(0, 10))

            ttk.Label(filter_frame, text="Поиск").grid(row=0, column=0, sticky="w")
            ttk.Entry(filter_frame, textvariable=self.search_var, width=24).grid(row=1, column=0, padx=(0, 8), sticky="we")

            ttk.Label(filter_frame, text="Категория").grid(row=0, column=1, sticky="w")
            categories = [""] + self.db.all_categories()
            ttk.Combobox(filter_frame, textvariable=self.category_var, values=categories, state="readonly", width=18).grid(row=1, column=1, padx=8)

            ttk.Label(filter_frame, text="Тип").grid(row=0, column=2, sticky="w")
            types = [""] + list(TYPE_NAMES.keys())
            ttk.Combobox(filter_frame, textvariable=self.type_var, values=types, state="readonly", width=14).grid(row=1, column=2, padx=8)

            ttk.Label(filter_frame, text="Условия").grid(row=0, column=3, sticky="w")
            condition_values = [""]
            self.condition_map = {"": ""}
            for row in self.db.conditions():
                title = f"{row['id']}: {row['climate_zone']}, {row['sunlight']}, полив {row['watering']}"
                condition_values.append(title)
                self.condition_map[title] = row["id"]
            ttk.Combobox(filter_frame, textvariable=self.condition_var, values=condition_values, state="readonly", width=28).grid(row=1, column=3, padx=8)

            ttk.Label(filter_frame, text="Сортировка").grid(row=0, column=4, sticky="w")
            ttk.Combobox(
                filter_frame,
                textvariable=self.sort_var,
                values=["name", "price", "created_at"],
                state="readonly",
                width=14,
            ).grid(row=1, column=4, padx=8)

            ttk.Button(filter_frame, text="Применить", command=self.refresh).grid(row=1, column=5, padx=(8, 0))

        columns = ("article", "name", "type", "category", "brand", "price", "quantity", "season")
        self.tree = ttk.Treeview(self, columns=columns, show="headings", height=14)
        headings = {
            "article": "Артикул",
            "name": "Название",
            "type": "Тип",
            "category": "Категория",
            "brand": "Поставщик",
            "price": "Цена",
            "quantity": "Остаток",
            "season": "Сезон",
        }
        widths = {
            "article": 95,
            "name": 190,
            "type": 100,
            "category": 110,
            "brand": 120,
            "price": 80,
            "quantity": 80,
            "season": 110,
        }
        for col in columns:
            self.tree.heading(col, text=headings[col])
            self.tree.column(col, width=widths[col], anchor="w")
        self.tree.pack(fill="both", expand=True)
        self.tree.bind("<<TreeviewSelect>>", self.on_select)

        bottom = ttk.Frame(self, padding=(0, 10))
        bottom.pack(fill="x")
        self.info = tk.Text(bottom, height=5, wrap="word", bg="white", relief="solid", borderwidth=1)
        self.info.pack(side="left", fill="both", expand=True)

        if role == "admin":
            buttons = ttk.Frame(bottom)
            buttons.pack(side="right", fill="y", padx=(12, 0))
            ttk.Button(buttons, text="Добавить", command=self.add_product).pack(fill="x", pady=2)
            ttk.Button(buttons, text="Изменить", command=self.edit_product).pack(fill="x", pady=2)
            ttk.Button(buttons, text="Удалить", command=self.delete_product).pack(fill="x", pady=2)

    def refresh(self):
        # Все параметры фильтрации уходят в db.products().
        # Если нужно добавить новый фильтр, обычно надо менять этот метод и SQL в db.py.
        role = self.user["role_name"]
        condition_id = self.condition_map.get(self.condition_var.get(), "")
        rows = self.db.products(
            role,
            self.search_var.get().strip(),
            self.category_var.get(),
            self.type_var.get(),
            condition_id,
            self.sort_var.get(),
        )
        self.tree.delete(*self.tree.get_children())
        self.products_by_iid = {}
        for row in rows:
            iid = str(row["id"])
            self.products_by_iid[iid] = dict(row)
            self.tree.insert(
                "",
                "end",
                iid=iid,
                values=(
                    row["article"],
                    row["name"],
                    TYPE_NAMES.get(row["type"], row["type"]),
                    row["category"],
                    row["brand"],
                    f"{row['price']:.2f}",
                    row["quantity"],
                    row["planting_season"] or "",
                ),
            )
        self.info.delete("1.0", "end")

    def on_select(self, _event=None):
        selected = self.tree.selection()
        if not selected:
            self.selected_product_id = None
            return
        self.selected_product_id = int(selected[0])
        row = self.products_by_iid[selected[0]]
        text = (
            f"{row['name']} ({row['article']})\n"
            f"Описание: {row['description'] or 'нет описания'}\n"
            f"Условия выращивания: {row['conditions'] or 'не указаны'}"
        )
        self.info.delete("1.0", "end")
        self.info.insert("1.0", text)

    def add_product(self):
        ProductDialog(self, self.db, on_save=self.refresh)

    def edit_product(self):
        if not self.selected_product_id:
            messagebox.showwarning("Выбор", "Выберите товар")
            return
        ProductDialog(self, self.db, product_id=self.selected_product_id, on_save=self.refresh)

    def delete_product(self):
        if not self.selected_product_id:
            messagebox.showwarning("Выбор", "Выберите товар")
            return
        if messagebox.askyesno("Удаление", "Удалить выбранный товар?"):
            self.db.delete_product(self.selected_product_id)
            self.db.log(self.user["login"], "Удалён товар")
            self.refresh()


class ProductDialog(tk.Toplevel):
    """Форма добавления и редактирования товара для администратора."""
    def __init__(self, parent, db, product_id=None, on_save=None):
        super().__init__(parent)
        self.db = db
        self.product_id = product_id
        self.on_save = on_save
        self.title("Товар")
        self.geometry("520x600")
        self.resizable(False, False)
        self.configure(bg=BG)
        self.vars = {}
        self.condition_vars = {}
        self.build()
        if product_id:
            self.load_product()

    def build(self):
        frame = ttk.Frame(self, padding=18)
        frame.pack(fill="both", expand=True)

        fields = [
            ("Артикул", "article"),
            ("Название", "name"),
            ("Поставщик", "brand"),
            ("Цена", "price"),
            ("Остаток", "quantity"),
            ("Категория", "category"),
            ("Сезон посадки", "season"),
        ]
        for row, (label, key) in enumerate(fields):
            ttk.Label(frame, text=label).grid(row=row, column=0, sticky="w", pady=4)
            var = tk.StringVar()
            self.vars[key] = var
            ttk.Entry(frame, textvariable=var, width=36).grid(row=row, column=1, sticky="we", pady=4)

        ttk.Label(frame, text="Тип").grid(row=7, column=0, sticky="w", pady=4)
        self.vars["type"] = tk.StringVar(value="seed")
        ttk.Combobox(frame, textvariable=self.vars["type"], values=list(TYPE_NAMES.keys()), state="readonly", width=33).grid(row=7, column=1, sticky="we", pady=4)

        ttk.Label(frame, text="Описание").grid(row=8, column=0, sticky="nw", pady=4)
        self.description = tk.Text(frame, width=34, height=5, wrap="word")
        self.description.grid(row=8, column=1, sticky="we", pady=4)

        ttk.Label(frame, text="Условия").grid(row=9, column=0, sticky="nw", pady=4)
        cond_box = ttk.Frame(frame)
        cond_box.grid(row=9, column=1, sticky="we", pady=4)
        for row in self.db.conditions():
            var = tk.BooleanVar()
            self.condition_vars[row["id"]] = var
            text = f"{row['climate_zone']}, {row['soil_type']}, {row['sunlight']}, {row['watering']}"
            ttk.Checkbutton(cond_box, text=text, variable=var).pack(anchor="w")

        ttk.Button(frame, text="Сохранить", style="Accent.TButton", command=self.save).grid(row=10, column=1, sticky="e", pady=16)

    def load_product(self):
        row = self.db.product_by_id(self.product_id)
        values = {
            "article": row["article"],
            "name": row["name"],
            "brand": row["brand"],
            "price": str(row["price"]),
            "quantity": str(row["quantity"]),
            "category": row["category"],
            "season": row["planting_season"] or "",
            "type": row["type"],
        }
        for key, value in values.items():
            self.vars[key].set(value)
        self.description.insert("1.0", row["description"] or "")
        linked = self.db.execute(
            "SELECT condition_id FROM product_condition_link WHERE product_id=?",
            (self.product_id,),
        ).fetchall()
        for row in linked:
            if row["condition_id"] in self.condition_vars:
                self.condition_vars[row["condition_id"]].set(True)

    def save(self):
        try:
            data = (
                self.vars["article"].get().strip(),
                self.vars["name"].get().strip(),
                self.vars["type"].get(),
                self.vars["brand"].get().strip(),
                float(self.vars["price"].get().replace(",", ".")),
                int(self.vars["quantity"].get()),
                self.vars["category"].get().strip(),
                self.description.get("1.0", "end").strip(),
                self.vars["season"].get().strip(),
            )
        except ValueError:
            messagebox.showerror("Ошибка", "Цена и остаток должны быть числами")
            return

        if not all(str(item).strip() for item in data[:4]) or not data[6]:
            messagebox.showwarning("Проверка", "Заполните основные поля товара")
            return

        condition_ids = [cid for cid, var in self.condition_vars.items() if var.get()]
        try:
            self.db.save_product(data, condition_ids, self.product_id)
        except DatabaseError as exc:
            self.db.rollback()
            messagebox.showerror("Ошибка БД", f"Не удалось сохранить товар: {exc}")
            return
        if self.on_save:
            self.on_save()
        self.destroy()
