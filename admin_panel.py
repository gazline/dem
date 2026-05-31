import tkinter as tk
from tkinter import messagebox, ttk

from config import BG

class AdminFrame(ttk.Frame):
    """Админская вкладка: справочник условий, статистика и журнал действий."""
    def __init__(self, parent, db, user):
        super().__init__(parent, padding=14)
        self.db = db
        self.user = user
        self.selected_condition_id = None
        self.build()
        self.refresh_conditions()
        self.refresh_stats()

    def build(self):
        ttk.Label(self, text="Администрирование", font=("Segoe UI", 16, "bold")).pack(anchor="w", pady=(0, 10))

        top = ttk.Frame(self)
        top.pack(fill="both", expand=True)

        left = ttk.Frame(top)
        left.pack(side="left", fill="both", expand=True, padx=(0, 12))
        ttk.Label(left, text="Справочник условий выращивания", font=("Segoe UI", 12, "bold")).pack(anchor="w")

        columns = ("id", "climate", "soil", "sun", "watering")
        self.tree = ttk.Treeview(left, columns=columns, show="headings", height=10)
        for col, text, width in [
            ("id", "ID", 50),
            ("climate", "Зона", 120),
            ("soil", "Почва", 120),
            ("sun", "Свет", 110),
            ("watering", "Полив", 110),
        ]:
            self.tree.heading(col, text=text)
            self.tree.column(col, width=width, anchor="w")
        self.tree.pack(fill="both", expand=True, pady=6)
        self.tree.bind("<<TreeviewSelect>>", self.on_condition_select)

        btns = ttk.Frame(left)
        btns.pack(anchor="e")
        ttk.Button(btns, text="Добавить", command=self.add_condition).pack(side="left", padx=2)
        ttk.Button(btns, text="Изменить", command=self.edit_condition).pack(side="left", padx=2)
        ttk.Button(btns, text="Удалить", command=self.delete_condition).pack(side="left", padx=2)

        right = ttk.Frame(top)
        right.pack(side="right", fill="both", expand=True)
        ttk.Label(right, text="Статистика", font=("Segoe UI", 12, "bold")).pack(anchor="w")
        self.stats_label = ttk.Label(right, text="", font=("Segoe UI", 11))
        self.stats_label.pack(anchor="w", pady=(6, 16))

        ttk.Label(right, text="Последние действия", font=("Segoe UI", 12, "bold")).pack(anchor="w")
        self.logs_text = tk.Text(right, height=14, wrap="word", bg="white", relief="solid", borderwidth=1)
        self.logs_text.pack(fill="both", expand=True, pady=6)

    def refresh_conditions(self):
        self.tree.delete(*self.tree.get_children())
        for row in self.db.conditions():
            self.tree.insert(
                "",
                "end",
                iid=str(row["id"]),
                values=(row["id"], row["climate_zone"], row["soil_type"], row["sunlight"], row["watering"]),
            )

    def refresh_stats(self):
        # Простая статистика для демонстрации админского модуля.
        # При необходимости сюда можно добавить выручку по датам или популярные товары.
        stats = self.db.stats()
        self.stats_label.config(
            text=(
                f"Товаров: {stats['products']}\n"
                f"Заказов: {stats['orders']}\n"
                f"Пользователей: {stats['users']}\n"
                f"Сумма заказов: {stats['sum']:.2f} руб."
            )
        )
        self.logs_text.delete("1.0", "end")
        lines = [f"{row['created_at']} | {row['user_login'] or '-'} | {row['action']}" for row in self.db.logs()]
        self.logs_text.insert("1.0", "\n".join(lines))

    def on_condition_select(self, _event=None):
        selected = self.tree.selection()
        self.selected_condition_id = int(selected[0]) if selected else None

    def add_condition(self):
        ConditionDialog(self, self.db, on_save=self.after_condition_save)

    def edit_condition(self):
        if not self.selected_condition_id:
            messagebox.showwarning("Выбор", "Выберите условие")
            return
        ConditionDialog(self, self.db, self.selected_condition_id, self.after_condition_save)

    def delete_condition(self):
        if not self.selected_condition_id:
            messagebox.showwarning("Выбор", "Выберите условие")
            return
        if messagebox.askyesno("Удаление", "Удалить условие выращивания?"):
            self.db.delete_condition(self.selected_condition_id)
            self.db.log(self.user["login"], "Удалено условие выращивания")
            self.after_condition_save()

    def after_condition_save(self):
        self.refresh_conditions()
        self.refresh_stats()


class ConditionDialog(tk.Toplevel):
    """Форма справочника условий выращивания."""
    def __init__(self, parent, db, condition_id=None, on_save=None):
        super().__init__(parent)
        self.db = db
        self.condition_id = condition_id
        self.on_save = on_save
        self.title("Условия выращивания")
        self.geometry("360x280")
        self.configure(bg=BG)
        self.vars = {}

        frame = ttk.Frame(self, padding=18)
        frame.pack(fill="both", expand=True)
        for label, key in [
            ("Климатическая зона", "climate_zone"),
            ("Тип почвы", "soil_type"),
            ("Освещённость", "sunlight"),
            ("Полив", "watering"),
        ]:
            ttk.Label(frame, text=label).pack(anchor="w")
            var = tk.StringVar()
            self.vars[key] = var
            ttk.Entry(frame, textvariable=var).pack(fill="x", pady=(3, 9))

        if condition_id:
            row = self.db.execute("SELECT * FROM growing_conditions WHERE id=?", (condition_id,)).fetchone()
            for key in self.vars:
                self.vars[key].set(row[key])

        ttk.Button(frame, text="Сохранить", style="Accent.TButton", command=self.save).pack(anchor="e", pady=10)

    def save(self):
        data = tuple(var.get().strip() for var in self.vars.values())
        if not all(data):
            messagebox.showwarning("Проверка", "Заполните все поля")
            return
        self.db.save_condition(data, self.condition_id)
        if self.on_save:
            self.on_save()
        self.destroy()
