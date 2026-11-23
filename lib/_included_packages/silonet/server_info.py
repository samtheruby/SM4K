"""
Telling whether an address is a Silo server SM4K can talk to, before anyone signs in: GET /api/v2/system/info and
/api/v2/system/identity answer without credentials.
"""

from .client import Credentials, SiloClient
from .errors import SiloError, SiloIncompatible, SiloUnavailable

SUPPORTED_API_MAJOR = 2


class ServerInfo:
    def __init__(self, serverId, serverVersion, apiMajor, contractDigest):
        self.serverId = serverId
        self.serverVersion = serverVersion
        self.apiMajor = apiMajor
        self.contractDigest = contractDigest


def probe(baseUrl, device, session=None):
    """The server's ServerInfo. Raises SiloUnavailable when nothing answers, SiloIncompatible for anything else."""
    client = SiloClient(baseUrl, device, Credentials(), session=session)
    try:
        info = client.request('GET', '/api/v2/system/info', profile=False)
        if not isinstance(info, dict) or 'api_major' not in info:
            raise SiloIncompatible(0, 'not_silo', 'no api_major in /api/v2/system/info')
        version = info.get('server_version', '?')
        if info['api_major'] != SUPPORTED_API_MAJOR:
            raise SiloIncompatible(0, 'unsupported_api', f'API {info["api_major"]} on Silo {version}')
        identity = client.request('GET', '/api/v2/system/identity', profile=False)
        return ServerInfo(identity['server_id'], version, info['api_major'], info.get('contract_digest', ''))
    except (SiloUnavailable, SiloIncompatible):
        raise
    except (SiloError, ValueError, KeyError, TypeError) as e:
        raise SiloIncompatible(0, 'not_silo', type(e).__name__)
