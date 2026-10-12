"""Launch the synthetic demo and optional prepared research cohorts; never train or download."""
from pathlib import Path
import argparse
import errno
import hashlib
import importlib
import importlib.metadata
import importlib.util
import json
import socket
import sys
import urllib.error
import urllib.request
import webbrowser

ROOT = Path(__file__).resolve().parents[1]
RUNTIME_PACKAGES = {'numpy': 'numpy', 'pandas': 'pandas',
                    'scikit-learn': 'sklearn', 'joblib': 'joblib'}


class LaunchError(RuntimeError):
    """An actionable local setup or port error."""


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, response, code, message, headers, url):
        return None


def workspace_id(root):
    return hashlib.sha256(str(Path(root).resolve()).encode()).hexdigest()


def port_available(port):
    """Probe bindability; Windows can time out when connecting to a free port."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        # Windows permits overlapping binds unless exclusive use is requested.
        # Never let the probe report an existing listener's port as available.
        if hasattr(socket, 'SO_EXCLUSIVEADDRUSE'):
            probe.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        try:
            probe.bind(('127.0.0.1', port))
        except OSError as exc:
            if exc.errno in (errno.EADDRINUSE, errno.EACCES) or getattr(exc, 'winerror', None) in (10048, 10013):
                return False
            raise LaunchError(f'Cannot check localhost port {port}: {exc}') from exc
    return True


def matching_server(port, root=ROOT):
    """Return false for an unused port; refuse any nonmatching listener."""
    if port_available(port):
        return False
    try:
        connection = socket.create_connection(('127.0.0.1', port), timeout=1)
    except OSError as exc:
        raise LaunchError(f'Port {port} is occupied or unavailable and its server '
                          f'could not be verified: {exc}. Close the other server or '
                          f'run python scripts/launch_dashboard.py --port {port + 1 if port < 65535 else 8001}.') from exc
    connection.close()
    try:
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
        with opener.open(f'http://127.0.0.1:{port}/api/health', timeout=2) as response:
            payload = response.read(4097)
            if len(payload) > 4096:
                raise ValueError('Unexpected health response')
            value = json.loads(payload)
            if (response.status == 200 and isinstance(value, dict)
                    and value.get('app') == 'GlucoTwin'
                    and value.get('workspace_id') == workspace_id(root)):
                return True
    except (OSError, ValueError, urllib.error.URLError):
        pass
    raise LaunchError(f'Port {port} is occupied by another server. Close it or run '
                      f'python scripts/launch_dashboard.py --port {port + 1 if port < 65535 else 8001}.')


def check_dependencies(root=ROOT):
    pins = {}
    try:
        for line in (Path(root) / 'requirements.txt').read_text(encoding='utf-8').splitlines():
            if '==' in line and not line.lstrip().startswith('#'):
                name, version = line.strip().split('==', 1)
                pins[name] = version
    except (OSError, ValueError) as exc:
        raise LaunchError('Cannot read requirements.txt in the project directory.') from exc
    problems = []
    for name, module in RUNTIME_PACKAGES.items():
        expected = pins.get(name)
        if expected is None:
            problems.append(f'{name}: missing pinned requirement')
            continue
        try:
            actual = importlib.metadata.version(name)
            if importlib.util.find_spec(module) is None:
                problems.append(f'{name}: package cannot be imported')
            elif actual != expected:
                problems.append(f'{name}: found {actual}, requires {expected}')
        except (importlib.metadata.PackageNotFoundError, ImportError, ValueError):
            problems.append(f'{name}: not installed')
    if problems:
        raise LaunchError('Python dependencies need setup:\n  ' + '\n  '.join(problems)
                          + '\nFrom the project directory run:\n'
                            '  python -m pip install -r requirements.txt\n'
                            'Then run StartGlucoTwin.cmd again.')


def open_dashboard(url):
    try:
        opened = webbrowser.open(url, new=2)
    except (webbrowser.Error, OSError):
        opened = False
    if not opened:
        print(f'Open this address in your browser: {url}', flush=True)


def launch(port=8000, no_browser=False, root=ROOT):
    url = f'http://127.0.0.1:{port}/'
    if matching_server(port, root):
        print(f'GlucoTwin is already running: {url}', flush=True)
        if not no_browser:
            open_dashboard(url)
        return 0
    check_dependencies(root)
    # The synthetic replay needs no private datasets or fitted artifacts.
    for name in ('web/index.html','web/style.css','web/app.js'):
        if not (Path(root)/name).is_file():raise LaunchError(f'Missing application file: {name}')
    # Heavy dependencies and trusted local joblib files are loaded only now.
    sys.path.insert(0, str(Path(root) / 'scripts'))
    try:
        service = importlib.import_module('serve_dashboard')
    except Exception as exc:
        raise LaunchError(f'Prepared models could not be loaded: {exc}\n'
                          'Use the pinned requirements and locally generated model artifacts. '
                          'See docs/REPRODUCTION.md.') from exc
    try:
        server = service.ThreadingHTTPServer(('127.0.0.1', port), service.Handler)
    except OSError as exc:
        # Another click may have started the same workspace during preflight.
        if matching_server(port, root):
            if not no_browser:
                open_dashboard(url)
            return 0
        raise LaunchError(f'Cannot start localhost on port {port}: {exc}') from exc
    server.daemon_threads = True
    print(f'GlucoTwin: {url}\nKeep this window open. Press Ctrl+C to stop.', flush=True)
    try:
        if not no_browser:
            open_dashboard(url)
        server.serve_forever()
    except KeyboardInterrupt:
        print('\nGlucoTwin stopped.', flush=True)
    finally:
        server.server_close()
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=8000)
    parser.add_argument('--no-browser', action='store_true')
    args = parser.parse_args(argv)
    if not 1 <= args.port <= 65535:
        parser.error('--port must be between 1 and 65535')
    try:
        return launch(args.port, args.no_browser)
    except LaunchError as exc:
        print(f'GlucoTwin did not start:\n{exc}', file=sys.stderr, flush=True)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
