import tkinter as tk
from tkinter import messagebox, ttk

try:
    from PIL import Image, ImageTk
except Exception:
    Image = None
    ImageTk = None

from admin_panel import AdminFrame
from catalog import CatalogFrame
from config import BG, BROWN, DARK, GREEN, LOGO_PATH, LOGO_PNG_PATH
from db import Database
from orders import OrdersFrame
from registration import open_register_window

class GreenGardenApp:
    """Главное окно: вход, выход и подключение вкладок по роли пользователя."""
    def __init__(self, root):
        self.root = root
        try:
            self.db = Database()
        except Exception as exc:
            messagebox.showerror(
                "Ошибка PostgreSQL",
                "Не удалось подключиться к базе PostgreSQL.\n"
                "Проверьте настройки PG_HOST, PG_PORT, PG_DATABASE, PG_USER, PG_PASSWORD.\n\n"
                f"{exc}",
            )
            self.root.destroy()
            return
        self.user = None
        self.logo_image = None

        self.root.title("ООО «Зелёный Сад»")
        self.root.geometry("1120x720")
        self.root.minsize(980, 620)
        self.root.configure(bg=BG)
        self.setup_style()
        self.show_login()

    def setup_style(self):
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("TFrame", background=BG)
        style.configure("Card.TFrame", background="white", relief="flat")
        style.configure("TLabel", background=BG, foreground=DARK, font=("Segoe UI", 10))
        style.configure("Title.TLabel", background=BG, foreground=DARK, font=("Segoe UI", 22, "bold"))
        style.configure("Header.TLabel", background=BG, foreground=GREEN, font=("Segoe UI", 18, "bold"))
        style.configure("TButton", padding=7, font=("Segoe UI", 10))
        style.configure("Accent.TButton", background=GREEN, foreground="white")
        style.configure("Treeview", rowheight=28, font=("Segoe UI", 10))
        style.configure("Treeview.Heading", font=("Segoe UI", 10, "bold"))
        style.map("Accent.TButton", background=[("active", "#16A34A")])

    def clear(self):
        for widget in self.root.winfo_children():
            widget.destroy()

    def load_logo(self, parent, size=(260, 145)):
        if Image and ImageTk and LOGO_PATH.exists():
            image = Image.open(LOGO_PATH)
            image.thumbnail(size)
            self.logo_image = ImageTk.PhotoImage(image)
            return ttk.Label(parent, image=self.logo_image, background=BG)
        if LOGO_PNG_PATH.exists():
            self.logo_image = tk.PhotoImage(file=str(LOGO_PNG_PATH))
            self.logo_image = self.logo_image.subsample(3, 3)
            return ttk.Label(parent, image=self.logo_image, background=BG)
        return ttk.Label(parent, text="Зелёный Сад", style="Title.TLabel")

    def show_login(self):
        self.clear()
        wrapper = ttk.Frame(self.root, padding=30)
        wrapper.pack(fill="both", expand=True)

        left = ttk.Frame(wrapper)
        left.pack(side="left", fill="both", expand=True, padx=(0, 35))
        self.load_logo(left).pack(pady=(45, 20))
        ttk.Label(left, text="Природа в вашем доме", style="Header.TLabel").pack()
        ttk.Label(
            left,
            text="Информационная система магазина растений и семян",
            font=("Segoe UI", 12),
        ).pack(pady=10)

        form = ttk.Frame(wrapper, padding=28, style="Card.TFrame")
        form.pack(side="right", fill="y", padx=(10, 0))
        ttk.Label(form, text="Вход в систему", font=("Segoe UI", 20, "bold"), background="white").pack(pady=(10, 24))

        ttk.Label(form, text="Логин", background="white").pack(anchor="w")
        login_var = tk.StringVar(value="admin_garden")
        login_entry = ttk.Entry(form, textvariable=login_var, width=32)
        login_entry.pack(pady=(4, 14))

        ttk.Label(form, text="Пароль", background="white").pack(anchor="w")
        password_var = tk.StringVar(value="GardenAdmin2026!")
        password_entry = ttk.Entry(form, textvariable=password_var, show="*", width=32)
        password_entry.pack(pady=(4, 20))

        def do_login():
            login = login_var.get().strip()
            password = password_var.get()
            user = self.db.authenticate(login, password)
            if not user:
                messagebox.showerror("Ошибка", "Неверный логин или пароль")
                return
            self.user = dict(user)
            self.db.log(login, "Вход в систему")
            self.show_main()

        ttk.Button(form, text="Войти", style="Accent.TButton", command=do_login).pack(fill="x", pady=4)
        ttk.Button(form, text="Регистрация клиента", command=self.show_register).pack(fill="x", pady=4)
        ttk.Button(form, text="Войти как гость", command=self.login_as_guest).pack(fill="x", pady=4)

        ttk.Label(
            form,
            text="Тестовые роли: admin_garden / manager01 / client_ivanov",
            background="white",
            foreground=BROWN,
            wraplength=260,
        ).pack(pady=(24, 0))

        login_entry.focus()

    def login_as_guest(self):
        self.user = {
            "id": None,
            "login": "guest",
            "full_name": "Гость",
            "phone": "",
            "role_name": "guest",
        }
        self.show_main()

    def show_register(self):
        # Регистрация вынесена в отдельный файл registration.py.
        open_register_window(self.root, self.db)

    def show_main(self):
        self.clear()
        role = self.user["role_name"]

        header = ttk.Frame(self.root, padding=(18, 12))
        header.pack(fill="x")
        ttk.Label(header, text="ООО «Зелёный Сад»", style="Header.TLabel").pack(side="left")
        ttk.Label(
            header,
            text=f"{self.user['full_name']} | роль: {role}",
            font=("Segoe UI", 10, "bold"),
        ).pack(side="left", padx=20)
        ttk.Button(header, text="Выход", command=self.show_login).pack(side="right")

        notebook = ttk.Notebook(self.root)
        notebook.pack(fill="both", expand=True, padx=16, pady=(0, 16))

        catalog = CatalogFrame(notebook, self.db, self.user)
        notebook.add(catalog, text="Каталог товаров")

        # Права доступа по ролям: менеджер и админ видят заказы, клиент и гость - нет.
        if role in ("manager", "admin"):
            orders = OrdersFrame(notebook, self.db, self.user)
            notebook.add(orders, text="Заказы")

        # Администратор получает отдельную вкладку с CRUD и справочниками.
        if role == "admin":
            admin = AdminFrame(notebook, self.db, self.user)
            notebook.add(admin, text="Администрирование")
