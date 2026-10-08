import unittest

from services.permissions import (
    ActionCategory,
    PermissionManager,
    category_for_request,
    clear_session_approvals,
)
from services.verification import CommandVerifier


class PermissionPreferenceTests(unittest.TestCase):
    def tearDown(self):
        clear_session_approvals()

    def test_risky_requests_map_to_specific_permission_categories(self):
        self.assertEqual(
            category_for_request("Ayşe'ye WhatsApp mesaj gönder"),
            ActionCategory.MESSAGE_SEND,
        )
        self.assertEqual(
            category_for_request("dosya düzenle notes.txt"),
            ActionCategory.FILE_WRITE,
        )
        self.assertEqual(
            category_for_request("PowerShell komutunu çalıştır"),
            ActionCategory.CODE_EXEC,
        )
        for request in (
            "sistem ayarlarını değiştir",
            "ödeme yap",
            "işlemi sonlandır",
            "ağ bağlantısını kes",
            "programı kaldır",
        ):
            with self.subTest(request=request):
                self.assertTrue(CommandVerifier().inspect(request).requires_confirmation)
        self.assertIsNone(category_for_request("hava durumu nedir"))

    def test_preferences_are_validated_and_session_approvals_are_separate(self):
        settings = {}
        manager = PermissionManager(settings)
        category = ActionCategory.FILE_DELETE

        self.assertEqual(manager.get_preference(category), "always_ask")
        manager.set_preference(category, "session")
        self.assertFalse(manager.is_session_approved(category))
        manager.mark_session_approved(category)
        self.assertTrue(manager.is_session_approved(category))
        self.assertEqual(settings["perm_file_delete"], "session")
        with self.assertRaises(ValueError):
            manager.set_preference(category, "sometimes")


if __name__ == "__main__":
    unittest.main()
