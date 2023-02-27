"""
    U9 A1: Proyecto Integrador

    Author: Eloy Uziel García Cisneros (eloy.garcia@edu.uag.mx)

    usage: python node.py [-s]
"""

from client import Client
from server import Server
import argparse

import logging

logging.basicConfig(level='INFO')

# Initialize parser
PARSER = argparse.ArgumentParser()
# set argument to identify if process will run as message broker.
PARSER.add_argument("-s", "--server", action='store_true')
ARGS = PARSER.parse_args()


if ARGS.server:
    server = Server()
    server.start_server()

client = Client()
