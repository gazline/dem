import random
import tkinter as tk
from tkinter import messagebox, ttk

from config import BG
from db import DatabaseError


def open_register_window(root, db):
    """Окно регистрации клиента. Новому пользователю всегда назначается роль client."""
    win = tk.Toplevel(root)
    win.title("Регистрация клиента")
    win.geometry("380x420")
    win.resizable(False, False)
    win.configure(bg=BG)

    captcha_a = random.randint(2, 9)
    captcha_b = random.randint(2, 9)

    frame = ttk.Frame(win, padding=24)
    frame.pack(fill="both", expand=True)
    ttk.Label(frame, text="Новый клиент", font=("Segoe UI", 18, "bold")).pack(pady=(0, 18))

    fields = {}
    for label, key, show in [
        ("ФИО", "full_name", ""),
        ("Телефон", "phone", ""),
        ("Логин", "login", ""),
        ("Пароль", "password", "*"),
    ]:
        ttk.Label(frame, text=label).pack(anchor="w")
        var = tk.StringVar()
        fields[key] = var
        ttk.Entry(frame, textvariable=var, show=show, width=36).pack(pady=(3, 10))

    ttk.Label(frame, text=f"CAPTCHA: {captcha_a} + {captcha_b} = ?").pack(anchor="w")
    captcha_var = tk.StringVar()
    ttk.Entry(frame, textvariable=captcha_var, width=36).pack(pady=(3, 16))

    def save():
        if not all(v.get().strip() for v in fields.values()):
            messagebox.showwarning("Проверка", "Заполните все поля")
            return
        try:
            if int(captcha_var.get()) != captcha_a + captcha_b:
                messagebox.showerror("CAPTCHA", "Ответ CAPTCHA неверный")
                return
        except ValueError:
            messagebox.showerror("CAPTCHA", "Введите число")
            return
        try:
            db.register_client(
                fields["login"].get().strip(),
                fields["password"].get(),
                fields["full_name"].get().strip(),
                fields["phone"].get().strip(),
            )
        except DatabaseError:
            db.rollback()
            messagebox.showerror("Ошибка", "Такой логин уже занят")
            return

        db.log(fields["login"].get().strip(), "Регистрация клиента")
        messagebox.showinfo("Готово", "Клиент зарегистрирован. Теперь можно войти.")
        win.destroy()

    ttk.Button(frame, text="Зарегистрироваться", style="Accent.TButton", command=save).pack(fill="x")
