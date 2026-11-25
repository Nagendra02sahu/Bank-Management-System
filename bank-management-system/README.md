# 🏦 Bank Management System (Python)

A fully working, menu-driven **Bank Management System** built with pure Python and **SQLite**.
No external libraries needed.

## Features
- Open Savings / Current accounts (auto-generated 10-digit account number)
- Secure login — PINs are hashed with **PBKDF2 + salt** (never stored in plain text)
- Account lock after 3 wrong PIN attempts (admin can unlock)
- Deposit, withdraw, and transfer between accounts (atomic database transactions)
- Minimum balance rule for Savings accounts (Rs. 500)
- Mini statement (last 10 transactions)
- Change PIN, close account
- Admin panel: view all accounts, unlock accounts, bank summary
- Money stored as integer paise (no floating-point errors)
- Unit tests included

## Project Structure
```
bank-management-system/
├── main.py              # entry point
├── bank/
│   ├── __init__.py
│   ├── cli.py           # menus / user interface
│   ├── services.py      # business logic
│   ├── database.py      # SQLite schema + connection
│   └── security.py      # PIN hashing
├── tests/
│   └── test_bank.py     # unit tests
├── requirements.txt
├── .gitignore
├── LICENSE
└── README.md
```

## How to Run
Requires Python 3.8+.
```bash
python main.py
```
The database file is created automatically at `data/bank.db`.

**Default admin login:** username `admin`, password `admin123` (change it for real use).

## Run Tests
```bash
python -m unittest discover -s tests -v
```

## Upload to GitHub
```bash
git init
git add .
git commit -m "Initial commit: Bank Management System"
git branch -M main
git remote add origin https://github.com/<your-username>/bank-management-system.git
git push -u origin main
```

## Future Improvements
- GUI with Tkinter or a web version with Flask/Django
- Interest calculation, loans, and fixed deposits
- Export statements to PDF

## Author
Nagendra Sahu — MIT License
