"""
    U9 A1: Proyecto Integrador

    Author: Eloy Uziel García Cisneros (eloy.garcia@edu.uag.mx)

    usage: from network import Network
"""

import socket
import logging
import rsa
import os
import hashlib

import struct


LOGGER = logging.getLogger(__name__)
PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))


CHUNK_SIZE = 4096
BUFF_SIZE = CHUNK_SIZE

class AuthError(Exception):
    pass

class Crypto:

    ENCODING = 'UTF-8'

    def __init__(self) -> None:
        self.key_pub, self.key_priv = rsa.newkeys(512)

    def encrypt(self, data, key_pub):
        return rsa.encrypt(data.encode(self.ENCODING), key_pub)

    def decrypt(self, data):
        return rsa.decrypt(data, self.key_priv).decode(self.ENCODING)

class User:

    def __init__(self, user, pwd) -> None:
        self.user = user
        self.hash = hashlib.sha256(pwd.encode('utf-8')).hexdigest()

class Network:

    ADDR = ('localhost', 20001)

    def __init__(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    
    def send_file(): {...}
    def get_file(): {...}

    def append_size(self, data):
        return struct.pack('Q', len(data)) + data
    
    
