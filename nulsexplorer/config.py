# settings.py
import pathlib
import yaml

def get_defaults():
    return {
        'explorer': {
            'host': '127.0.0.1',
            'port': 8080,
            'secret': {'@required': True}
        },
        'nuls': {
          'host': '127.0.0.1',
          'port': 8001,
          'path': '/api/',
          'base_uri': 'http://127.0.0.1:8001/api/',
          'chain_id': 8964,
          'hash_switch_height': None
        },
        'mongodb': {
          'uri': 'mongodb://127.0.0.1:27006',
          'database': 'nuls'
        },
        'mail': {
            'email_sender': 'nuls@localhost.localdomain',
            'smtp_url': 'smtp://localhost'
        },
        'ipfs': {
            'enabled': True,
            'host': '127.0.0.1',
            'port': 5001
        }
    }
