"""Command-line interface for the Bank Management System."""
from getpass import getpass

from .services import BankError, BankService, money

LINE = "=" * 50


class CloseAccountDone(Exception):
    """Raised internally when the account was closed and the menu should exit."""


def ask(prompt: str) -> str:
    return input(prompt).strip()


def secret(prompt: str) -> str:
    try:
        return getpass(prompt)
    except Exception:  # some IDE consoles don't support getpass
        return input(prompt)


def header(title: str) -> None:
    print(f"\n{LINE}\n{title.center(50)}\n{LINE}")


def safe(action) -> None:
    """Run an action, printing BankError messages nicely."""
    try:
        action()
    except BankError as err:
        print(f"\n[!] {err}")
    except KeyboardInterrupt:
        print("\nCancelled.")


# ---------------- customer flows ----------------
def create_account(bank: BankService) -> None:
    header("OPEN NEW ACCOUNT")
    name = ask("Full name           : ")
    email = ask("Email              : ")
    phone = ask("Phone (10 digits)  : ")
    acc_type = ask("Type (SAVINGS/CURRENT) [SAVINGS]: ") or "SAVINGS"
    deposit = ask("Opening deposit (min Rs. 500): ")
    pin = secret("Set PIN (4-6 digits): ")
    if secret("Confirm PIN        : ") != pin:
        raise BankError("PINs do not match.")
    acc_no = bank.create_account(name, email, phone, pin, acc_type, deposit)
    print(f"\n[OK] Account created! Your account number is: {acc_no}")
    print("     Please remember it - you need it to log in.")


def print_statement(rows) -> None:
    header("MINI STATEMENT")
    if not rows:
        print("No transactions yet.")
        return
    print(f"{'Date (UTC)':<20}{'Type':<14}{'Amount':>14}{'Balance':>16}")
    print("-" * 64)
    for r in rows:
        print(f"{r['created_at']:<20}{r['txn_type']:<14}{money(r['amount']):>14}{money(r['balance_after']):>16}")


def customer_menu(bank: BankService, acc: dict) -> None:
    acc_no = acc["account_no"]
    print(f"\nWelcome, {acc['name']}!")
    while True:
        header(f"ACCOUNT {acc_no}")
        print("1. Check balance\n2. Deposit\n3. Withdraw\n4. Transfer\n"
              "5. Mini statement (last 10)\n6. Change PIN\n7. Close account\n8. Logout")
        choice = ask("\nChoose: ")
        if choice == "1":
            safe(lambda: print(f"\nBalance: {money(bank.get_balance(acc_no))}"))
        elif choice == "2":
            safe(lambda: print(f"\n[OK] New balance: {money(bank.deposit(acc_no, ask('Amount: ')))}"))
        elif choice == "3":
            safe(lambda: print(f"\n[OK] New balance: {money(bank.withdraw(acc_no, ask('Amount: ')))}"))
        elif choice == "4":
            def do_transfer():
                to = ask("Recipient account no: ")
                amt = ask("Amount: ")
                print(f"\n[OK] Transferred. New balance: {money(bank.transfer(acc_no, to, amt))}")
            safe(do_transfer)
        elif choice == "5":
            safe(lambda: print_statement(bank.history(acc_no)))
        elif choice == "6":
            def do_change():
                bank.change_pin(acc_no, secret("Current PIN: "), secret("New PIN: "))
                print("\n[OK] PIN changed.")
            safe(do_change)
        elif choice == "7":
            def do_close():
                if ask("Type YES to confirm closing the account: ").upper() == "YES":
                    bank.close_account(acc_no, secret("PIN: "))
                    print("\n[OK] Account closed.")
                    raise CloseAccountDone
            try:
                safe(do_close)
            except CloseAccountDone:
                return
        elif choice == "8":
            print("Logged out.")
            return
        else:
            print("Invalid choice.")


def customer_login(bank: BankService) -> None:
    header("CUSTOMER LOGIN")
    acc_no = ask("Account number: ")
    pin = secret("PIN: ")
    acc = bank.login(acc_no, pin)
    customer_menu(bank, acc)


# ---------------- admin flows ----------------
def admin_menu(bank: BankService) -> None:
    header("ADMIN LOGIN")
    bank.admin_login(ask("Username: "), secret("Password: "))
    while True:
        header("ADMIN PANEL")
        print("1. View all accounts\n2. Unlock an account\n3. Bank summary\n4. Back")
        choice = ask("\nChoose: ")
        if choice == "1":
            rows = bank.list_accounts()
            print(f"\n{'Acc No':<12}{'Name':<20}{'Type':<9}{'Balance':>16}  Status")
            print("-" * 66)
            for r in rows:
                status = "LOCKED" if r["locked"] else r["status"]
                print(f"{r['account_no']:<12}{r['name'][:18]:<20}{r['acc_type']:<9}{money(r['balance']):>16}  {status}")
        elif choice == "2":
            def do_unlock():
                bank.unlock_account(ask("Account number: "))
                print("\n[OK] Account unlocked.")
            safe(do_unlock)
        elif choice == "3":
            s = bank.bank_summary()
            print(f"\nActive accounts : {s['active_accounts']}")
            print(f"Total deposits  : {money(s['total_deposits'])}")
        elif choice == "4":
            return
        else:
            print("Invalid choice.")


# ---------------- entry point ----------------
def main() -> None:
    bank = BankService()
    try:
        while True:
            header("PYTHON BANK MANAGEMENT SYSTEM")
            print("1. Open new account\n2. Customer login\n3. Admin login\n4. Exit")
            choice = ask("\nChoose: ")
            if choice == "1":
                safe(lambda: create_account(bank))
            elif choice == "2":
                safe(lambda: customer_login(bank))
            elif choice == "3":
                safe(lambda: admin_menu(bank))
            elif choice == "4":
                print("Thank you for banking with us. Goodbye!")
                break
            else:
                print("Invalid choice.")
    except (KeyboardInterrupt, EOFError):
        print("\nGoodbye!")
    finally:
        bank.close()
