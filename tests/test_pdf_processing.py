import sys
import types
from importlib import import_module
from unittest import mock

# Provide lightweight mocks for external dependencies before import
class SessionState(dict):
    __getattr__ = dict.get

fake_st = types.SimpleNamespace(session_state=SessionState())
sys.modules['streamlit'] = fake_st

for name in ['boto3', 'botocore', 'requests', 'requests_aws4auth', 'openai']:
    sys.modules[name] = types.ModuleType(name)
    if name == 'openai':
        sys.modules[name].OpenAI = object

# dummy modules used by pdf_processing
sys.modules['upload_pdf'] = types.ModuleType('upload_pdf')
sys.modules['process_rfp'] = types.ModuleType('process_rfp')
storage_module = types.ModuleType('rfp_app.storage')
storage_module.get_cached_analysis = lambda *args, **kwargs: None
storage_module.store_analysis_result = lambda *args, **kwargs: None
sys.modules['rfp_app.storage'] = storage_module

# create dummy reportlab structure
reportlab = types.ModuleType('reportlab')
reportlab.lib = types.ModuleType('reportlab.lib')
reportlab.lib.pagesizes = types.ModuleType('reportlab.lib.pagesizes')
reportlab.lib.pagesizes.letter = None
reportlab.platypus = types.ModuleType('reportlab.platypus')
reportlab.platypus.SimpleDocTemplate = object
reportlab.platypus.Paragraph = object
reportlab.platypus.Spacer = object
reportlab.platypus.Table = object
reportlab.platypus.TableStyle = object
reportlab.platypus.Image = object
reportlab.lib.styles = types.ModuleType('reportlab.lib.styles')
reportlab.lib.styles.getSampleStyleSheet = lambda: {}
reportlab.lib.styles.ParagraphStyle = object
reportlab.lib.colors = types.SimpleNamespace(blue=0,darkblue=0,lightgrey=0,lightblue=0,whitesmoke=0)
reportlab.lib.units = types.ModuleType('reportlab.lib.units')
reportlab.lib.units.inch = 1
sys.modules['reportlab'] = reportlab
sys.modules['reportlab.lib'] = reportlab.lib
sys.modules['reportlab.lib.pagesizes'] = reportlab.lib.pagesizes
sys.modules['reportlab.platypus'] = reportlab.platypus
sys.modules['reportlab.lib.styles'] = reportlab.lib.styles
sys.modules['reportlab.lib.colors'] = types.ModuleType('reportlab.lib.colors')
sys.modules['reportlab.lib.colors'].blue = 0
sys.modules['reportlab.lib.colors'].darkblue = 0
sys.modules['reportlab.lib.colors'].lightgrey = 0
sys.modules['reportlab.lib.colors'].lightblue = 0
sys.modules['reportlab.lib.colors'].whitesmoke = 0
sys.modules['reportlab.lib.units'] = reportlab.lib.units

pdf_processing = import_module('rfp_app.pdf_processing')


def test_calculate_document_hash():
    data = b'example'
    expected = __import__('hashlib').sha256(data).hexdigest()
    assert pdf_processing.calculate_document_hash(data) == expected


def test_generate_report_filename_with_user():
    ts = mock.Mock()
    ts.strftime.return_value = '20240101_000000'
    with mock.patch('rfp_app.pdf_processing.datetime') as dt, \
         mock.patch('getpass.getuser', return_value='tester'):
        dt.now.return_value = ts
        dt.now.return_value.strftime.return_value = '20240101_000000'
        pdf_processing.st.session_state = SessionState({'user': {'fullname': 'John Doe'}})
        filename = pdf_processing.generate_report_filename('proposal.pdf', 'gpt-4')
    assert filename.startswith('RFP_Analysis_proposal_gpt4_John_Doe_20240101_000000')
    pdf_processing.st.session_state.clear()


