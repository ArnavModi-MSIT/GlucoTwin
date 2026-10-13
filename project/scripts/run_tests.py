"""Run Python and every JavaScript check with one command; no model fitting."""
import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--integration', action='store_true', help='Include prepared local-data/model checks')
    parser.add_argument('--node', help='Path to Node.js when it is not on PATH')
    args = parser.parse_args(argv)
    node = args.node or shutil.which('node')
    if not node:
        print('Node.js 22+ is required. Install Node or pass --node PATH.', file=sys.stderr)
        return 2
    try:
        version = subprocess.run([node, '--version'], capture_output=True, text=True, check=True)
        if int(version.stdout.strip().lstrip('v').split('.')[0]) < 22:
            raise ValueError('Node.js 22+ is required')
    except (OSError, ValueError, subprocess.SubprocessError):
        print('Cannot run Node.js 22+. Check PATH or --node.', file=sys.stderr)
        return 2
    env = os.environ.copy()
    if args.integration:
        env['GLUCOTWIN_INTEGRATION'] = '1'
    commands = [[sys.executable, '-m', 'unittest', 'discover', '-s', 'tests', '-v']]
    commands += [[node, '--check', str(p.relative_to(ROOT))] for p in sorted((ROOT/'web').glob('*.js'))]
    commands += [[node, str(p.relative_to(ROOT))] for p in sorted((ROOT/'tests').glob('*_unit.js'))]
    for command in commands:
        print('Running: ' + ' '.join(command[1:]), flush=True)
        try:
            code = subprocess.run(command, cwd=ROOT, env=env).returncode
        except OSError:
            print('Could not start a test process.', file=sys.stderr)
            return 2
        if code:
            return code
    print('Python tests, JavaScript syntax checks and unit suites passed.', flush=True)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
