"""Offline regression tests for the money, coupon, delivery and OTP safeguards."""

import os
import shutil
import sys
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace
from unittest.mock import patch


TEST_DATA_DIR = tempfile.mkdtemp(prefix="telegram-bot-regression-")
os.environ["BOT_TOKEN"] = "123456:OFFLINE_TEST_TOKEN"
os.environ["ADMIN_ID"] = "123456789"
os.environ["DATA_DIR"] = TEST_DATA_DIR
os.environ["RAILWAY_VOLUME_MOUNT_PATH"] = TEST_DATA_DIR
os.environ["BOT_DATA_ENCRYPTION_KEY"] = "offline-regression-test-key"
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_ROOT)

import main  # noqa: E402
import shop_integration as shop  # noqa: E402


class RegressionTests(unittest.TestCase):
    def setUp(self):
        with shop.conn() as c:
            for table in (
                "shop_coupon_usage",
                "shop_cart_coupon",
                "shop_transactions",
                "shop_deliveries",
                "shop_topups",
                "shop_order_items",
                "shop_orders",
                "shop_coupons",
                "shop_products",
                "user_streaks",
                "wallet",
            ):
                c.execute(f"DELETE FROM {table}")
            c.execute(
                """INSERT INTO shop_products
                   (product_id, name, category, price, stock, enabled, is_deleted)
                   VALUES ('P-1', 'Test item', 'Test', 10.00, 10, 1, 0)"""
            )
            c.execute(
                "INSERT INTO wallet (user_id, balance) VALUES (1001, 100.00)"
            )
            c.execute(
                "INSERT INTO wallet (user_id, balance) VALUES (1002, 100.00)"
            )

    def tearDown(self):
        pass

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(TEST_DATA_DIR, ignore_errors=True)

    @staticmethod
    def _order_payload(user_id=1001, coupon="", quoted_price=10.00, total=10.00):
        return {
            "items": [{
                "product_id": "P-1",
                "name": "Test item",
                "qty": 1,
                "unit_price": quoted_price,
                "subtotal": quoted_price,
            }],
            "subtotal": quoted_price,
            "discount": 0,
            "total": total,
            "coupon": coupon,
        }

    def test_topup_credit_is_once_and_cents_are_rounded(self):
        self.assertEqual(shop._round_money("2.675"), 2.68)
        self.assertEqual(main._round_money("12.345"), 12.35)
        with shop.conn() as c:
            c.execute(
                "INSERT INTO shop_topups (user_id, amount, reference) VALUES (1001, 12.345, 'trx')"
            )
            topup_id = c.execute("SELECT last_insert_rowid()").fetchone()[0]
        first = shop.process_topup_request(topup_id, "approve", 123456789)
        second = shop.process_topup_request(topup_id, "approve", 123456789)
        self.assertEqual(first["status"], "processed")
        self.assertEqual(first["amount"], 12.35)
        self.assertEqual(second["status"], "already_processed")
        self.assertEqual(shop.user_balance(1001), 112.35)
        with shop.conn() as c:
            self.assertEqual(
                c.execute(
                    "SELECT COUNT(*) FROM shop_transactions WHERE note LIKE 'Topup #% approved%'"
                ).fetchone()[0],
                1,
            )

    def test_topup_notification_falls_back_to_admin_dm(self):
        with patch.object(shop, "_forward_shop_request", return_value=None), patch.object(
            shop, "send", return_value=object()
        ) as send:
            route = shop._notify_topup_admin("new request", reply_markup="buttons")
        self.assertEqual(route, "admin")
        send.assert_called_once_with(
            shop.ADMIN_ID, "new request", reply_markup="buttons"
        )

    def test_coupon_start_expiry_global_and_per_user_limits(self):
        now = shop.now_ts()
        with shop.conn() as c:
            c.execute(
                """INSERT INTO shop_coupons
                   (code, discount_type, discount_value, start_at, expiry_at)
                   VALUES ('FUTURE', 'PERCENT', 10, ?, 0)""",
                (now + 3600,),
            )
            c.execute(
                """INSERT INTO shop_coupons
                   (code, discount_type, discount_value, expiry_at)
                   VALUES ('EXPIRED', 'PERCENT', 10, ?)""",
                (now - 1,),
            )
            c.execute(
                """INSERT INTO shop_coupons
                   (code, discount_type, discount_value, max_usage, used_count)
                   VALUES ('GLOBAL', 'PERCENT', 10, 1, 1)"""
            )
            c.execute(
                """INSERT INTO shop_coupons
                   (code, discount_type, discount_value, per_user_limit)
                   VALUES ('PERUSER', 'PERCENT', 10, 1)"""
            )
            c.execute(
                "INSERT INTO shop_coupon_usage (code, user_id) VALUES ('PERUSER', 1001)"
            )

        for code in ("FUTURE", "EXPIRED", "GLOBAL", "PERUSER"):
            ok, _, discount = shop.validate_coupon(code, 1001, 10)
            self.assertFalse(ok, code)
            self.assertEqual(discount, 0.0)

    def test_expired_coupon_cannot_be_used_at_checkout(self):
        with shop.conn() as c:
            c.execute(
                """INSERT INTO shop_coupons
                   (code, discount_type, discount_value, expiry_at)
                   VALUES ('EXPIRED', 'PERCENT', 10, ?)""",
                (shop.now_ts() - 1,),
            )
        user = SimpleNamespace(id=1001, username="buyer")
        order_id, error = shop.place_order(
            user, 1001, self._order_payload(coupon="EXPIRED", total=9.0)
        )
        self.assertIsNone(order_id)
        self.assertIn("মেয়াদ", error)
        self.assertEqual(shop.user_balance(1001), 100.0)
        with shop.conn() as c:
            self.assertEqual(c.execute("SELECT stock FROM shop_products WHERE product_id='P-1'").fetchone()[0], 10)

    def test_order_rejects_stale_price_then_accepts_current_invoice(self):
        with shop.conn() as c:
            c.execute("UPDATE shop_products SET price=12.00 WHERE product_id='P-1'")
        user = SimpleNamespace(id=1001, username="buyer")
        order_id, error = shop.place_order(
            user, 1001, self._order_payload(quoted_price=10.00, total=10.00)
        )
        self.assertIsNone(order_id)
        self.assertIn("দাম বদলেছে", error)
        self.assertEqual(shop.user_balance(1001), 100.0)

        order_id, error = shop.place_order(
            user, 1001, self._order_payload(quoted_price=12.00, total=12.00)
        )
        self.assertIsNotNone(order_id, error)
        self.assertEqual(shop.user_balance(1001), 88.0)
        with shop.conn() as c:
            self.assertEqual(c.execute("SELECT stock FROM shop_products WHERE product_id='P-1'").fetchone()[0], 9)

    def test_coupon_global_limit_is_enforced_inside_concurrent_checkout(self):
        with shop.conn() as c:
            c.execute(
                """INSERT INTO shop_coupons
                   (code, discount_type, discount_value, max_usage, per_user_limit)
                   VALUES ('ONCE', 'PERCENT', 10, 1, 1)"""
            )
        users = [
            SimpleNamespace(id=1001, username="buyer1"),
            SimpleNamespace(id=1002, username="buyer2"),
        ]
        payloads = [
            self._order_payload(coupon="ONCE", total=9.0),
            self._order_payload(coupon="ONCE", total=9.0),
        ]
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(
                pool.map(
                    lambda args: shop.place_order(args[0], args[0].id, args[1]),
                    zip(users, payloads),
                )
            )
        self.assertEqual(sum(order_id is not None for order_id, _ in results), 1)
        with shop.conn() as c:
            self.assertEqual(c.execute("SELECT used_count FROM shop_coupons WHERE code='ONCE'").fetchone()[0], 1)
            self.assertEqual(c.execute("SELECT COUNT(*) FROM shop_coupon_usage WHERE code='ONCE'").fetchone()[0], 1)

    def test_duplicate_cart_lines_cannot_oversell_stock(self):
        user = SimpleNamespace(id=1001, username="buyer")
        payload = {
            "items": [
                {"product_id": "P-1", "name": "Test item", "qty": 2, "unit_price": 10, "subtotal": 20},
                {"product_id": "P-1", "name": "Test item", "qty": 2, "unit_price": 10, "subtotal": 20},
            ],
            "subtotal": 40,
            "discount": 0,
            "total": 40,
            "coupon": "",
        }
        with shop.conn() as c:
            c.execute("UPDATE shop_products SET stock=3 WHERE product_id='P-1'")
        order_id, error = shop.place_order(user, 1001, payload)
        self.assertIsNone(order_id)
        self.assertIn("স্টক", error)
        self.assertEqual(shop.user_balance(1001), 100.0)

    def test_refund_is_atomic_and_only_applied_once_under_race(self):
        with shop.conn() as c:
            c.execute("INSERT INTO shop_orders (order_id, user_id, total, order_status) VALUES ('R-1', 1001, 9.99, 'PROCESSING')")
        with ThreadPoolExecutor(max_workers=6) as pool:
            results = list(pool.map(lambda _: shop.refund_order_atomic("R-1", 123456789), range(6)))
        self.assertEqual(sum(result["status"] == "refunded" for result in results), 1)
        self.assertEqual(shop.user_balance(1001), 109.99)
        with shop.conn() as c:
            self.assertEqual(c.execute("SELECT COUNT(*) FROM shop_transactions WHERE order_id='R-1' AND kind='CREDIT'").fetchone()[0], 1)
            self.assertEqual(c.execute("SELECT payment_status FROM shop_orders WHERE order_id='R-1'").fetchone()[0], "REFUNDED")

    def test_delivery_claim_serializes_sends_and_uncertainty_requires_admin_recovery(self):
        with shop.conn() as c:
            c.execute("INSERT INTO shop_orders (order_id, user_id, total, order_status, delivery_status) VALUES ('D-1', 1001, 5, 'PROCESSING', 'NOT_DELIVERED')")
        with ThreadPoolExecutor(max_workers=2) as pool:
            claims = list(pool.map(lambda _: shop.claim_order_delivery("D-1"), range(2)))
        self.assertEqual(sum(item["status"] == "claimed" for item in claims), 1)
        self.assertTrue(shop.finish_order_delivery("D-1", delivered=False))
        self.assertEqual(shop.claim_order_delivery("D-1")["status"], "claimed")
        shop.mark_order_delivery_uncertain("D-1")
        self.assertEqual(shop.claim_order_delivery("D-1")["status"], "uncertain")
        self.assertTrue(shop.recover_uncertain_delivery("D-1"))
        self.assertEqual(shop.claim_order_delivery("D-1")["status"], "claimed")
        self.assertTrue(shop.finish_order_delivery("D-1", delivered=True))
        self.assertEqual(shop.claim_order_delivery("D-1")["status"], "not_deliverable")

    def test_unconfirmed_telegram_send_blocks_automatic_redelivery(self):
        with shop.conn() as c:
            c.execute("INSERT INTO shop_orders (order_id, user_id, total, order_status, delivery_status) VALUES ('D-2', 1001, 5, 'PROCESSING', 'NOT_DELIVERED')")
        key = shop._skey(shop.ADMIN_ID, shop.ADMIN_ID)
        shop.shop_states[key] = {"step": "adm_deliver_text", "order_id": "D-2"}
        admin_message = SimpleNamespace(
            from_user=SimpleNamespace(id=shop.ADMIN_ID),
            chat=SimpleNamespace(id=shop.ADMIN_ID),
            text="license-key",
        )
        attempted_user_sends = []

        def fake_send(destination, text, **kwargs):
            if destination == 1001:
                attempted_user_sends.append((destination, text))
                return None  # Telegram did not confirm whether it accepted the send.
            return object()

        with patch.object(shop, "send", side_effect=fake_send):
            shop._handle_all_text_impl(admin_message)
        with shop.conn() as c:
            self.assertEqual(c.execute("SELECT delivery_status FROM shop_orders WHERE order_id='D-2'").fetchone()[0], "DELIVERY_UNCERTAIN")

        shop.shop_states[key] = {"step": "adm_deliver_text", "order_id": "D-2"}
        with patch.object(shop, "send", side_effect=fake_send):
            shop._handle_all_text_impl(admin_message)
        self.assertEqual(len(attempted_user_sends), 1)

    def test_database_has_new_indexes_and_incremental_vacuum_setting(self):
        with main.get_conn() as c:
            self.assertEqual(c.execute("PRAGMA auto_vacuum").fetchone()[0], 2)
            index_names = {
                row[0] for row in c.execute(
                    "SELECT name FROM sqlite_master WHERE type='index'"
                ).fetchall()
            }
        self.assertIn("idx_otps_user_time", index_names)
        self.assertIn("idx_order_items_order", index_names)
        self.assertIn("idx_topups_status_id", index_names)

    def test_source_group_never_matches_an_otp_code_as_phone_suffix(self):
        allocations = [
            {"id": 1, "number": "8801712345123"},
            {"id": 2, "number": "8801912345123"},
        ]
        message = SimpleNamespace(text="Your OTP code is 456123", message_id=77)
        with patch.object(main, "_iter_active_allocations_batches", return_value=iter([allocations])), patch.object(
            main, "_deliver_otp"
        ) as deliver:
            main.handle_otp_source_group(message)
        deliver.assert_not_called()

    def test_source_group_never_matches_a_long_otp_as_a_national_phone_suffix(self):
        allocations = [{"id": 1, "number": "8801712345678"}]
        message = SimpleNamespace(text="Your verification code is 171234567", message_id=80)
        with patch.object(main, "_iter_active_allocations_batches", return_value=iter([allocations])), patch.object(
            main, "_deliver_otp"
        ) as deliver:
            main.handle_otp_source_group(message)
        deliver.assert_not_called()

    def test_source_group_requires_unique_phone_or_explicit_unique_masked_suffix(self):
        active = [
            {"id": 1, "number": "8801712345123"},
            {"id": 2, "number": "8801912345123"},
        ]
        ambiguous = SimpleNamespace(text="Phone ending in 123; code 456789", message_id=78)
        with patch.object(main, "_iter_active_allocations_batches", return_value=iter([active])), patch.object(
            main, "_deliver_otp"
        ) as deliver:
            main.handle_otp_source_group(ambiguous)
        deliver.assert_not_called()

        unique = [active[0]]
        explicit = SimpleNamespace(text="Phone number ending in 123; code 456789", message_id=79)
        with patch.object(main, "_iter_active_allocations_batches", return_value=iter([unique])), patch.object(
            main, "_deliver_otp"
        ) as deliver:
            main.handle_otp_source_group(explicit)
        deliver.assert_called_once()
        self.assertEqual(deliver.call_args.args[0]["id"], 1)

    def test_source_group_accepts_a_unique_full_phone_number(self):
        active = [{"id": 1, "number": "8801712345678"}]
        message = SimpleNamespace(
            text="SMS for +880 1712-345678: verification code 456789",
            message_id=81,
        )
        with patch.object(main, "_iter_active_allocations_batches", return_value=iter([active])), patch.object(
            main, "_deliver_otp"
        ) as deliver:
            main.handle_otp_source_group(message)
        deliver.assert_called_once()
        self.assertEqual(deliver.call_args.args[0]["id"], 1)

    def test_api_number_duplicate_allocations_are_skipped_as_ambiguous(self):
        allocs = [
            {"id": 1, "number": "8801712345678"},
            {"id": 2, "number": "9901712345678"},
        ]
        otp = [{"number": "12345678", "full_message": "Your code is 456789", "otp_id": "api-1"}]
        with patch.object(main, "_auto_forward_panel_sms"), patch.object(
            main, "_iter_active_allocations_batches", return_value=iter([allocs])
        ), patch.object(main, "_deliver_otp_api") as deliver:
            main._deliver_panel_otps("test", otp, 1_800_000_000, 1200, 2)
        deliver.assert_not_called()

    def test_otp_success_keeps_code_history_without_persisting_raw_body(self):
        user_id = 2001
        with main.get_conn() as c:
            c.execute(
                "INSERT OR IGNORE INTO users (id, first_name, username) VALUES (?, 'Test', 'test_user')",
                (user_id,),
            )
            c.execute("INSERT OR IGNORE INTO wallet (user_id) VALUES (?)", (user_id,))
            c.execute(
                """INSERT INTO allocations
                   (user_id, number, service_name, country_name, country_flag, country_code)
                   VALUES (?, '8801712345678', 'Test service', 'Bangladesh', '🇧🇩', '+880')""",
                (user_id,),
            )
            allocation_id = c.execute("SELECT last_insert_rowid()").fetchone()[0]
        allocation = {
            "id": allocation_id,
            "user_id": user_id,
            "number": "8801712345678",
            "service_name": "Test service",
            "country_name": "Bangladesh",
            "country_flag": "🇧🇩",
            "country_code": "+880",
        }
        raw_body = "Your secure code is 481926. Do not share this message."
        with patch.object(main.bot, "send_message", return_value=object()) as telegram_send, patch.object(
            main, "_forward_otp"
        ), patch.object(main, "_notify_admin_live_otp"):
            self.assertTrue(
                main._deliver_otp_api(
                    allocation, raw_body, "2026-10-04 00:00:00",
                    "regression-otp-hash", "test",
                )
            )
            self.assertFalse(
                main._deliver_otp_api(
                    allocation, raw_body, "2026-10-04 00:00:00",
                    "regression-otp-hash", "test",
                )
            )
        with main.get_conn() as c:
            self.assertEqual(
                c.execute("SELECT otp_text FROM allocations WHERE id=?", (allocation_id,)).fetchone()[0],
                "",
            )
            history = c.execute(
                "SELECT message, otp_code FROM otps WHERE msg_hash='regression-otp-hash'"
            ).fetchone()
            self.assertEqual(history["message"], "")
            self.assertEqual(history["otp_code"], "481926")
            self.assertEqual(c.execute("SELECT total_otp FROM wallet WHERE user_id=?", (user_id,)).fetchone()[0], 1)
        self.assertEqual(telegram_send.call_count, 1)


if __name__ == "__main__":
    try:
        unittest.main()
    finally:
        shutil.rmtree(TEST_DATA_DIR, ignore_errors=True)