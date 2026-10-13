"""Explicit opt-in for checks requiring private datasets and fitted artifacts."""
import os
import unittest

local_only = unittest.skipUnless(
    os.environ.get('GLUCOTWIN_INTEGRATION') == '1',
    'Local data/artifacts required; set GLUCOTWIN_INTEGRATION=1 after preparation',
)
