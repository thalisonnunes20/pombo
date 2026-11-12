from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.core.cache import cache

User = get_user_model()

class SecurityBruteForceTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = Client()
        self.user = User.objects.create_user(
            username='admin_test',
            password='Password123!',
        )

    def test_brute_force_lockout_after_five_attempts(self):
        # 4 tentativas incorretas
        for i in range(4):
            response = self.client.post('/auth/login/', {
                'username': 'admin_test',
                'password': 'wrongpassword'
            })
            self.assertEqual(response.status_code, 200)

        # 5ª tentativa incorreta deve bloquear
        response = self.client.post('/auth/login/', {
            'username': 'admin_test',
            'password': 'wrongpassword'
        })
        self.assertEqual(response.status_code, 200)

        # 6ª tentativa bloqueada com HTTP 429
        response = self.client.post('/auth/login/', {
            'username': 'admin_test',
            'password': 'Password123!'
        })
        self.assertEqual(response.status_code, 429)

    def test_successful_login_resets_counter(self):
        # 2 falhas
        for i in range(2):
            self.client.post('/auth/login/', {'username': 'admin_test', 'password': 'wrong'})
        
        # Sucesso
        response = self.client.post('/auth/login/', {'username': 'admin_test', 'password': 'Password123!'})
        self.assertEqual(response.status_code, 302)

        # Próxima tentativa com senha correta funciona
        self.client.logout()
        response = self.client.post('/auth/login/', {'username': 'admin_test', 'password': 'Password123!'})
        self.assertEqual(response.status_code, 302)

    def test_remember_me_session_persistence(self):
        # Login sem remember_me: expira ao fechar navegador
        self.client.post('/auth/login/', {'username': 'admin_test', 'password': 'Password123!'})
        session = self.client.session
        self.assertTrue(session.get_expire_at_browser_close())

        # Login com remember_me: não expira ao fechar e dura 30 dias (2.592.000s)
        self.client.logout()
        self.client.post('/auth/login/', {'username': 'admin_test', 'password': 'Password123!', 'remember_me': 'true'})
        session = self.client.session
        self.assertFalse(session.get_expire_at_browser_close())
        self.assertEqual(session.get_expiry_age(), 60 * 60 * 24 * 30)

