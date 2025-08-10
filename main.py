"""
Simple Library Management System (Python + SQLite)

File: library_management.py
Run: python library_management.py

Features:
- SQLite database (library.db)
- Books, Members, Loans tables
- Add/list/search books and members
- Issue and return books (tracks availability)
- CLI menu

This is a single-file starter project you can extend (Flask/GUI/MySQL/SQLAlchemy, etc.).
"""

import sqlite3
from contextlib import closing
from datetime import datetime, timedelta
import os
import textwrap

DB_PATH = "library.db"

SCHEMA_SQL = textwrap.dedent("""
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS books (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    author TEXT,
    year INTEGER,
    copies_total INTEGER NOT NULL DEFAULT 1,
    copies_available INTEGER NOT NULL DEFAULT 1,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS members (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    email TEXT UNIQUE,
    phone TEXT,
    joined_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS loans (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    book_id INTEGER NOT NULL,
    member_id INTEGER NOT NULL,
    issue_date TEXT NOT NULL,
    due_date TEXT NOT NULL,
    return_date TEXT,
    FOREIGN KEY(book_id) REFERENCES books(id),
    FOREIGN KEY(member_id) REFERENCES members(id)
);
""")


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    # enable foreign keys
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def init_db():
    if not os.path.exists(DB_PATH):
        print("Initializing database...")
    with closing(get_conn()) as conn:
        conn.executescript(SCHEMA_SQL)
        conn.commit()


######### Book Operations #########

def add_book(title, author=None, year=None, copies=1):
    with closing(get_conn()) as conn:
        cur = conn.execute(
            "INSERT INTO books (title, author, year, copies_total, copies_available) VALUES (?, ?, ?, ?, ?)",
            (title, author, year, copies, copies),
        )
        conn.commit()
        print(f"Added book id={cur.lastrowid}")


def list_books():
    with closing(get_conn()) as conn:
        cur = conn.execute("SELECT * FROM books ORDER BY id")
        rows = cur.fetchall()
        if not rows:
            print("No books found.")
            return
        for r in rows:
            print(f"[{r['id']}] {r['title']} - {r['author']} ({r['year']}) | available: {r['copies_available']}/{r['copies_total']}")


def search_books(keyword):
    kw = f"%{keyword}%"
    with closing(get_conn()) as conn:
        cur = conn.execute("SELECT * FROM books WHERE title LIKE ? OR author LIKE ? ORDER BY id", (kw, kw))
        rows = cur.fetchall()
        if not rows:
            print("No results.")
            return
        for r in rows:
            print(f"[{r['id']}] {r['title']} - {r['author']} ({r['year']}) | available: {r['copies_available']}/{r['copies_total']}")


def update_book_copies(book_id, delta):
    with closing(get_conn()) as conn:
        cur = conn.execute("SELECT copies_available, copies_total FROM books WHERE id = ?", (book_id,))
        r = cur.fetchone()
        if not r:
            return False
        new_available = r['copies_available'] + delta
        if new_available < 0 or new_available > r['copies_total']:
            return False
        conn.execute("UPDATE books SET copies_available = ? WHERE id = ?", (new_available, book_id))
        conn.commit()
        return True


######### Member Operations #########

def add_member(name, email=None, phone=None):
    with closing(get_conn()) as conn:
        try:
            cur = conn.execute(
                "INSERT INTO members (name, email, phone) VALUES (?, ?, ?)",
                (name, email, phone),
            )
            conn.commit()
            print(f"Added member id={cur.lastrowid}")
        except sqlite3.IntegrityError:
            print("Email already exists. Use a different email.")


def list_members():
    with closing(get_conn()) as conn:
        cur = conn.execute("SELECT * FROM members ORDER BY id")
        rows = cur.fetchall()
        if not rows:
            print("No members found.")
            return
        for r in rows:
            print(f"[{r['id']}] {r['name']} | email: {r['email']} | phone: {r['phone']}")


######### Loan Operations #########

def issue_book(book_id, member_id, days=14):
    with closing(get_conn()) as conn:
        # check book availability
        cur = conn.execute("SELECT copies_available FROM books WHERE id = ?", (book_id,))
        r = cur.fetchone()
        if not r:
            print("Book not found.")
            return
        if r['copies_available'] <= 0:
            print("No copies available to issue.")
            return
        issue_date = datetime.utcnow()
        due_date = issue_date + timedelta(days=days)
        conn.execute(
            "INSERT INTO loans (book_id, member_id, issue_date, due_date) VALUES (?, ?, ?, ?)",
            (book_id, member_id, issue_date.isoformat(), due_date.isoformat()),
        )
        # decrement availability
        conn.execute("UPDATE books SET copies_available = copies_available - 1 WHERE id = ?", (book_id,))
        conn.commit()
        print(f"Issued book {book_id} to member {member_id}. Due on {due_date.date()}")


