# Accounting Web MVP (Flask + SQLite)

A lightweight web version of an accounting ledger to help migrate from a legacy Windows app.

## Features
- Multi-company support (Subjects)
- Chart of Accounts (Plan kontabël)
- Journal entries with multi-line debit/credit
- Bank/Cash transactions
- Trial Balance report
- Import/Export CSV (basic)
- SQLite database (`app.db`) for easy portability

## Quick Start (Windows)
1. Install Python 3.10+ from https://www.python.org/downloads/
2. Open **Command Prompt** in this folder.
3. Create a virtual env (optional but recommended):
   ```bat
   python -m venv .venv
   .venv\Scripts\activate
   ```
4. Install dependencies:
   ```bat
   pip install -r requirements.txt
   ```
5. Run the app:
   ```bat
   python app.py
   ```
6. Open http://127.0.0.1:5000

## Next Steps
- Upload your legacy DB schema or a CSV/SQL export for automated migration.
- We can switch to PostgreSQL later using the same models with minimal changes.
