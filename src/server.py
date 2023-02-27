
"""
    U9 A1: Proyecto Integrador

    Author: Eloy Uziel García Cisneros (eloy.garcia@edu.uag.mx)

    usage: from server import Server
"""

from network import Network, AuthError, User, CHUNK_SIZE, BUFF_SIZE

import pickle
import logging
import os
import threading
import socket
import time
import struct

LOGGER = logging.getLogger(__name__)
PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))


class Server(Network):

    def __init__(self):
        super().__init__()
        self.sock.bind(self.ADDR)
        self.sock.listen(10)
        self.user_db = {}
        self.clients = {}
    
    def _login(self, cred: User):
        if hash := self.user_db.get(cred.user):
            if cred.hash ==  hash: return True
            raise AuthError('Invalid credentials.')
        return self._singup(cred)
        
    
    def _singup(self, cred: User):
        if cred.user in self.user_db:
            raise AuthError('User already in db.')
        self.user_db[cred.user] = cred.hash
        return True
    
    def _remove_client(self, user):
        del self.clients[user]
        self._boardcast()


    def _boardcast(self):
        LOGGER.info('broadcast pub keys')
        
        user_list = {usr: key['enc_key'] for usr, key in self.clients.items()}
        for user, u_data in self.clients.items():
            data = {'comm': user_list}
            try:
                data = pickle.dumps(data)
                u_data['conn'].send(self.append_size(data))
            except:
                del self.clients[user]

    def threaded_client(self, conn: socket.socket, addr):
        LOGGER.info('Waiting for client credentials')
        data = pickle.loads(conn.recv(1024))
        resp = {}
        try:
            LOGGER.info('Validating creds')
            self._login(data['cred'])
        except AuthError as err:
            LOGGER.warning('Unable to accept client.')
            resp['error'] = str(err)
            resp = pickle.dumps(resp)
            conn.send(resp)
            conn.close()
            return

        MYSELF = data['cred'].user
        threading.current_thread().setName(MYSELF)
        del data['cred']

        self.clients[MYSELF] = {'inbox': [], 'outbox': [], 'conn': conn, 'enc_key': data['enc_key']}
        data = {'msg': f"Welcome {MYSELF}"}
        data = pickle.dumps(data)

        LOGGER.info('client connected. Sending response.')
        conn.send(data)
        self._boardcast()

        while True:
            try:
                data = conn.recv(1024)
                decoded = pickle.loads(data)

                # Print decoded (NOT decrypted, can only be decripted by receiver.)
                LOGGER.info(decoded)

                if file_name := decoded.get('file'):
                    LOGGER.info('Sending ACK on file trans...')
                    data = pickle.dumps({'send_file': 'Server READY'})
                    self.clients[MYSELF]['conn'].sendall(self.append_size(data))

                    LOGGER.info('Retransmitting file..')
                    self.get_file(conn, self.clients[decoded['to']]['conn'], file_name, decoded['size'])

                    LOGGER.info('File transfer done.')
                    continue

                if decoded.get('stream'):
                    LOGGER.info('Sending ACK on video stream...')
                    # data = pickle.dumps({'start_stream': 'Server READY'})
                    # conn.sendall(data)

                    # Reach out to dest client
                    # data = pickle.dumps({'get_stream': True})
                    # self.clients[decoded['to']]['conn'].sendall(data)


                    self.get_stream(conn, self.clients[decoded['to']]['conn'])
                    continue

                # Send msg to receiver.
                self.clients[decoded['to']]['conn'].sendall(self.append_size(data))
            except (ConnectionResetError, EOFError):
                LOGGER.warning('Removing %s', MYSELF)
                self._remove_client(MYSELF)
                break
            except pickle.UnpicklingError:
                pass # Monstly control acks!
            except KeyError:
                pass
    
    def read_data(self, sock):
        data = b''
        tmp = sock.recv(CHUNK_SIZE)
        d_size = struct.unpack('Q', tmp[0:8])[0]
        data = tmp[8:]

        while len(data) < d_size:
            data += sock.recv(CHUNK_SIZE)

        return data

    def get_stream(self, conn_s, sock_r):
        LOGGER.info('Starting stream retransmition.')
        data = pickle.dumps({"get_stream": True})
        sock_r.sendall(self.append_size(data))

        time.sleep(3)

        data = pickle.dumps({'start_stream': 'Server READY'})
        conn_s.sendall(self.append_size(data))

        while True:
            # data = conn_s.recv(BUFF_SIZE)
            data = self.read_data(conn_s)
            if not data:
                break
            sock_r.sendall(self.append_size(data))

    
    def get_file(self, conn_s, sock_r, file_name, f_size):
        # Get the file name to receive
        #f_size, file_name = conn.recv(1024).decode('utf-8').split(',')
        LOGGER.info('Starting file retransmition.')
        data = pickle.dumps({"get_file": file_name, "size": f_size})
        sock_r.sendall(self.append_size(data))
        #_ = sock_r.recv(14)

        f_size = int(f_size)

        rec_count = 0
        LOGGER.info('Starting chunk retransmition.')
        while f_size > rec_count:
            chunk = conn_s.recv(CHUNK_SIZE)
            conn_s.send(b'ack')

            sock_r.send(chunk)

            rec_count += len(chunk)
        LOGGER.info('Chunks retransmitted.')


        LOGGER.info('%s: transfer completed!', file_name)

    
    def get_threads(self):
        return [(t.getName(), t.is_alive()) for t in threading.enumerate()]
    
    def _get_db(self):
        return self.user_db

    def console(self):
        while True:
            q = input('')

            func = {'/db': self._get_db,
                    '/active': self.clients.keys,
                    '/info': self.get_threads}
            
            LOGGER.info(func.get(q, lambda: f'available cmds: {func.keys()}')())


    def start_server(self):
        LOGGER.info('Starting server console.')
        th = threading.Thread(target=self.console, daemon=True, name='Console').start()

        LOGGER.info('Starting server, waiting for incomming conn.')
        while True:
            try:
                conn, addr = self.sock.accept()
                LOGGER.info('Client connected %s', addr)
                threading.Thread(target=self.threaded_client, args=(conn, addr), daemon=True).start()
            except KeyboardInterrupt:
                LOGGER.warning('Shutting down server.')
                self.sock.close()
