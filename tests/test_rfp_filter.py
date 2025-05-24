import types
import sys
from importlib import import_module

# rfp_filter imports process_rfp which depends on heavy modules. we can provide a dummy module to satisfy the import
class DummyProcessor:
    def process_rfp(self, path):
        return {}

sys.modules['process_rfp'] = types.ModuleType('process_rfp')
sys.modules['process_rfp'].RFPProcessor = DummyProcessor

rfp_filter = import_module('rfp_filter')


def test_get_dates_empty():
    assert rfp_filter.get_dates({}) == {"dates": []}


def test_get_dates_sort_and_clean():
    input_data = {
        'dates': [
            {'page': '2', 'event': 'B', 'date': '2024-01-02'},
            {'page': 1, 'event': 'A', 'date': '2024-01-01'},
            {'page': None, 'event': 'C', 'date': '2024-01-03'},
        ]
    }
    result = rfp_filter.get_dates(input_data)
    events = [d['event'] for d in result['dates']]
    assert events == ['C', 'A', 'B']


def test_get_dates_ignore_invalid():
    input_data = {
        'dates': [
            None,
            'invalid',
            {'event': 'Valid', 'date': '2024'},
        ]
    }
    result = rfp_filter.get_dates(input_data)
    assert result == {"dates": [{'page': 0, 'event': 'Valid', 'date': '2024', 'description': ''}]}


def test_get_requirements_filter():
    data = {
        'requirements': [
            {'category': 'Security', 'description': 'A'},
            {'category': 'Compliance', 'description': 'B'},
        ]
    }
    res = rfp_filter.get_requirements(data, 'Security')
    assert res == {"requirements": [{'category': 'Security', 'description': 'A'}]}

