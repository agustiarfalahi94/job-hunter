import unittest

from job_hunter.locations import city_options, fetch_malaysia_cities


class LocationsTest(unittest.TestCase):
    def test_fetch_malaysia_cities_reads_countriesnow_response(self):
        class Response:
            def raise_for_status(self):
                return None

            def json(self):
                return {"error": False, "data": ["Kuala Lumpur", "Petaling Jaya", "Ampang"]}

        cities = fetch_malaysia_cities(fetcher=lambda url, json, timeout: Response())

        self.assertEqual(cities, ("Kuala Lumpur", "Petaling Jaya", "Ampang"))

    def test_fetch_malaysia_cities_uses_fallback_on_error(self):
        cities = fetch_malaysia_cities(fetcher=lambda url, json, timeout: (_ for _ in ()).throw(RuntimeError("down")))

        self.assertIn("Kuala Lumpur", cities)
        self.assertIn("Petaling Jaya", cities)

    def test_city_options_filters_by_query_and_limits_results(self):
        cities = city_options("ku", cities=("Kuala Lumpur", "Kuantan", "Petaling Jaya"), limit=1)

        self.assertEqual(cities, ("Kuala Lumpur",))


if __name__ == "__main__":
    unittest.main()
