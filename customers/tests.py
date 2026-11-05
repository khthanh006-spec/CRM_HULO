
from django.apps import apps
from django.test import SimpleTestCase


# =====================================================
# MODULE 5 - KIEM THU TICH HOP VOI MODULE 3
# =====================================================

class M3M5IntegrationTests(SimpleTestCase):

    def test_ticket_links_to_customer(self):
        """
        Kiem tra Ticket M3 lien ket voi Customer M5.
        """

        Ticket = apps.get_model('tickets', 'Ticket')
        Customer = apps.get_model('customers', 'Customer')

        field = Ticket._meta.get_field('khach_hang')

        self.assertIs(
            field.remote_field.model,
            Customer
        )

        self.assertEqual(
            field.remote_field.related_name,
            'tickets'
        )

    def test_ticket_has_csat_required_fields(self):
        """
        Kiem tra Ticket co du truong can thiet cho CSAT.
        """

        Ticket = apps.get_model('tickets', 'Ticket')

        required_fields = {
            'ma_ticket',
            'khach_hang',
            'trang_thai',
            'trang_thai_xac_nhan',
            'ket_qua_xu_ly',
            'thoi_diem_tao',
        }

        actual_fields = {
            field.name
            for field in Ticket._meta.get_fields()
        }

        self.assertTrue(
            required_fields.issubset(actual_fields)
        )


# =====================================================
# MODULE 5 - KIEM THU MODEL CSAT
# =====================================================

class CSATIntegrationTests(SimpleTestCase):

    def test_csat_links_to_ticket(self):
        """
        Kiem tra moi CSAT lien ket voi mot Ticket.
        """

        CSAT = apps.get_model('customers', 'CSAT')
        Ticket = apps.get_model('tickets', 'Ticket')

        field = CSAT._meta.get_field('ticket')

        self.assertTrue(
            field.one_to_one
        )

        self.assertIs(
            field.remote_field.model,
            Ticket
        )

    def test_csat_related_name(self):
        """
        Kiem tra ten lien ket nguoc tu Ticket sang CSAT.
        """

        CSAT = apps.get_model('customers', 'CSAT')

        field = CSAT._meta.get_field('ticket')

        self.assertEqual(
            field.remote_field.related_name,
            'csat'
        )
