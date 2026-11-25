import unittest

from bank import BankError, BankService


class BankTests(unittest.TestCase):
    def setUp(self):
        self.bank = BankService(":memory:")
        self.a = self.bank.create_account("Alice", "alice@example.com", "9876543210", "1234", "SAVINGS", "1000")
        self.b = self.bank.create_account("Bob", "bob@example.com", "9876543211", "4321", "CURRENT", "500")

    def tearDown(self):
        self.bank.close()

    def test_create_and_balance(self):
        self.assertEqual(self.bank.get_balance(self.a), 100000)

    def test_duplicate_email(self):
        with self.assertRaises(BankError):
            self.bank.create_account("Alice 2", "alice@example.com", "9876543299", "1234", "SAVINGS", "500")

    def test_deposit_withdraw(self):
        self.assertEqual(self.bank.deposit(self.a, "250.50"), 125050)
        self.assertEqual(self.bank.withdraw(self.a, "100"), 115050)

    def test_invalid_amounts(self):
        for bad in ("0", "-5", "abc", "10.999", "nan"):
            with self.assertRaises(BankError):
                self.bank.deposit(self.a, bad)

    def test_insufficient_and_min_balance(self):
        with self.assertRaises(BankError):
            self.bank.withdraw(self.a, "5000")
        with self.assertRaises(BankError):  # would drop below Rs. 500 minimum
            self.bank.withdraw(self.a, "600")
        self.bank.withdraw(self.b, "500")  # current account may reach zero
        self.assertEqual(self.bank.get_balance(self.b), 0)

    def test_transfer(self):
        self.bank.transfer(self.a, self.b, "200")
        self.assertEqual(self.bank.get_balance(self.a), 80000)
        self.assertEqual(self.bank.get_balance(self.b), 70000)
        with self.assertRaises(BankError):
            self.bank.transfer(self.a, self.a, "10")
        with self.assertRaises(BankError):
            self.bank.transfer(self.a, "0000000000", "10")

    def test_history(self):
        self.bank.deposit(self.a, "10")
        kinds = [t["txn_type"] for t in self.bank.history(self.a)]
        self.assertEqual(kinds, ["DEPOSIT", "OPENING"])

    def test_login_and_lockout(self):
        self.assertEqual(self.bank.login(self.a, "1234")["name"], "Alice")
        for _ in range(3):
            with self.assertRaises(BankError):
                self.bank.login(self.a, "0000")
        with self.assertRaises(BankError):  # locked even with right PIN
            self.bank.login(self.a, "1234")
        self.bank.unlock_account(self.a)
        self.assertEqual(self.bank.login(self.a, "1234")["name"], "Alice")

    def test_change_pin_and_close(self):
        self.bank.change_pin(self.b, "4321", "9999")
        self.bank.login(self.b, "9999")
        with self.assertRaises(BankError):  # balance not zero
            self.bank.close_account(self.b, "9999")
        self.bank.withdraw(self.b, "500")
        self.bank.close_account(self.b, "9999")
        with self.assertRaises(BankError):
            self.bank.login(self.b, "9999")

    def test_admin(self):
        self.assertTrue(self.bank.admin_login("admin", "admin123"))
        with self.assertRaises(BankError):
            self.bank.admin_login("admin", "wrong")
        self.assertEqual(self.bank.bank_summary()["active_accounts"], 2)


if __name__ == "__main__":
    unittest.main()
