
import csv
import hashlib
import os
import shutil
import sqlite3
from datetime import datetime, date
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

APP_TITLE = "Фриланс-биржа — учет заявок"
DB_FILE = "freelance_exchange.db"


def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


class Database:
    def __init__(self, path: str = DB_FILE):
        self.path = path
        self.conn = sqlite3.connect(self.path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.create_schema()
        self.seed_data()

    def execute(self, sql: str, params=(), commit: bool = False):
        cur = self.conn.execute(sql, params)
        if commit:
            self.conn.commit()
        return cur

    def query(self, sql: str, params=()):
        return self.execute(sql, params).fetchall()

    def create_schema(self):
        schema = """
        CREATE TABLE IF NOT EXISTS roles (
            role_id INTEGER PRIMARY KEY AUTOINCREMENT,
            role_name TEXT NOT NULL UNIQUE
        );

        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY AUTOINCREMENT,
            role_id INTEGER NOT NULL,
            full_name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            phone TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            is_active INTEGER DEFAULT 1,
            FOREIGN KEY (role_id) REFERENCES roles(role_id)
        );

        CREATE TABLE IF NOT EXISTS clients (
            client_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL UNIQUE,
            company_name TEXT,
            contact_info TEXT,
            FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS freelancers (
            freelancer_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL UNIQUE,
            specialization TEXT NOT NULL,
            portfolio_url TEXT,
            rating REAL DEFAULT 0 CHECK (rating >= 0 AND rating <= 5),
            FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS categories (
            category_id INTEGER PRIMARY KEY AUTOINCREMENT,
            category_name TEXT NOT NULL UNIQUE,
            description TEXT
        );

        CREATE TABLE IF NOT EXISTS requests (
            request_id INTEGER PRIMARY KEY AUTOINCREMENT,
            client_id INTEGER NOT NULL,
            category_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            description TEXT NOT NULL,
            budget REAL NOT NULL CHECK (budget > 0),
            deadline TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'Новая' CHECK (status IN ('Новая', 'В работе', 'Завершена', 'Отменена')),
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (client_id) REFERENCES clients(client_id),
            FOREIGN KEY (category_id) REFERENCES categories(category_id)
        );

        CREATE TABLE IF NOT EXISTS bids (
            bid_id INTEGER PRIMARY KEY AUTOINCREMENT,
            request_id INTEGER NOT NULL,
            freelancer_id INTEGER NOT NULL,
            bid_text TEXT NOT NULL,
            proposed_price REAL NOT NULL CHECK (proposed_price > 0),
            proposed_days INTEGER NOT NULL CHECK (proposed_days > 0),
            status TEXT NOT NULL DEFAULT 'На рассмотрении' CHECK (status IN ('На рассмотрении', 'Принят', 'Отклонен')),
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (request_id) REFERENCES requests(request_id) ON DELETE CASCADE,
            FOREIGN KEY (freelancer_id) REFERENCES freelancers(freelancer_id)
        );

        CREATE TABLE IF NOT EXISTS contracts (
            contract_id INTEGER PRIMARY KEY AUTOINCREMENT,
            request_id INTEGER NOT NULL UNIQUE,
            bid_id INTEGER NOT NULL UNIQUE,
            start_date TEXT NOT NULL,
            end_date TEXT NOT NULL,
            total_price REAL NOT NULL CHECK (total_price > 0),
            status TEXT NOT NULL DEFAULT 'Активен' CHECK (status IN ('Активен', 'Завершен', 'Расторгнут')),
            FOREIGN KEY (request_id) REFERENCES requests(request_id),
            FOREIGN KEY (bid_id) REFERENCES bids(bid_id)
        );

        CREATE TABLE IF NOT EXISTS payments (
            payment_id INTEGER PRIMARY KEY AUTOINCREMENT,
            contract_id INTEGER NOT NULL,
            amount REAL NOT NULL CHECK (amount > 0),
            payment_date TEXT NOT NULL,
            payment_method TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'Ожидается' CHECK (status IN ('Ожидается', 'Оплачен', 'Возврат')),
            FOREIGN KEY (contract_id) REFERENCES contracts(contract_id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS reviews (
            review_id INTEGER PRIMARY KEY AUTOINCREMENT,
            contract_id INTEGER NOT NULL UNIQUE,
            rating INTEGER NOT NULL CHECK (rating BETWEEN 1 AND 5),
            comment TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (contract_id) REFERENCES contracts(contract_id) ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
        CREATE INDEX IF NOT EXISTS idx_requests_status ON requests(status);
        CREATE INDEX IF NOT EXISTS idx_requests_category ON requests(category_id);
        CREATE INDEX IF NOT EXISTS idx_bids_request ON bids(request_id);
        CREATE INDEX IF NOT EXISTS idx_payments_status ON payments(status);
        CREATE INDEX IF NOT EXISTS idx_contracts_status ON contracts(status);
        """
        self.conn.executescript(schema)
        self.conn.commit()

    def seed_data(self):
        if self.query("SELECT COUNT(*) AS cnt FROM roles")[0]["cnt"] > 0:
            return

        password = hash_password("12345")
        script = """
        INSERT INTO roles (role_name) VALUES
        ('Администратор'),
        ('Заказчик'),
        ('Исполнитель'),
        ('Менеджер');

        INSERT INTO users (role_id, full_name, email, password_hash, phone) VALUES
        (1, 'Иван Петров', 'admin@mail.ru', ?, '+79000000001'),
        (2, 'Анна Смирнова', 'client1@mail.ru', ?, '+79000000002'),
        (2, 'Олег Иванов', 'client2@mail.ru', ?, '+79000000003'),
        (3, 'Мария Кузнецова', 'freelancer1@mail.ru', ?, '+79000000004'),
        (3, 'Дмитрий Соколов', 'freelancer2@mail.ru', ?, '+79000000005'),
        (4, 'Екатерина Орлова', 'manager@mail.ru', ?, '+79000000006');

        INSERT INTO clients (user_id, company_name, contact_info) VALUES
        (2, 'ООО Вектор', 'Заказчик веб-проектов'),
        (3, 'ИП Иванов', 'Заказчик дизайнерских услуг');

        INSERT INTO freelancers (user_id, specialization, portfolio_url, rating) VALUES
        (4, 'Веб-разработка', 'https://portfolio-web.ru', 4.80),
        (5, 'Графический дизайн', 'https://portfolio-design.ru', 4.60);

        INSERT INTO categories (category_name, description) VALUES
        ('Веб-разработка', 'Создание сайтов и веб-приложений'),
        ('Дизайн', 'Разработка логотипов, баннеров и макетов'),
        ('Копирайтинг', 'Написание текстов и статей'),
        ('Маркетинг', 'Продвижение и рекламные кампании');

        INSERT INTO requests (client_id, category_id, title, description, budget, deadline, status) VALUES
        (1, 1, 'Разработка сайта-визитки', 'Нужно создать адаптивный сайт для компании.', 35000, '2026-07-01', 'Новая'),
        (1, 2, 'Дизайн логотипа', 'Требуется современный логотип для бренда.', 12000, '2026-06-25', 'Новая'),
        (2, 1, 'Интернет-магазин', 'Нужно разработать небольшой интернет-магазин.', 80000, '2026-08-10', 'В работе'),
        (2, 3, 'Тексты для сайта', 'Нужно подготовить 10 SEO-текстов.', 15000, '2026-07-15', 'Новая');

        INSERT INTO bids (request_id, freelancer_id, bid_text, proposed_price, proposed_days, status) VALUES
        (1, 1, 'Готов разработать сайт на HTML, CSS и JavaScript.', 32000, 14, 'Принят'),
        (2, 2, 'Сделаю три варианта логотипа.', 10000, 5, 'На рассмотрении'),
        (3, 1, 'Разработаю интернет-магазин с каталогом и корзиной.', 78000, 30, 'Принят'),
        (4, 2, 'Подготовлю тексты и структуру страниц.', 14000, 7, 'На рассмотрении');

        INSERT INTO contracts (request_id, bid_id, start_date, end_date, total_price, status) VALUES
        (1, 1, '2026-06-10', '2026-06-24', 32000, 'Активен'),
        (3, 3, '2026-06-12', '2026-07-12', 78000, 'Активен');

        INSERT INTO payments (contract_id, amount, payment_date, payment_method, status) VALUES
        (1, 16000, '2026-06-10', 'Банковская карта', 'Оплачен'),
        (1, 16000, '2026-06-24', 'Банковская карта', 'Ожидается'),
        (2, 39000, '2026-06-12', 'Банковский перевод', 'Оплачен');

        INSERT INTO reviews (contract_id, rating, comment) VALUES
        (1, 5, 'Исполнитель выполнил работу качественно и в срок.');
        """
        self.conn.executescript(script.replace("?", f"'{password}'", 6))
        self.conn.commit()

    def backup(self, target_folder: str) -> str:
        os.makedirs(target_folder, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_name = f"freelance_exchange_backup_{timestamp}.db"
        backup_path = os.path.join(target_folder, backup_name)
        self.conn.commit()
        shutil.copy2(self.path, backup_path)
        return backup_path


class LoginWindow(tk.Tk):
    def __init__(self):
        super().__init__()
        self.db = Database()
        self.title("Вход — фриланс-биржа")
        self.geometry("480x360")
        self.resizable(False, False)
        self.configure(bg="#f5f5f5")
        self.create_widgets()

    def create_widgets(self):
        frame = ttk.Frame(self, padding=24)
        frame.pack(fill="both", expand=True)

        ttk.Label(frame, text="База данных учета заявок фриланс-биржи", font=("Arial", 14, "bold")).pack(pady=(0, 12))
        ttk.Label(frame, text="Тестовые аккаунты:").pack(anchor="w")
        ttk.Label(frame, text="admin@mail.ru / client1@mail.ru / freelancer1@mail.ru / manager@mail.ru").pack(anchor="w")
        ttk.Label(frame, text="Пароль для всех: 12345").pack(anchor="w", pady=(0, 16))

        ttk.Label(frame, text="Email").pack(anchor="w")
        self.email_var = tk.StringVar(value="admin@mail.ru")
        ttk.Entry(frame, textvariable=self.email_var).pack(fill="x", pady=(0, 8))

        ttk.Label(frame, text="Пароль").pack(anchor="w")
        self.password_var = tk.StringVar(value="12345")
        ttk.Entry(frame, textvariable=self.password_var, show="*").pack(fill="x", pady=(0, 16))

        ttk.Button(frame, text="Войти", command=self.login).pack(fill="x")
        ttk.Button(frame, text="Открыть без входа как администратор", command=self.open_admin).pack(fill="x", pady=(8, 0))

    def login(self):
        email = self.email_var.get().strip()
        password = self.password_var.get()
        row = self.db.query(
            """
            SELECT u.*, r.role_name
            FROM users u
            JOIN roles r ON u.role_id = r.role_id
            WHERE u.email = ? AND u.password_hash = ? AND u.is_active = 1
            """,
            (email, hash_password(password)),
        )
        if not row:
            messagebox.showerror("Ошибка", "Неверный email или пароль.")
            return
        self.destroy()
        app = FreelanceApp(self.db, row[0])
        app.mainloop()

    def open_admin(self):
        row = self.db.query(
            """
            SELECT u.*, r.role_name
            FROM users u
            JOIN roles r ON u.role_id = r.role_id
            WHERE u.email = 'admin@mail.ru'
            """
        )[0]
        self.destroy()
        app = FreelanceApp(self.db, row)
        app.mainloop()


class FreelanceApp(tk.Tk):
    def __init__(self, db: Database, user):
        super().__init__()
        self.db = db
        self.user = user
        self.title(f"{APP_TITLE} | {user['full_name']} ({user['role_name']})")
        self.geometry("1180x760")
        self.minsize(1000, 650)
        self.status_values = ["Все", "Новая", "В работе", "Завершена", "Отменена"]
        self.create_menu()
        self.create_widgets()
        self.refresh_all()

    def create_menu(self):
        menubar = tk.Menu(self)
        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="Сделать резервную копию", command=self.backup_db)
        file_menu.add_command(label="Выход", command=self.destroy)
        menubar.add_cascade(label="Файл", menu=file_menu)
        self.config(menu=menubar)

    def create_widgets(self):
        top = ttk.Frame(self, padding=(12, 10))
        top.pack(fill="x")
        ttk.Label(
            top,
            text="Информационная система: учет заявок фриланс-биржи",
            font=("Arial", 16, "bold"),
        ).pack(side="left")
        ttk.Label(top, text=f"Пользователь: {self.user['full_name']} | Роль: {self.user['role_name']}").pack(side="right")

        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill="both", expand=True, padx=12, pady=8)

        self.tab_requests = ttk.Frame(self.notebook, padding=10)
        self.tab_new_request = ttk.Frame(self.notebook, padding=10)
        self.tab_bids = ttk.Frame(self.notebook, padding=10)
        self.tab_contracts = ttk.Frame(self.notebook, padding=10)
        self.tab_reports = ttk.Frame(self.notebook, padding=10)
        self.tab_sql = ttk.Frame(self.notebook, padding=10)
        self.tab_admin = ttk.Frame(self.notebook, padding=10)

        self.notebook.add(self.tab_requests, text="Заявки")
        self.notebook.add(self.tab_new_request, text="Новая заявка")
        self.notebook.add(self.tab_bids, text="Отклики")
        self.notebook.add(self.tab_contracts, text="Договоры и платежи")
        self.notebook.add(self.tab_reports, text="Отчеты")
        self.notebook.add(self.tab_sql, text="SQL-запросы")
        self.notebook.add(self.tab_admin, text="Администрирование")

        self.build_requests_tab()
        self.build_new_request_tab()
        self.build_bids_tab()
        self.build_contracts_tab()
        self.build_reports_tab()
        self.build_sql_tab()
        self.build_admin_tab()

    def build_requests_tab(self):
        filters = ttk.LabelFrame(self.tab_requests, text="Поиск, фильтрация и сортировка", padding=10)
        filters.pack(fill="x")

        ttk.Label(filters, text="Поиск по названию:").grid(row=0, column=0, sticky="w")
        self.req_search_var = tk.StringVar()
        ttk.Entry(filters, textvariable=self.req_search_var, width=30).grid(row=0, column=1, padx=6)

        ttk.Label(filters, text="Статус:").grid(row=0, column=2, sticky="w")
        self.req_status_var = tk.StringVar(value="Все")
        ttk.Combobox(filters, textvariable=self.req_status_var, values=self.status_values, state="readonly", width=18).grid(row=0, column=3, padx=6)

        ttk.Label(filters, text="Сортировка:").grid(row=0, column=4, sticky="w")
        self.req_sort_var = tk.StringVar(value="Дата создания")
        ttk.Combobox(
            filters,
            textvariable=self.req_sort_var,
            values=["Дата создания", "Бюджет по убыванию", "Бюджет по возрастанию", "Срок выполнения"],
            state="readonly",
            width=22,
        ).grid(row=0, column=5, padx=6)

        ttk.Button(filters, text="Применить", command=self.load_requests).grid(row=0, column=6, padx=6)
        ttk.Button(filters, text="Сбросить", command=self.reset_request_filters).grid(row=0, column=7, padx=6)

        columns = ("id", "title", "client", "category", "budget", "deadline", "status", "created")
        self.req_tree = ttk.Treeview(self.tab_requests, columns=columns, show="headings", height=18)
        headings = {
            "id": "ID",
            "title": "Заявка",
            "client": "Заказчик",
            "category": "Категория",
            "budget": "Бюджет",
            "deadline": "Срок",
            "status": "Статус",
            "created": "Создана",
        }
        widths = {"id": 60, "title": 260, "client": 160, "category": 150, "budget": 100, "deadline": 100, "status": 120, "created": 160}
        for col in columns:
            self.req_tree.heading(col, text=headings[col])
            self.req_tree.column(col, width=widths[col], anchor="w")
        self.req_tree.pack(fill="both", expand=True, pady=10)

        actions = ttk.Frame(self.tab_requests)
        actions.pack(fill="x")
        ttk.Button(actions, text="Обновить", command=self.load_requests).pack(side="left")
        ttk.Button(actions, text="Статус: В работе", command=lambda: self.set_request_status("В работе")).pack(side="left", padx=4)
        ttk.Button(actions, text="Статус: Завершена", command=lambda: self.set_request_status("Завершена")).pack(side="left", padx=4)
        ttk.Button(actions, text="Статус: Отменена", command=lambda: self.set_request_status("Отменена")).pack(side="left", padx=4)

    def build_new_request_tab(self):
        form = ttk.LabelFrame(self.tab_new_request, text="Форма ввода новой заявки", padding=14)
        form.pack(fill="x", anchor="n")

        self.client_map = {}
        self.category_map = {}

        labels = ["Заказчик", "Категория", "Название", "Описание", "Бюджет", "Срок YYYY-MM-DD"]
        for i, label in enumerate(labels):
            ttk.Label(form, text=label).grid(row=i, column=0, sticky="w", pady=4)

        self.new_client_var = tk.StringVar()
        self.new_category_var = tk.StringVar()
        self.new_title_var = tk.StringVar()
        self.new_budget_var = tk.StringVar()
        self.new_deadline_var = tk.StringVar(value=date.today().isoformat())

        self.client_combo = ttk.Combobox(form, textvariable=self.new_client_var, state="readonly", width=45)
        self.category_combo = ttk.Combobox(form, textvariable=self.new_category_var, state="readonly", width=45)
        self.new_title_entry = ttk.Entry(form, textvariable=self.new_title_var, width=48)
        self.new_desc_text = tk.Text(form, width=60, height=6)
        self.new_budget_entry = ttk.Entry(form, textvariable=self.new_budget_var, width=48)
        self.new_deadline_entry = ttk.Entry(form, textvariable=self.new_deadline_var, width=48)

        self.client_combo.grid(row=0, column=1, sticky="w", pady=4)
        self.category_combo.grid(row=1, column=1, sticky="w", pady=4)
        self.new_title_entry.grid(row=2, column=1, sticky="w", pady=4)
        self.new_desc_text.grid(row=3, column=1, sticky="w", pady=4)
        self.new_budget_entry.grid(row=4, column=1, sticky="w", pady=4)
        self.new_deadline_entry.grid(row=5, column=1, sticky="w", pady=4)

        ttk.Button(form, text="Сохранить заявку", command=self.add_request).grid(row=6, column=1, sticky="w", pady=12)

        info = ttk.LabelFrame(self.tab_new_request, text="Проверки ввода", padding=10)
        info.pack(fill="x", pady=10)
        ttk.Label(
            info,
            text="Программа проверяет обязательные поля, положительный бюджет, дату в формате YYYY-MM-DD и наличие выбранных справочников.",
        ).pack(anchor="w")

    def build_bids_tab(self):
        pane = ttk.PanedWindow(self.tab_bids, orient="horizontal")
        pane.pack(fill="both", expand=True)

        left = ttk.Frame(pane, padding=8)
        right = ttk.Frame(pane, padding=8)
        pane.add(left, weight=1)
        pane.add(right, weight=2)

        form = ttk.LabelFrame(left, text="Форма подачи отклика", padding=10)
        form.pack(fill="x")

        self.bid_request_map = {}
        self.bid_freelancer_map = {}
        self.bid_request_var = tk.StringVar()
        self.bid_freelancer_var = tk.StringVar()
        self.bid_price_var = tk.StringVar()
        self.bid_days_var = tk.StringVar(value="7")

        ttk.Label(form, text="Заявка").pack(anchor="w")
        self.bid_request_combo = ttk.Combobox(form, textvariable=self.bid_request_var, state="readonly", width=45)
        self.bid_request_combo.pack(fill="x", pady=4)

        ttk.Label(form, text="Исполнитель").pack(anchor="w")
        self.bid_freelancer_combo = ttk.Combobox(form, textvariable=self.bid_freelancer_var, state="readonly", width=45)
        self.bid_freelancer_combo.pack(fill="x", pady=4)

        ttk.Label(form, text="Текст отклика").pack(anchor="w")
        self.bid_text = tk.Text(form, height=6)
        self.bid_text.pack(fill="x", pady=4)

        ttk.Label(form, text="Цена").pack(anchor="w")
        ttk.Entry(form, textvariable=self.bid_price_var).pack(fill="x", pady=4)

        ttk.Label(form, text="Срок, дней").pack(anchor="w")
        ttk.Entry(form, textvariable=self.bid_days_var).pack(fill="x", pady=4)

        ttk.Button(form, text="Добавить отклик", command=self.add_bid).pack(fill="x", pady=8)

        bid_actions = ttk.LabelFrame(left, text="Изменение статуса отклика", padding=10)
        bid_actions.pack(fill="x", pady=10)
        ttk.Button(bid_actions, text="Принять выбранный отклик", command=lambda: self.set_bid_status("Принят")).pack(fill="x", pady=3)
        ttk.Button(bid_actions, text="Отклонить выбранный отклик", command=lambda: self.set_bid_status("Отклонен")).pack(fill="x", pady=3)

        columns = ("id", "request", "freelancer", "price", "days", "status", "created")
        self.bid_tree = ttk.Treeview(right, columns=columns, show="headings", height=20)
        headings = {
            "id": "ID",
            "request": "Заявка",
            "freelancer": "Исполнитель",
            "price": "Цена",
            "days": "Дней",
            "status": "Статус",
            "created": "Дата",
        }
        widths = {"id": 50, "request": 230, "freelancer": 160, "price": 90, "days": 70, "status": 130, "created": 150}
        for col in columns:
            self.bid_tree.heading(col, text=headings[col])
            self.bid_tree.column(col, width=widths[col], anchor="w")
        self.bid_tree.pack(fill="both", expand=True)
        ttk.Button(right, text="Обновить", command=self.load_bids).pack(anchor="w", pady=8)

    def build_contracts_tab(self):
        top = ttk.LabelFrame(self.tab_contracts, text="Создание договора по принятому отклику", padding=10)
        top.pack(fill="x")

        self.contract_bid_map = {}
        self.contract_bid_var = tk.StringVar()
        self.contract_start_var = tk.StringVar(value=date.today().isoformat())
        self.contract_end_var = tk.StringVar(value=date.today().isoformat())

        ttk.Label(top, text="Принятый отклик").grid(row=0, column=0, sticky="w")
        self.contract_bid_combo = ttk.Combobox(top, textvariable=self.contract_bid_var, state="readonly", width=70)
        self.contract_bid_combo.grid(row=0, column=1, padx=6, pady=4)

        ttk.Label(top, text="Дата начала").grid(row=1, column=0, sticky="w")
        ttk.Entry(top, textvariable=self.contract_start_var, width=25).grid(row=1, column=1, sticky="w", padx=6, pady=4)

        ttk.Label(top, text="Дата окончания").grid(row=2, column=0, sticky="w")
        ttk.Entry(top, textvariable=self.contract_end_var, width=25).grid(row=2, column=1, sticky="w", padx=6, pady=4)

        ttk.Button(top, text="Создать договор", command=self.add_contract).grid(row=3, column=1, sticky="w", padx=6, pady=8)

        middle = ttk.PanedWindow(self.tab_contracts, orient="horizontal")
        middle.pack(fill="both", expand=True, pady=10)

        left = ttk.Frame(middle)
        right = ttk.Frame(middle)
        middle.add(left, weight=2)
        middle.add(right, weight=1)

        columns = ("id", "request", "freelancer", "start", "end", "price", "status")
        self.contract_tree = ttk.Treeview(left, columns=columns, show="headings", height=14)
        headings = {
            "id": "ID",
            "request": "Заявка",
            "freelancer": "Исполнитель",
            "start": "Начало",
            "end": "Окончание",
            "price": "Сумма",
            "status": "Статус",
        }
        for col in columns:
            self.contract_tree.heading(col, text=headings[col])
            self.contract_tree.column(col, width=120, anchor="w")
        self.contract_tree.column("request", width=230)
        self.contract_tree.column("freelancer", width=160)
        self.contract_tree.pack(fill="both", expand=True)
        ttk.Button(left, text="Обновить", command=self.load_contracts).pack(anchor="w", pady=6)

        pay_form = ttk.LabelFrame(right, text="Добавить платеж", padding=10)
        pay_form.pack(fill="x")
        self.pay_amount_var = tk.StringVar()
        self.pay_date_var = tk.StringVar(value=date.today().isoformat())
        self.pay_method_var = tk.StringVar(value="Банковская карта")
        self.pay_status_var = tk.StringVar(value="Ожидается")

        for label, var, values in [
            ("Сумма", self.pay_amount_var, None),
            ("Дата", self.pay_date_var, None),
            ("Метод", self.pay_method_var, ["Банковская карта", "Банковский перевод", "Электронный кошелек"]),
            ("Статус", self.pay_status_var, ["Ожидается", "Оплачен", "Возврат"]),
        ]:
            ttk.Label(pay_form, text=label).pack(anchor="w")
            if values:
                ttk.Combobox(pay_form, textvariable=var, values=values, state="readonly").pack(fill="x", pady=3)
            else:
                ttk.Entry(pay_form, textvariable=var).pack(fill="x", pady=3)
        ttk.Button(pay_form, text="Сохранить платеж", command=self.add_payment).pack(fill="x", pady=8)

    def build_reports_tab(self):
        buttons = ttk.Frame(self.tab_reports)
        buttons.pack(fill="x")

        ttk.Button(buttons, text="Отчет по заявкам", command=self.report_requests).pack(side="left", padx=4)
        ttk.Button(buttons, text="Сводка по категориям", command=self.report_categories).pack(side="left", padx=4)
        ttk.Button(buttons, text="Отчет по платежам", command=self.report_payments).pack(side="left", padx=4)
        ttk.Button(buttons, text="Рейтинг исполнителей", command=self.report_freelancers).pack(side="left", padx=4)
        ttk.Button(buttons, text="Экспорт отчета в TXT", command=self.export_report_txt).pack(side="right", padx=4)

        self.report_text = tk.Text(self.tab_reports, wrap="none", font=("Consolas", 10))
        self.report_text.pack(fill="both", expand=True, pady=10)

    def build_sql_tab(self):
        info = ttk.LabelFrame(self.tab_sql, text="Готовые SQL-запросы разного типа", padding=10)
        info.pack(fill="x")

        queries = [
            ("1. Все заявки", "SELECT request_id, title, budget, deadline, status FROM requests;"),
            ("2. Активные заявки", "SELECT title, budget, deadline FROM requests WHERE status IN ('Новая', 'В работе');"),
            ("3. Бюджет > 30000", "SELECT title, budget, status FROM requests WHERE budget > 30000;"),
            ("4. Сортировка по бюджету", "SELECT title, budget, deadline FROM requests ORDER BY budget DESC;"),
            ("5. Группировка по категориям", "SELECT c.category_name, COUNT(r.request_id) AS request_count FROM categories c LEFT JOIN requests r ON c.category_id = r.category_id GROUP BY c.category_name ORDER BY request_count DESC;"),
            ("6. Заявки + заказчики", "SELECT r.title, u.full_name AS client_name, c.company_name, r.budget, r.status FROM requests r JOIN clients c ON r.client_id = c.client_id JOIN users u ON c.user_id = u.user_id;"),
            ("7. Отклики по заявкам", "SELECT r.title AS request_title, u.full_name AS freelancer_name, b.proposed_price, b.proposed_days, b.status FROM bids b JOIN requests r ON b.request_id = r.request_id JOIN freelancers f ON b.freelancer_id = f.freelancer_id JOIN users u ON f.user_id = u.user_id ORDER BY r.title;"),
            ("8. Сводка оплат", "SELECT p.status, COUNT(p.payment_id) AS payment_count, SUM(p.amount) AS total_amount FROM payments p GROUP BY p.status;"),
            ("9. Договоры", "SELECT ct.contract_id, r.title, ct.total_price, ct.status FROM contracts ct JOIN requests r ON ct.request_id = r.request_id;"),
            ("10. Рейтинг исполнителей", "SELECT u.full_name, f.specialization, f.rating FROM freelancers f JOIN users u ON f.user_id = u.user_id ORDER BY f.rating DESC;"),
        ]
        self.ready_queries = queries

        for i, (title, sql) in enumerate(queries):
            ttk.Button(info, text=title, command=lambda s=sql: self.run_ready_sql(s)).grid(row=i // 5, column=i % 5, padx=3, pady=3, sticky="ew")

        custom = ttk.LabelFrame(self.tab_sql, text="Пользовательский SELECT-запрос", padding=10)
        custom.pack(fill="x", pady=8)

        self.sql_text = tk.Text(custom, height=4, font=("Consolas", 10))
        self.sql_text.pack(fill="x")
        self.sql_text.insert("1.0", "SELECT * FROM requests;")
        ttk.Button(custom, text="Выполнить SELECT", command=self.run_custom_sql).pack(anchor="w", pady=6)

        self.sql_result = tk.Text(self.tab_sql, wrap="none", font=("Consolas", 10))
        self.sql_result.pack(fill="both", expand=True, pady=8)

    def build_admin_tab(self):
        frame = ttk.LabelFrame(self.tab_admin, text="Администрирование и защита", padding=12)
        frame.pack(fill="both", expand=True)

        text = (
            "Роли пользователей:\n"
            "• Администратор — полный доступ к таблицам, отчетам и резервному копированию.\n"
            "• Заказчик — создание заявок и просмотр своих заказов.\n"
            "• Исполнитель — просмотр заявок и подача откликов.\n"
            "• Менеджер — контроль заявок, договоров, платежей и отчетов.\n\n"
            "Защита от некорректного ввода:\n"
            "• обязательные поля;\n"
            "• уникальный email;\n"
            "• положительный бюджет и суммы платежей;\n"
            "• допустимые статусы;\n"
            "• внешние ключи между таблицами;\n"
            "• проверка даты и рейтинга.\n\n"
            "Резервное копирование:\n"
            "• рекомендуется выполнять полную копию базы один раз в неделю;\n"
            "• копии хранить отдельно от основной базы;\n"
            "• периодически проверять восстановление.\n"
        )

        self.admin_text = tk.Text(frame, wrap="word", font=("Arial", 11))
        self.admin_text.pack(fill="both", expand=True)
        self.admin_text.insert("1.0", text)
        self.admin_text.config(state="disabled")

        buttons = ttk.Frame(self.tab_admin)
        buttons.pack(fill="x", pady=8)
        ttk.Button(buttons, text="Сделать резервную копию базы", command=self.backup_db).pack(side="left", padx=4)
        ttk.Button(buttons, text="Показать таблицы и количество записей", command=self.show_table_counts).pack(side="left", padx=4)

    def refresh_all(self):
        self.load_reference_data()
        self.load_requests()
        self.load_bids()
        self.load_contracts()
        self.report_requests()

    def load_reference_data(self):
        clients = self.db.query(
            """
            SELECT c.client_id, u.full_name, COALESCE(c.company_name, '') AS company_name
            FROM clients c
            JOIN users u ON c.user_id = u.user_id
            ORDER BY u.full_name
            """
        )
        self.client_map = {f"{row['client_id']} — {row['full_name']} ({row['company_name']})": row["client_id"] for row in clients}
        self.client_combo["values"] = list(self.client_map.keys())
        if self.client_map and not self.new_client_var.get():
            self.new_client_var.set(next(iter(self.client_map.keys())))

        cats = self.db.query("SELECT category_id, category_name FROM categories ORDER BY category_name")
        self.category_map = {f"{row['category_id']} — {row['category_name']}": row["category_id"] for row in cats}
        self.category_combo["values"] = list(self.category_map.keys())
        if self.category_map and not self.new_category_var.get():
            self.new_category_var.set(next(iter(self.category_map.keys())))

        requests = self.db.query("SELECT request_id, title, budget FROM requests WHERE status != 'Завершена' ORDER BY created_at DESC")
        self.bid_request_map = {f"{row['request_id']} — {row['title']} ({row['budget']:.2f} руб.)": row["request_id"] for row in requests}
        self.bid_request_combo["values"] = list(self.bid_request_map.keys())
        if self.bid_request_map and not self.bid_request_var.get():
            self.bid_request_var.set(next(iter(self.bid_request_map.keys())))

        freelancers = self.db.query(
            """
            SELECT f.freelancer_id, u.full_name, f.specialization
            FROM freelancers f
            JOIN users u ON f.user_id = u.user_id
            ORDER BY u.full_name
            """
        )
        self.bid_freelancer_map = {f"{row['freelancer_id']} — {row['full_name']} ({row['specialization']})": row["freelancer_id"] for row in freelancers}
        self.bid_freelancer_combo["values"] = list(self.bid_freelancer_map.keys())
        if self.bid_freelancer_map and not self.bid_freelancer_var.get():
            self.bid_freelancer_var.set(next(iter(self.bid_freelancer_map.keys())))

        accepted = self.db.query(
            """
            SELECT b.bid_id, b.request_id, r.title, b.proposed_price, u.full_name
            FROM bids b
            JOIN requests r ON b.request_id = r.request_id
            JOIN freelancers f ON b.freelancer_id = f.freelancer_id
            JOIN users u ON f.user_id = u.user_id
            LEFT JOIN contracts ct ON ct.bid_id = b.bid_id
            WHERE b.status = 'Принят' AND ct.contract_id IS NULL
            ORDER BY b.created_at DESC
            """
        )
        self.contract_bid_map = {
            f"{row['bid_id']} — {row['title']} | {row['full_name']} | {row['proposed_price']:.2f} руб.": row["bid_id"]
            for row in accepted
        }
        self.contract_bid_combo["values"] = list(self.contract_bid_map.keys())
        if self.contract_bid_map:
            self.contract_bid_var.set(next(iter(self.contract_bid_map.keys())))
        else:
            self.contract_bid_var.set("")

    def reset_request_filters(self):
        self.req_search_var.set("")
        self.req_status_var.set("Все")
        self.req_sort_var.set("Дата создания")
        self.load_requests()

    def load_requests(self):
        for item in self.req_tree.get_children():
            self.req_tree.delete(item)

        sql = """
        SELECT r.request_id, r.title, u.full_name AS client_name, c.category_name,
               r.budget, r.deadline, r.status, r.created_at
        FROM requests r
        JOIN clients cl ON r.client_id = cl.client_id
        JOIN users u ON cl.user_id = u.user_id
        JOIN categories c ON r.category_id = c.category_id
        WHERE 1=1
        """
        params = []

        search = self.req_search_var.get().strip()
        if search:
            sql += " AND LOWER(r.title) LIKE ?"
            params.append(f"%{search.lower()}%")

        status = self.req_status_var.get()
        if status and status != "Все":
            sql += " AND r.status = ?"
            params.append(status)

        sort = self.req_sort_var.get()
        if sort == "Бюджет по убыванию":
            sql += " ORDER BY r.budget DESC"
        elif sort == "Бюджет по возрастанию":
            sql += " ORDER BY r.budget ASC"
        elif sort == "Срок выполнения":
            sql += " ORDER BY r.deadline ASC"
        else:
            sql += " ORDER BY r.created_at DESC"

        for row in self.db.query(sql, params):
            self.req_tree.insert(
                "",
                "end",
                values=(
                    row["request_id"],
                    row["title"],
                    row["client_name"],
                    row["category_name"],
                    f"{row['budget']:.2f}",
                    row["deadline"],
                    row["status"],
                    row["created_at"],
                ),
            )

    def get_selected_id(self, tree: ttk.Treeview):
        selected = tree.selection()
        if not selected:
            return None
        return tree.item(selected[0], "values")[0]

    def set_request_status(self, status: str):
        request_id = self.get_selected_id(self.req_tree)
        if not request_id:
            messagebox.showwarning("Внимание", "Выберите заявку.")
            return
        self.db.execute("UPDATE requests SET status = ? WHERE request_id = ?", (status, request_id), commit=True)
        self.load_requests()
        self.load_reference_data()
        messagebox.showinfo("Готово", f"Статус заявки изменен на «{status}».")

    def add_request(self):
        try:
            client_id = self.client_map[self.new_client_var.get()]
            category_id = self.category_map[self.new_category_var.get()]
            title = self.new_title_var.get().strip()
            desc = self.new_desc_text.get("1.0", "end").strip()
            budget = float(self.new_budget_var.get().replace(",", "."))
            deadline = self.new_deadline_var.get().strip()
            datetime.strptime(deadline, "%Y-%m-%d")
            if not title or not desc:
                raise ValueError("Название и описание обязательны.")
            if budget <= 0:
                raise ValueError("Бюджет должен быть положительным.")
        except KeyError:
            messagebox.showerror("Ошибка", "Выберите заказчика и категорию.")
            return
        except ValueError as exc:
            messagebox.showerror("Ошибка ввода", str(exc))
            return

        self.db.execute(
            """
            INSERT INTO requests (client_id, category_id, title, description, budget, deadline, status)
            VALUES (?, ?, ?, ?, ?, ?, 'Новая')
            """,
            (client_id, category_id, title, desc, budget, deadline),
            commit=True,
        )
        self.new_title_var.set("")
        self.new_desc_text.delete("1.0", "end")
        self.new_budget_var.set("")
        self.load_reference_data()
        self.load_requests()
        messagebox.showinfo("Готово", "Заявка добавлена.")

    def load_bids(self):
        for item in self.bid_tree.get_children():
            self.bid_tree.delete(item)
        rows = self.db.query(
            """
            SELECT b.bid_id, r.title, u.full_name AS freelancer_name,
                   b.proposed_price, b.proposed_days, b.status, b.created_at
            FROM bids b
            JOIN requests r ON b.request_id = r.request_id
            JOIN freelancers f ON b.freelancer_id = f.freelancer_id
            JOIN users u ON f.user_id = u.user_id
            ORDER BY b.created_at DESC
            """
        )
        for row in rows:
            self.bid_tree.insert(
                "",
                "end",
                values=(
                    row["bid_id"],
                    row["title"],
                    row["freelancer_name"],
                    f"{row['proposed_price']:.2f}",
                    row["proposed_days"],
                    row["status"],
                    row["created_at"],
                ),
            )

    def add_bid(self):
        try:
            request_id = self.bid_request_map[self.bid_request_var.get()]
            freelancer_id = self.bid_freelancer_map[self.bid_freelancer_var.get()]
            text = self.bid_text.get("1.0", "end").strip()
            price = float(self.bid_price_var.get().replace(",", "."))
            days = int(self.bid_days_var.get())
            if not text:
                raise ValueError("Текст отклика обязателен.")
            if price <= 0 or days <= 0:
                raise ValueError("Цена и срок должны быть положительными.")
        except KeyError:
            messagebox.showerror("Ошибка", "Выберите заявку и исполнителя.")
            return
        except ValueError as exc:
            messagebox.showerror("Ошибка ввода", str(exc))
            return

        self.db.execute(
            """
            INSERT INTO bids (request_id, freelancer_id, bid_text, proposed_price, proposed_days, status)
            VALUES (?, ?, ?, ?, ?, 'На рассмотрении')
            """,
            (request_id, freelancer_id, text, price, days),
            commit=True,
        )
        self.bid_text.delete("1.0", "end")
        self.bid_price_var.set("")
        self.load_bids()
        self.load_reference_data()
        messagebox.showinfo("Готово", "Отклик добавлен.")

    def set_bid_status(self, status: str):
        bid_id = self.get_selected_id(self.bid_tree)
        if not bid_id:
            messagebox.showwarning("Внимание", "Выберите отклик.")
            return
        self.db.execute("UPDATE bids SET status = ? WHERE bid_id = ?", (status, bid_id), commit=True)
        if status == "Принят":
            request_row = self.db.query("SELECT request_id FROM bids WHERE bid_id = ?", (bid_id,))
            if request_row:
                self.db.execute("UPDATE requests SET status = 'В работе' WHERE request_id = ?", (request_row[0]["request_id"],), commit=True)
        self.load_bids()
        self.load_requests()
        self.load_reference_data()
        messagebox.showinfo("Готово", f"Статус отклика изменен на «{status}».")

    def load_contracts(self):
        for item in self.contract_tree.get_children():
            self.contract_tree.delete(item)

        rows = self.db.query(
            """
            SELECT ct.contract_id, r.title, u.full_name AS freelancer_name,
                   ct.start_date, ct.end_date, ct.total_price, ct.status
            FROM contracts ct
            JOIN requests r ON ct.request_id = r.request_id
            JOIN bids b ON ct.bid_id = b.bid_id
            JOIN freelancers f ON b.freelancer_id = f.freelancer_id
            JOIN users u ON f.user_id = u.user_id
            ORDER BY ct.contract_id DESC
            """
        )
        for row in rows:
            self.contract_tree.insert(
                "",
                "end",
                values=(
                    row["contract_id"],
                    row["title"],
                    row["freelancer_name"],
                    row["start_date"],
                    row["end_date"],
                    f"{row['total_price']:.2f}",
                    row["status"],
                ),
            )

    def add_contract(self):
        try:
            bid_id = self.contract_bid_map[self.contract_bid_var.get()]
            start = self.contract_start_var.get().strip()
            end = self.contract_end_var.get().strip()
            start_dt = datetime.strptime(start, "%Y-%m-%d")
            end_dt = datetime.strptime(end, "%Y-%m-%d")
            if end_dt < start_dt:
                raise ValueError("Дата окончания не может быть раньше даты начала.")
        except KeyError:
            messagebox.showerror("Ошибка", "Нет выбранного принятого отклика.")
            return
        except ValueError as exc:
            messagebox.showerror("Ошибка ввода", str(exc))
            return

        row = self.db.query("SELECT request_id, proposed_price FROM bids WHERE bid_id = ?", (bid_id,))
        if not row:
            messagebox.showerror("Ошибка", "Отклик не найден.")
            return

        try:
            self.db.execute(
                """
                INSERT INTO contracts (request_id, bid_id, start_date, end_date, total_price, status)
                VALUES (?, ?, ?, ?, ?, 'Активен')
                """,
                (row[0]["request_id"], bid_id, start, end, row[0]["proposed_price"]),
                commit=True,
            )
            self.db.execute("UPDATE requests SET status = 'В работе' WHERE request_id = ?", (row[0]["request_id"],), commit=True)
        except sqlite3.IntegrityError as exc:
            messagebox.showerror("Ошибка", f"Договор по этой заявке или отклику уже существует.\n{exc}")
            return

        self.load_contracts()
        self.load_requests()
        self.load_reference_data()
        messagebox.showinfo("Готово", "Договор создан.")

    def add_payment(self):
        contract_id = self.get_selected_id(self.contract_tree)
        if not contract_id:
            messagebox.showwarning("Внимание", "Выберите договор.")
            return
        try:
            amount = float(self.pay_amount_var.get().replace(",", "."))
            payment_date = self.pay_date_var.get().strip()
            datetime.strptime(payment_date, "%Y-%m-%d")
            method = self.pay_method_var.get().strip()
            status = self.pay_status_var.get().strip()
            if amount <= 0:
                raise ValueError("Сумма должна быть положительной.")
        except ValueError as exc:
            messagebox.showerror("Ошибка ввода", str(exc))
            return

        self.db.execute(
            """
            INSERT INTO payments (contract_id, amount, payment_date, payment_method, status)
            VALUES (?, ?, ?, ?, ?)
            """,
            (contract_id, amount, payment_date, method, status),
            commit=True,
        )
        self.pay_amount_var.set("")
        messagebox.showinfo("Готово", "Платеж добавлен.")

    def rows_to_text(self, title: str, rows):
        if not rows:
            return f"{title}\n\nНет данных."
        headers = rows[0].keys()
        widths = []
        for h in headers:
            max_len = len(str(h))
            for r in rows:
                max_len = max(max_len, len(str(r[h])))
            widths.append(min(max_len + 2, 35))

        lines = [title, "=" * len(title)]
        header_line = "".join(str(h).ljust(widths[i]) for i, h in enumerate(headers))
        lines.append(header_line)
        lines.append("-" * len(header_line))
        for r in rows:
            lines.append("".join(str(r[h]).ljust(widths[i])[:widths[i]] for i, h in enumerate(headers)))
        return "\n".join(lines)

    def show_report(self, title: str, rows):
        self.report_text.delete("1.0", "end")
        self.report_text.insert("1.0", self.rows_to_text(title, rows))

    def report_requests(self):
        rows = self.db.query(
            """
            SELECT r.request_id AS id, r.title AS заявка, u.full_name AS заказчик,
                   c.category_name AS категория, r.budget AS бюджет,
                   r.deadline AS срок, r.status AS статус
            FROM requests r
            JOIN clients cl ON r.client_id = cl.client_id
            JOIN users u ON cl.user_id = u.user_id
            JOIN categories c ON r.category_id = c.category_id
            ORDER BY r.created_at DESC
            """
        )
        self.show_report("ОТЧЕТ ПО ЗАЯВКАМ", rows)

    def report_categories(self):
        rows = self.db.query(
            """
            SELECT c.category_name AS категория,
                   COUNT(r.request_id) AS количество_заявок,
                   COALESCE(SUM(r.budget), 0) AS общий_бюджет,
                   ROUND(COALESCE(AVG(r.budget), 0), 2) AS средний_бюджет
            FROM categories c
            LEFT JOIN requests r ON c.category_id = r.category_id
            GROUP BY c.category_name
            ORDER BY общий_бюджет DESC
            """
        )
        self.show_report("СВОДНЫЙ ОТЧЕТ ПО КАТЕГОРИЯМ", rows)

    def report_payments(self):
        rows = self.db.query(
            """
            SELECT p.status AS статус,
                   COUNT(p.payment_id) AS количество,
                   COALESCE(SUM(p.amount), 0) AS сумма
            FROM payments p
            GROUP BY p.status
            ORDER BY сумма DESC
            """
        )
        self.show_report("ОТЧЕТ ПО ПЛАТЕЖАМ", rows)

    def report_freelancers(self):
        rows = self.db.query(
            """
            SELECT u.full_name AS исполнитель,
                   f.specialization AS специализация,
                   f.rating AS рейтинг,
                   COUNT(b.bid_id) AS количество_откликов
            FROM freelancers f
            JOIN users u ON f.user_id = u.user_id
            LEFT JOIN bids b ON f.freelancer_id = b.freelancer_id
            GROUP BY u.full_name, f.specialization, f.rating
            ORDER BY f.rating DESC
            """
        )
        self.show_report("РЕЙТИНГ ИСПОЛНИТЕЛЕЙ", rows)

    def export_report_txt(self):
        content = self.report_text.get("1.0", "end").strip()
        if not content:
            messagebox.showwarning("Внимание", "Сначала сформируйте отчет.")
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
            initialfile="report.txt",
        )
        if not path:
            return
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        messagebox.showinfo("Готово", f"Отчет сохранен:\n{path}")

    def run_ready_sql(self, sql: str):
        self.sql_text.delete("1.0", "end")
        self.sql_text.insert("1.0", sql)
        self.run_custom_sql()

    def run_custom_sql(self):
        sql = self.sql_text.get("1.0", "end").strip()
        if not sql.lower().startswith("select"):
            messagebox.showwarning("Ограничение", "В пользовательском поле разрешены только SELECT-запросы.")
            return
        try:
            rows = self.db.query(sql)
            self.sql_result.delete("1.0", "end")
            self.sql_result.insert("1.0", self.rows_to_text("РЕЗУЛЬТАТ SQL-ЗАПРОСА", rows))
        except Exception as exc:
            messagebox.showerror("Ошибка SQL", str(exc))

    def backup_db(self):
        folder = filedialog.askdirectory(title="Выберите папку для резервной копии")
        if not folder:
            return
        try:
            path = self.db.backup(folder)
            messagebox.showinfo("Резервная копия создана", f"Файл сохранен:\n{path}")
        except Exception as exc:
            messagebox.showerror("Ошибка", str(exc))

    def show_table_counts(self):
        tables = ["roles", "users", "clients", "freelancers", "categories", "requests", "bids", "contracts", "payments", "reviews"]
        rows = []
        for table in tables:
            cnt = self.db.query(f"SELECT COUNT(*) AS cnt FROM {table}")[0]["cnt"]
            rows.append({"таблица": table, "записей": cnt})
        text = self.rows_to_text("КОЛИЧЕСТВО ЗАПИСЕЙ В ТАБЛИЦАХ", rows)
        self.admin_text.config(state="normal")
        self.admin_text.delete("1.0", "end")
        self.admin_text.insert("1.0", text)
        self.admin_text.config(state="disabled")


if __name__ == "__main__":
    LoginWindow().mainloop()
