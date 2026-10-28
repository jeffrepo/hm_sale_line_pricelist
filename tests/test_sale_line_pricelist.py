from odoo import Command
from odoo.exceptions import ValidationError
from odoo.tests import Form, TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestSaleLinePricelist(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env.user.groups_id |= cls.env.ref("product.group_product_pricelist")
        cls.env.user.groups_id |= cls.env.ref("sale.group_discount_per_so_line")
        cls.partner = cls.env["res.partner"].create({"name": "HM Customer"})
        cls.product = cls.env["product.product"].create({
            "name": "HM Product", "list_price": 100, "taxes_id": [Command.clear()],
        })
        cls.retail = cls._pricelist("Retail", 100)
        cls.wholesale = cls._pricelist("Wholesale", 80)
        cls.env["product.pricelist.item"].create({
            "pricelist_id": cls.wholesale.id, "applied_on": "3_global",
            "min_quantity": 10, "compute_price": "fixed", "fixed_price": 60,
        })

    @classmethod
    def _pricelist(cls, name, price):
        return cls.env["product.pricelist"].create({
            "name": name, "currency_id": cls.env.company.currency_id.id,
            "item_ids": [Command.create({
                "applied_on": "3_global", "compute_price": "fixed", "fixed_price": price,
            })],
        })

    def _order(self):
        return self.env["sale.order"].create({
            "partner_id": self.partner.id, "pricelist_id": self.retail.id,
            "order_line": [
                Command.create({"product_id": self.product.id}),
                Command.create({"product_id": self.product.id, "line_pricelist_id": self.wholesale.id}),
            ],
        })

    def test_price_quantity_reset_and_update(self):
        order = self._order()
        regular, special = order.order_line
        self.assertEqual((regular.price_unit, special.price_unit), (100, 80))
        special.product_uom_qty = 10
        self.assertEqual(special.price_unit, 60)
        order.pricelist_id = self._pricelist("Other", 120)
        order.action_update_prices()
        self.assertEqual((regular.price_unit, special.price_unit), (120, 60))
        special.line_pricelist_id = False
        self.assertEqual(special.price_unit, 120)

    def test_manual_price_then_explicit_tariff(self):
        line = self._order().order_line[0]
        line.price_unit = 37
        line.product_uom_qty = 2
        self.assertEqual(line.price_unit, 37)
        line.line_pricelist_id = self.wholesale
        self.assertEqual(line.price_unit, 80)

    def test_form_selection_reprices(self):
        order = self._order()
        with Form(order) as form:
            with form.order_line.edit(0) as line:
                line.line_pricelist_id = self.wholesale
        self.assertEqual(order.order_line[0].price_unit, 80)

    def test_discount_and_invoice_values(self):
        percentage = self.env["product.pricelist"].create({
            "name": "Discount", "currency_id": self.env.company.currency_id.id,
            "item_ids": [Command.create({
                "applied_on": "3_global", "compute_price": "percentage", "percent_price": 25,
            })],
        })
        line = self._order().order_line[0]
        line.line_pricelist_id = percentage
        self.assertAlmostEqual(line.price_unit * (1 - line.discount / 100), 75)
        invoice_values = line._prepare_invoice_line()
        self.assertEqual(invoice_values["price_unit"], line.price_unit)
        self.assertEqual(invoice_values["discount"], line.discount)
        line.line_pricelist_id = self.wholesale
        self.assertEqual(line.discount, 0)

    def test_tax_included_price_keeps_native_calculation(self):
        tax = self.env["account.tax"].create({
            "name": "Included 20%", "amount": 20, "amount_type": "percent",
            "type_tax_use": "sale", "price_include_override": "tax_included",
        })
        self.product.taxes_id = tax
        order = self._order()
        line = order.order_line[1]
        self.assertAlmostEqual(line.price_total, 80, places=2)

    def test_copy_preserves_override(self):
        copied = self._order().copy()
        self.assertEqual(copied.order_line[1].line_pricelist_id, self.wholesale)
        self.assertEqual(copied.order_line[1].price_unit, 80)

    def test_no_matching_rule_uses_product_price(self):
        empty = self.env["product.pricelist"].create({
            "name": "No rules", "currency_id": self.env.company.currency_id.id,
        })
        line = self._order().order_line[1]
        line.line_pricelist_id = empty
        self.assertEqual(line.price_unit, 100)

    def test_unsaved_combo_components_follow_parent_tariff(self):
        combo = self.env["product.combo"].create({
            "name": "HM Combo Choice",
            "combo_item_ids": [Command.create({"product_id": self.product.id})],
        })
        product = self.env["product.product"].create({
            "name": "HM Combo", "type": "combo", "list_price": 100,
            "taxes_id": [Command.clear()], "combo_ids": [Command.link(combo.id)],
        })
        order = self.env["sale.order"].new({
            "partner_id": self.partner.id, "pricelist_id": self.retail.id,
            "order_line": [
                Command.create({"product_id": product.id, "virtual_id": "hm-combo"}),
                Command.create({
                    "product_id": self.product.id, "combo_item_id": combo.combo_item_ids.id,
                    "linked_virtual_id": "hm-combo",
                }),
            ],
        })
        parent, child = order.order_line
        child.linked_line_id = parent
        self.assertEqual(child.price_unit, 100)
        parent.line_pricelist_id = self.wholesale
        parent._onchange_line_pricelist_id()
        self.assertEqual(parent.price_unit, 0)
        self.assertEqual(child.price_unit, 80)

    def test_currency_rejected_on_line_and_order(self):
        other_currency = self.env["res.currency"].with_context(active_test=False).search([
            ("id", "!=", self.env.company.currency_id.id),
        ], limit=1)
        other_currency.active = True
        foreign = self.wholesale.copy({"currency_id": other_currency.id})
        order = self._order()
        with self.assertRaises(ValidationError), self.cr.savepoint():
            order.order_line[0].line_pricelist_id = foreign
        with self.assertRaises(ValidationError), self.cr.savepoint():
            order.pricelist_id = foreign

    def test_other_company_rejected(self):
        company = self.env["res.company"].create({"name": "Other HM Company"})
        foreign = self.wholesale.copy({"company_id": company.id})
        with self.assertRaises(ValidationError), self.cr.savepoint():
            self._order().order_line[0].line_pricelist_id = foreign

    def test_locked_order_rejected(self):
        order = self._order()
        order.locked = True
        with self.assertRaises(ValidationError), self.cr.savepoint():
            order.order_line[0].line_pricelist_id = self.wholesale
