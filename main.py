import tkinter as tk

from app import GreenGardenApp


def run():
    """Точка запуска. Этот файл можно запускать через Run Current File."""
    try:
        root = tk.Tk()
        GreenGardenApp(root)
        root.mainloop()
    except tk.TclError as exc:
        print("Не удалось открыть окно Tkinter.")
        print("Проверьте, что Python установлен с компонентом Tcl/Tk.")
        print(f"Техническая ошибка: {exc}")


if __name__ == "__main__":
    run()
