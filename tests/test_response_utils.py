import unittest
from shared import response_utils

class TestResponseUtils(unittest.TestCase):
    def test_success_response(self):
        resp = response_utils.success_response({"foo": "bar"})
        self.assertEqual(resp["statusCode"], 200)
        self.assertIn("foo", resp["body"])

    def test_error_response(self):
        resp = response_utils.error_response("fail", 400)
        self.assertEqual(resp["statusCode"], 400)
        self.assertIn("fail", resp["body"])

if __name__ == "__main__":
    unittest.main()
