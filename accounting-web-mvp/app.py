from flask import Flask, render_template, request, redirect, url_for, flash, send_file
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import func, CheckConstraint
import pandas as pd
import io
import datetime
import os

app = Flask(__name__)
app.secret_key = os.environ.get("APP_SECRET_KEY", "dev-secret")
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL", "sqlite:///app.db")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

# --- Models ---
class Company(db.Model):
    __tablename__ = "companies"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    nipt = db.Column(db.String(32))
    address = db.Column(db.String(255))

    accounts = db.relationship("Account", backref="company", cascade="all, delete-orphan")
    entries = db.relationship("JournalEntry", backref="company", cascade="all, delete-orphan")
    banktx = db.relationship("BankTransaction", backref="company", cascade="all, delete-orphan")


class Account(db.Model):
    __tablename__ = "accounts"
    id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.Integer, db.ForeignKey("companies.id"), nullable=False, index=True)
    code = db.Column(db.String(20), nullable=False)
    name = db.Column(db.String(200), nullable=False)
    type = db.Column(db.String(30), nullable=False)  # Asset, Liability, Equity, Income, Expense
    is_active = db.Column(db.Boolean, default=True)

    __table_args__ = (db.UniqueConstraint("company_id", "code", name="uq_company_code"),)


class JournalEntry(db.Model):
    __tablename__ = "journal_entries"
    id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.Integer, db.ForeignKey("companies.id"), nullable=False, index=True)
    date = db.Column(db.Date, nullable=False, index=True)
    description = db.Column(db.String(255))

    lines = db.relationship("JournalLine", backref="entry", cascade="all, delete-orphan")


class JournalLine(db.Model):
    __tablename__ = "journal_lines"
    id = db.Column(db.Integer, primary_key=True)
    entry_id = db.Column(db.Integer, db.ForeignKey("journal_entries.id"), nullable=False, index=True)
    account_id = db.Column(db.Integer, db.ForeignKey("accounts.id"), nullable=False, index=True)
    memo = db.Column(db.String(255))
    debit = db.Column(db.Numeric(14, 2), default=0)
    credit = db.Column(db.Numeric(14, 2), default=0)

    account = db.relationship("Account")


class BankTransaction(db.Model):
    __tablename__ = "bank_transactions"
    id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.Integer, db.ForeignKey("companies.id"), nullable=False, index=True)
    date = db.Column(db.Date, nullable=False, index=True)
    description = db.Column(db.String(255))
    amount = db.Column(db.Numeric(14,2), nullable=False)  # +deposit, -withdrawal
    account_id = db.Column(db.Integer, db.ForeignKey("accounts.id"))
    account = db.relationship("Account")


@app.before_first_request
def init_db():
    db.create_all()
    # Seed default account types if DB is empty
    if Company.query.count() == 0:
        demo = Company(name="Shembull SHPK", nipt="L12345678A", address="Elbasan")
        db.session.add(demo)
        db.session.flush()
        defaults = [
            ("1000", "Kasa", "Asset"),
            ("1010", "Banka", "Asset"),
            ("2000", "Detyrime", "Liability"),
            ("3000", "Kapitali", "Equity"),
            ("4000", "Të Ardhurat", "Income"),
            ("5000", "Shpenzimet", "Expense"),
        ]
        for code, name, typ in defaults:
            db.session.add(Account(company_id=demo.id, code=code, name=name, type=typ))
        db.session.commit()


# --- Routes ---
@app.route("/")
def index():
    companies = Company.query.order_by(Company.name).all()
    return render_template("index.html", companies=companies)


# Companies
@app.route("/companies", methods=["GET", "POST"])
def companies():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        nipt = request.form.get("nipt", "").strip()
        addr = request.form.get("address", "").strip()
        if not name:
            flash("Emri i subjektit është i detyrueshëm.", "danger")
        else:
            db.session.add(Company(name=name, nipt=nipt, address=addr))
            db.session.commit()
            flash("Subjekti u shtua.", "success")
        return redirect(url_for("companies"))
    items = Company.query.order_by(Company.name).all()
    return render_template("companies.html", items=items)


@app.route("/companies/<int:company_id>/delete", methods=["POST"])
def delete_company(company_id):
    c = Company.query.get_or_404(company_id)
    db.session.delete(c)
    db.session.commit()
    flash("Subjekti u fshi.", "warning")
    return redirect(url_for("companies"))


