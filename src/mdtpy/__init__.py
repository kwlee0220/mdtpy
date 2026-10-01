__version__ = "0.2.12"

# SSL 인증서 검증 경고 억제
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

from .instance import *
from .value import *
from .descriptor import *
from .exceptions import *
from .timeseries import *
from .ref import *
from .operation import *
from . import aas_misc as aas
from . import basyx
from .timeseries import *
from .utils import *
