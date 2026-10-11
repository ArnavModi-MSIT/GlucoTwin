"""One-click launcher checks use synthetic files and mocked network/models."""
from pathlib import Path
from unittest.mock import Mock, patch
import importlib.metadata
import errno
import io
import json
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import launch_dashboard as launcher


class LauncherTests(unittest.TestCase):
    def health(self, value):
        response = io.BytesIO(json.dumps(value).encode())
        response.status = 200
        return response

    def test_existing_server_requires_matching_workspace(self):
        root = Path('/synthetic/workspace')
        connection = Mock()
        opener = Mock()
        for identity, expected in [(launcher.workspace_id(root), True), ('another-workspace', False)]:
            opener.open.return_value = self.health({'app': 'GlucoTwin', 'workspace_id': identity})
            with patch.object(launcher, 'port_available', return_value=False), \
                    patch.object(launcher.socket, 'create_connection', return_value=connection), \
                    patch.object(launcher.urllib.request, 'build_opener', return_value=opener):
                if expected:
                    self.assertTrue(launcher.matching_server(8000, root))
                else:
                    with self.assertRaisesRegex(launcher.LaunchError, 'occupied by another server'):
                        launcher.matching_server(8000, root)
        self.assertEqual(connection.close.call_count, 2)

    def test_unused_port_skips_windows_connect_timeout(self):
        probe = Mock()
        context = Mock()
        context.__enter__ = Mock(return_value=probe)
        context.__exit__ = Mock(return_value=False)
        with patch.object(launcher.socket, 'socket', return_value=context), \
                patch.object(launcher.socket, 'create_connection', side_effect=TimeoutError) as connect, \
                patch.object(launcher.urllib.request, 'build_opener') as opener:
            self.assertFalse(launcher.matching_server(8000))
        probe.bind.assert_called_once_with(('127.0.0.1', 8000))
        context.__exit__.assert_called_once()
        connect.assert_not_called()
        opener.assert_not_called()

    def test_occupied_port_with_timeout_is_never_treated_as_free(self):
        probe = Mock()
        probe.bind.side_effect = OSError(errno.EADDRINUSE, 'Address in use')
        context = Mock()
        context.__enter__ = Mock(return_value=probe)
        context.__exit__ = Mock(return_value=False)
        with patch.object(launcher.socket, 'socket', return_value=context), \
                patch.object(launcher.socket, 'create_connection', side_effect=TimeoutError('timed out')):
            with self.assertRaisesRegex(launcher.LaunchError, 'occupied or unavailable'):
                launcher.matching_server(8000)

    def test_matching_reuse_skips_model_loading_and_obeys_no_browser(self):
        for no_browser in (False, True):
            with patch.object(launcher, 'matching_server', return_value=True), \
                    patch.object(launcher, 'check_dependencies') as dependencies, \
                    patch.object(launcher, 'open_dashboard') as browser, \
                    patch.object(launcher.importlib, 'import_module') as load:
                self.assertEqual(launcher.launch(no_browser=no_browser), 0)
                self.assertEqual(browser.call_count, 0 if no_browser else 1)
            dependencies.assert_not_called()
            load.assert_not_called()

    def test_missing_dependency_has_setup_command(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / 'requirements.txt').write_text(
                'numpy==2.2.6\npandas==2.3.3\nscikit-learn==1.7.2\njoblib==1.5.3\n')
            with patch.object(launcher.importlib.metadata, 'version', side_effect=importlib.metadata.PackageNotFoundError):
                with self.assertRaisesRegex(launcher.LaunchError, 'python -m pip install -r requirements.txt'):
                    launcher.check_dependencies(root)

    def test_preflight_fails_before_service_import(self):
        with patch.object(launcher, 'matching_server', return_value=False), \
                patch.object(launcher, 'check_dependencies', side_effect=launcher.LaunchError('dependencies missing')), \
                patch.object(launcher.importlib, 'import_module') as load:
            with self.assertRaisesRegex(launcher.LaunchError, 'dependencies missing'):
                launcher.launch(no_browser=True)
        load.assert_not_called()

    def test_missing_prepared_data_does_not_start_service(self):
        with tempfile.TemporaryDirectory() as folder:
            with patch.object(launcher, 'matching_server', return_value=False), \
                    patch.object(launcher, 'check_dependencies'), \
                    patch.object(launcher.importlib, 'import_module') as load:
                with self.assertRaisesRegex(launcher.LaunchError, 'Local dashboard files are missing'):
                    launcher.launch(no_browser=True, root=Path(folder))
            load.assert_not_called()

    def test_new_server_stays_foreground_and_closes_after_interrupt(self):
        service = Mock()
        server = service.ThreadingHTTPServer.return_value
        server.serve_forever.side_effect = KeyboardInterrupt
        with patch.object(launcher, 'matching_server', return_value=False), \
                patch.object(launcher, 'check_dependencies'), \
                patch.object(launcher, 'check_prepared_files'), \
                patch.object(launcher.importlib, 'import_module', return_value=service), \
                patch.object(launcher, 'open_dashboard') as browser:
            self.assertEqual(launcher.launch(8012, no_browser=True), 0)
        service.ThreadingHTTPServer.assert_called_once_with(('127.0.0.1', 8012), service.Handler)
        server.serve_forever.assert_called_once()
        server.server_close.assert_called_once()
        browser.assert_not_called()


if __name__ == '__main__':
    unittest.main()