# Accounts
@app.route("/companies/<int:company_id>/accounts", methods=["GET", "POST"])
def accounts(company_id):
    company = Company.query.get_or_404(company_id)
    if request.method == "POST":
        code = request.form.get("code", "").strip()
        name = request.form.get("name", "").strip()
        typ = request.form.get("type", "").strip()
        if not (code and name and typ):
            flash("Kodi, emri dhe tipi janë të detyrueshëm.", "danger")
        else:
            db.session.add(Account(company_id=company.id, code=code, name=name, type=typ))
            try:
                db.session.commit()
                flash("Llogaria u shtua.", "success")
            except Exception as e:
                db.session.rollback()
                flash("Gabim: kodi i llogarisë duhet të jetë unik brenda subjektit.", "danger")
        return redirect(url_for("accounts", company_id=company.id))

    items = Account.query.filter_by(company_id=company.id, is_active=True).order_by(Account.code).all()
    return render_template("accounts.html", company=company, items=items)


@app.route("/companies/<int:company_id>/accounts/<int:account_id>/delete", methods=["POST"])
def delete_account(company_id, account_id):
    acct = Account.query.get_or_404(account_id)
    db.session.delete(acct)
    db.session.commit()
    flash("Llogaria u fshi.", "warning")
    return redirect(url_for("accounts", company_id=company_id))


# Journal entries
@app.route("/companies/<int:company_id>/entries", methods=["GET", "POST"])
def entries(company_id):
    company = Company.query.get_or_404(company_id)
    accounts = Account.query.filter_by(company_id=company.id).order_by(Account.code).all()

    if request.method == "POST":
        date = request.form.get("date")
        description = request.form.get("description", "").strip()
        lines = []
        # Expect arrays of account_id[], debit[], credit[], memo[]
        acct_ids = request.form.getlist("account_id")
        debits = request.form.getlist("debit")
        credits = request.form.getlist("credit")
        memos = request.form.getlist("memo")

        for i in range(len(acct_ids)):
            try:
                aid = int(acct_ids[i])
            except:
                continue
            d = float(debits[i]) if debits[i] else 0.0
            c = float(credits[i]) if credits[i] else 0.0
            m = memos[i].strip() if i < len(memos) else ""
            if d == 0 and c == 0:
                continue
            lines.append((aid, d, c, m))

        if not date or not lines:
            flash("Data dhe të paktën një rresht janë të detyrueshëm.", "danger")
            return redirect(url_for("entries", company_id=company.id))
        # Check balance
        total_d = sum(x[1] for x in lines)
        total_c = sum(x[2] for x in lines)
        if round(total_d, 2) != round(total_c, 2):
            flash("Shënimi nuk balancon: Debiti dhe Krediti duhet të jenë të barabartë.", "danger")
            return redirect(url_for("entries", company_id=company.id))

        je = JournalEntry(company_id=company.id, date=datetime.date.fromisoformat(date), description=description)
        db.session.add(je)
        db.session.flush()
        for aid, d, c, m in lines:
            db.session.add(JournalLine(entry_id=je.id, account_id=aid, debit=d, credit=c, memo=m))
        db.session.commit()
        flash("Shënimi u ruajt.", "success")
        return redirect(url_for("entries", company_id=company.id))

    items = JournalEntry.query.filter_by(company_id=company.id).order_by(JournalEntry.date.desc(), JournalEntry.id.desc()).all()
    # Preload totals
    totals = {}
    for je in items:
        sums = db.session.query(
            func.coalesce(func.sum(JournalLine.debit),0),
            func.coalesce(func.sum(JournalLine.credit),0)
        ).filter(JournalLine.entry_id == je.id).first()
        totals[je.id] = {"debit": float(sums[0]), "credit": float(sums[1])}
    return render_template("entries.html", company=company, accounts=accounts, items=items, totals=totals)


@app.route("/entries/<int:entry_id>/delete", methods=["POST"])
def delete_entry(entry_id):
    je = JournalEntry.query.get_or_404(entry_id)
    cid = je.company_id
    db.session.delete(je)
    db.session.commit()
    flash("Shënimi u fshi.", "warning")
    return redirect(url_for("entries", company_id=cid))


