"""
Tests for the deployment environment reported by /api/info.

Standalone like test_release: ``beacon_api.environment`` imports no Django, so
these run with plain unittest.

    python3 -m unittest beacon_api.test_environment -v
"""
import unittest

from beacon_api.environment import DEFAULT_ENVIRONMENT, resolve_environment


class ResolveEnvironmentTests(unittest.TestCase):
    def test_unset_keeps_the_production_default(self):
        # Existing production deployments set nothing and must keep reporting prod.
        self.assertEqual(resolve_environment(None), 'prod')
        self.assertEqual(DEFAULT_ENVIRONMENT, 'prod')

    def test_blank_is_treated_as_unset(self):
        self.assertEqual(resolve_environment(''), 'prod')
        self.assertEqual(resolve_environment('   '), 'prod')

    def test_each_spec_value_is_accepted(self):
        for value in ('prod', 'test', 'dev', 'staging'):
            self.assertEqual(resolve_environment(value), value)

    def test_case_and_whitespace_are_normalised(self):
        self.assertEqual(resolve_environment(' DEV '), 'dev')

    def test_an_unknown_value_is_refused_not_turned_into_prod(self):
        # A typo such as "development" must stop the service from starting.
        # Falling back to prod would label a dev server as production.
        for bad in ('development', 'production', 'qa', 'devv'):
            with self.assertRaises(ValueError) as ctx:
                resolve_environment(bad)
            self.assertIn(bad, str(ctx.exception))
            self.assertIn('prod', str(ctx.exception))  # names the allowed values


if __name__ == '__main__':
    unittest.main()