def return_book(loan_id):
    with closing(get_conn()) as conn:
        cur = conn.execute("SELECT * FROM loans WHERE id = ?", (loan_id,))
        loan = cur.fetchone()
        if not loan:
            print("Loan record not found.")
            return
        if loan['return_date'] is not None:
            print("Book already returned.")
            return
        return_date = datetime.utcnow().isoformat()
        conn.execute("UPDATE loans SET return_date = ? WHERE id = ?", (return_date, loan_id))
        # increase availability
        conn.execute("UPDATE books SET copies_available = copies_available + 1 WHERE id = ?", (loan['book_id'],))
        conn.commit()
        print("Book returned successfully.")


def list_loans(active_only=True):
    q = "SELECT l.id, l.book_id, b.title, l.member_id, m.name as member_name, l.issue_date, l.due_date, l.return_date FROM loans l JOIN books b ON l.book_id = b.id JOIN members m ON l.member_id = m.id"
    if active_only:
        q += " WHERE l.return_date IS NULL"
    q += " ORDER BY l.id"
    with closing(get_conn()) as conn:
        cur = conn.execute(q)
        rows = cur.fetchall()
        if not rows:
            print("No loans found.")
            return
        for r in rows:
            status = "Returned" if r['return_date'] else "Issued"
            issue = r['issue_date'][:10]
            due = r['due_date'][:10]
            print(f"[{r['id']}] Book: ({r['book_id']}) {r['title']} -> Member: ({r['member_id']}) {r['member_name']} | {status} | issue: {issue} | due: {due}")


######### CLI #########

def print_menu():
    print("\nLibrary Management - Menu")
    print("1. Add book")
    print("2. List books")
    print("3. Search books")
    print("4. Add member")
    print("5. List members")
    print("6. Issue book")
    print("7. Return book")
    print("8. List active loans")
    print("9. List all loans")
    print("10. Seed sample data")
    print("0. Exit")


def seed_sample_data():
    # adds sample books and members
    sample_books = [
        ("The Pragmatic Programmer", "Andrew Hunt", 1999, 2),
        ("Clean Code", "Robert C. Martin", 2008, 3),
        ("Introduction to Algorithms", "Cormen et al.", 2009, 1),
    ]
    sample_members = [
        ("Alice Johnson", "alice@example.com", "1234567890"),
        ("Bob Singh", "bob@example.com", "9876543210"),
    ]
    with closing(get_conn()) as conn:
        for b in sample_books:
            conn.execute("INSERT INTO books (title, author, year, copies_total, copies_available) VALUES (?, ?, ?, ?, ?)", b)
        for m in sample_members:
            try:
                conn.execute("INSERT INTO members (name, email, phone) VALUES (?, ?, ?)", m)
            except sqlite3.IntegrityError:
                pass
        conn.commit()
    print("Seeded sample books and members.")


def main():
    init_db()
    while True:
        print_menu()
        choice = input("Choose an option: ").strip()
        if choice == "1":
            title = input("Title: ").strip()
            author = input("Author: ").strip() or None
            year = input("Year: ").strip() or None
            copies = input("Copies: ").strip() or "1"
            try:
                year_val = int(year) if year else None
                copies_val = int(copies)
                add_book(title, author, year_val, copies_val)
            except ValueError:
                print("Year and copies must be numbers.")
        elif choice == "2":
            list_books()
        elif choice == "3":
            kw = input("Search keyword (title/author): ").strip()
            search_books(kw)
        elif choice == "4":
            name = input("Name: ").strip()
            email = input("Email: ").strip() or None
            phone = input("Phone: ").strip() or None
            add_member(name, email, phone)
        elif choice == "5":
            list_members()
        elif choice == "6":
            try:
                book_id = int(input("Book ID: ").strip())
                member_id = int(input("Member ID: ").strip())
                days = int(input("Loan days (default 14): ").strip() or "14")
                issue_book(book_id, member_id, days)
            except ValueError:
                print("IDs and days must be numbers.")
        elif choice == "7":
            try:
                loan_id = int(input("Loan ID: ").strip())
                return_book(loan_id)
            except ValueError:
                print("Loan ID must be a number.")
        elif choice == "8":
            list_loans(active_only=True)
        elif choice == "9":
            list_loans(active_only=False)
        elif choice == "10":
            seed_sample_data()
        elif choice == "0":
            print("Goodbye!")
            break
        else:
            print("Invalid choice.")


if __name__ == "__main__":
    main()