# Bank
@app.route("/companies/<int:company_id>/bank", methods=["GET", "POST"])
def bank(company_id):
    company = Company.query.get_or_404(company_id)
    accounts = Account.query.filter_by(company_id=company.id).order_by(Account.code).all()

    if request.method == "POST":
        date = request.form.get("date")
        desc = request.form.get("description","").strip()
        amount = request.form.get("amount")
        account_id = request.form.get("account_id")
        if not (date and amount):
            flash("Data dhe shuma janë të detyrueshme.", "danger")
        else:
            bt = BankTransaction(
                company_id=company.id,
                date=datetime.date.fromisoformat(date),
                description=desc,
                amount=float(amount),
                account_id=int(account_id) if account_id else None
            )
            db.session.add(bt)
            db.session.commit()
            flash("Transaksioni u ruajt.", "success")
        return redirect(url_for("bank", company_id=company.id))

    items = BankTransaction.query.filter_by(company_id=company.id).order_by(BankTransaction.date.desc(), BankTransaction.id.desc()).all()
    balance = sum([float(x.amount) for x in items])
    return render_template("bank.html", company=company, accounts=accounts, items=items, balance=balance)


@app.route("/bank/<int:tx_id>/delete", methods=["POST"])
def delete_bank(tx_id):
    tx = BankTransaction.query.get_or_404(tx_id)
    cid = tx.company_id
    db.session.delete(tx)
    db.session.commit()
    flash("Transaksioni u fshi.", "warning")
    return redirect(url_for("bank", company_id=cid))


# Reports
@app.route("/reports/trial_balance/<int:company_id>")
def trial_balance(company_id):
    company = Company.query.get_or_404(company_id)
    # Compute balance per account: debit - credit
    q = db.session.query(
        Account.id, Account.code, Account.name, Account.type,
        func.coalesce(func.sum(JournalLine.debit),0).label("debit"),
        func.coalesce(func.sum(JournalLine.credit),0).label("credit")
    ).join(JournalLine, JournalLine.account_id == Account.id, isouter=True)     .join(JournalEntry, JournalEntry.id == JournalLine.entry_id, isouter=True)     .filter(Account.company_id==company.id)     .group_by(Account.id)     .order_by(Account.code)
    rows = []
    for r in q:
        balance = float(r.debit) - float(r.credit)
        rows.append({
            "code": r.code, "name": r.name, "type": r.type,
            "debit_total": float(r.debit), "credit_total": float(r.credit),
            "balance": balance
        })
    return render_template("trial_balance.html", company=company, rows=rows)


@app.route("/export/trial_balance/<int:company_id>.xlsx")
def export_trial_balance(company_id):
    company = Company.query.get_or_404(company_id)
    q = db.session.query(
        Account.code.label("Kodi"),
        Account.name.label("Emri"),
        Account.type.label("Tipi"),
        func.coalesce(func.sum(JournalLine.debit),0).label("Debiti"),
        func.coalesce(func.sum(JournalLine.credit),0).label("Krediti")
    ).join(JournalLine, JournalLine.account_id == Account.id, isouter=True)     .join(JournalEntry, JournalEntry.id == JournalLine.entry_id, isouter=True)     .filter(Account.company_id==company.id)     .group_by(Account.id)     .order_by(Account.code)
    df = pd.read_sql(q.statement, db.session.bind)
    df["Bilanci"] = df["Debiti"] - df["Krediti"]
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Trial Balance")
    buf.seek(0)
    fname = f"trial_balance_{company.id}.xlsx"
    return send_file(buf, as_attachment=True, download_name=fname, mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


# CSV import for accounts
@app.route("/import/accounts/<int:company_id>", methods=["POST"])
def import_accounts(company_id):
    company = Company.query.get_or_404(company_id)
    file = request.files.get("file")
    if not file:
        flash("Ngarko një CSV me kolonat: code,name,type", "danger")
        return redirect(url_for("accounts", company_id=company.id))
    df = pd.read_csv(file)
    required = {"code","name","type"}
    if not required.issubset(set([c.lower() for c in df.columns])):
        flash("CSV duhet të ketë kolonat: code,name,type", "danger")
        return redirect(url_for("accounts", company_id=company.id))
    added = 0
    for _, row in df.iterrows():
        code = str(row.get("code"))
        name = str(row.get("name"))
        typ = str(row.get("type"))
        if code and name and typ:
            db.session.add(Account(company_id=company.id, code=code, name=name, type=typ))
            added += 1
    db.session.commit()
    flash(f"U importuan {added} llogari.", "success")
    return redirect(url_for("accounts", company_id=company.id))



# --- Helpers ---
def ensure_account(company_id:int, code:str, name:str=None, acc_type:str=None):
    a = Account.query.filter_by(company_id=company_id, code=code).first()
    if a:
        return a
    # Guess type by first digit if not provided
    if not acc_type and code and code[0].isdigit():
        first = int(code[0])
        acc_type = {1:"Asset",2:"Liability",3:"Equity",4:"Income",5:"Expense"}.get(first, "Expense")
    if not name:
        name = f"Llogari {code}"
    a = Account(company_id=company_id, code=code, name=name, type=acc_type or "Expense")
    db.session.add(a)
    db.session.flush()
    return a



# CSV import for journal entries (grouped by entry_ref)
# Expected columns (case-insensitive): entry_ref, date, description, account_code, debit, credit, memo
@app.route("/import/journal/<int:company_id>", methods=["POST"])
def import_journal(company_id):
    company = Company.query.get_or_404(company_id)
    file = request.files.get("file")
    if not file:
        flash("Ngarko CSV me kolonat: entry_ref,date,description,account_code,debit,credit,memo", "danger")
        return redirect(url_for("entries", company_id=company.id))
    df = pd.read_csv(file)
    # normalize columns
    cols = {c.lower(): c for c in df.columns}
    required = {"entry_ref","date","account_code","debit","credit"}
    if not required.issubset(set(cols.keys())):
        flash("Mungojnë kolonat e detyrueshme: entry_ref,date,account_code,debit,credit", "danger")
        return redirect(url_for("entries", company_id=company.id))

    created = 0
    for ref, grp in df.groupby(df[cols["entry_ref"]]):
        date_val = str(grp.iloc[0][cols["date"]])
        try:
            d = datetime.date.fromisoformat(date_val[:10])  # allow 'YYYY-MM-DD' or with time
        except Exception:
            try:
                d = datetime.datetime.strptime(date_val, "%d/%m/%Y").date()
            except Exception:
                flash(f"Data e pavlefshme: {date_val}", "danger")
                continue
        desc = str(grp.iloc[0][cols.get("description", cols["entry_ref"])])
        je = JournalEntry(company_id=company.id, date=d, description=desc)
        db.session.add(je)
        db.session.flush()
        for _, row in grp.iterrows():
            code = str(row[cols["account_code"]]).strip()
            acc = ensure_account(company.id, code)
            debit = float(row[cols["debit"]]) if str(row[cols["debit"]]).strip() not in ("","None","nan") else 0.0
            credit = float(row[cols["credit"]]) if str(row[cols["credit"]]).strip() not in ("","None","nan") else 0.0
            memo = str(row[cols["memo"]]) if "memo" in cols else ""
            db.session.add(JournalLine(entry_id=je.id, account_id=acc.id, memo=memo, debit=debit, credit=credit))
        created += 1
    db.session.commit()
    flash(f"U importuan {created} shënime ditari.", "success")
    return redirect(url_for("entries", company_id=company.id))


# CSV import for bank transactions
# Expected columns (case-insensitive): date, description, amount, account_code (optional)
@app.route("/import/bank/<int:company_id>", methods=["POST"])
def import_bank(company_id):
    company = Company.query.get_or_404(company_id)
    file = request.files.get("file")
    if not file:
        flash("Ngarko CSV me kolonat: date,description,amount,account_code (ops.)", "danger")
        return redirect(url_for("bank", company_id=company.id))
    df = pd.read_csv(file)
    cols = {c.lower(): c for c in df.columns}
    required = {"date","amount"}
    if not required.issubset(set(cols.keys())):
        flash("Mungojnë kolonat e detyrueshme: date,amount", "danger")
        return redirect(url_for("bank", company_id=company.id))

    created = 0
    for _, row in df.iterrows():
        date_val = str(row[cols["date"]])
        try:
            d = datetime.date.fromisoformat(date_val[:10])
        except Exception:
            try:
                d = datetime.datetime.strptime(date_val, "%d/%m/%Y").date()
            except Exception:
                continue
        desc = str(row[cols.get("description","")]) if "description" in cols else ""
        amount = float(row[cols["amount"]])
        account_id = None
        if "account_code" in cols and str(row[cols["account_code"]]).strip():
            acc = ensure_account(company.id, str(row[cols["account_code"]]).strip())
            account_id = acc.id
        bt = BankTransaction(company_id=company.id, date=d, description=desc, amount=amount, account_id=account_id)
        db.session.add(bt)
        created += 1
    db.session.commit()
    flash(f"U importuan {created} transaksione banke/kase.", "success")
    return redirect(url_for("bank", company_id=company.id))


if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 5000))
    host = os.environ.get("HOST", "127.0.0.1")
    app.run(debug=True, host=host, port=port)
