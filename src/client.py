
"""
    U9 A1: Proyecto Integrador

    Author: Eloy Uziel García Cisneros (eloy.garcia@edu.uag.mx)

    usage: from client import Client
"""

from network import Network, Crypto, User, CHUNK_SIZE, BUFF_SIZE
import threading
import logging
import pickle
import getpass
import os
import json
from tqdm import tqdm
import numpy as np
import cv2 as cv
import time
import queue
import imutils
import struct
from termcolor import colored


LOGGER = logging.getLogger(__name__)
PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))

SRC_DIR = os.path.join(PROJECT_DIR, 'from')
TRGT_DIR = os.path.join(PROJECT_DIR, 'to')



EMOJI = {':)': u'😀',
         ':(': u'🙁',
         '(L)': u'♥️ ',
         '(8)': u'🎵',
         ':[': u'🧛‍♂️',
         '(K)': u'💋',
         ':baba:': u'🤤'}

class Client(Network):

    def __init__(self):
        super().__init__()
        self.keys = Crypto()
        self._init_user()
        self._login()
        self.active_users = {}

        self.file_q = []
        self.file_st = []

        self.queue = queue.Queue(maxsize=10)

        self.rendering = False

        # Start listener
        LOGGER.info('starting listener.')
        threading.Thread(target=self.receive, daemon=True, name='Listener').start()

        # Main Thread
        self.send()
    
    def _init_user(self):
        print('Sign-in/Sign-up.. Press ENTER when done.')
        user = input('USER: ')
        pwd = getpass.getpass('PWD: ')
        self.user_data = User(user, pwd)
    
    def _login(self):
        self.sock.connect(self.ADDR)
        LOGGER.info('Connected to server.')
    
        data = {'cred': self.user_data, 'enc_key': self.keys.key_pub}

        LOGGER.info('Sending cred data.')
        self.sock.sendall(pickle.dumps(data))

        LOGGER.info('Waiting for server response.')
        resp = pickle.loads(self.sock.recv(1024))
        if err := resp.get('error'):
            print(err)
            self.sock.close()
            quit()
        LOGGER.info(resp)
    
    def list_files(self, *kargs):
        self.files = {id_: file for id_, file in enumerate(os.listdir(SRC_DIR))}
        return json.dumps(self.files, indent=4)

    
    def send_file(self):
        # LOGGER.info('Starting file trans...')
        # file_id = self.file_q.pop()
        # file_name = self.files.get(int(file_id))

        # LOGGER.info("Sending %s", file_name)
        # with open(os.path.join(PROJECT_DIR, 'from', file_name), 'rb') as f:
        #     # Read the file contents into memory
        #     file_data = f.read()
        #     LOGGER.info('Total file size %d', len(file_data))
        #     #file_data = self.enc_key.encrypt(file_data)

        #     total = len(file_data)
        #     LOGGER.info('Total file size (ENCRYPTED) %d', total)
        #     file_data = [file_data[i:i+CHUNK_SIZE] for i in range(0, total, CHUNK_SIZE)]

        # LOGGER.info("first_chunk: %d, last_chuck size: %d", len(file_data[0]), len(file_data[-1]))

        # data = f"{total},{file_name}"
        # LOGGER.info('Sending metadata : %s', data)
        # self.sock.sendall(data.encode('utf-8'))


        file_data = self.file_q.pop()
        LOGGER.info('Sending chunks.')
        # Send the chunks one by one
        for chunk in file_data['file_data']:
            self.sock.sendall(chunk)
            _ = self.sock.recv(14)
        
        print(f"{file_data['filename']}: transfer completed!")
    

    
    def get_file(self, file_name, f_size):
        # Get the file name to receive
        #f_size, file_name = sock.recv(1024).decode('utf-8').split(',')
        self.sock.send(b'ack')
        f_size = int(f_size)
        file_name = os.path.join(TRGT_DIR, file_name)
        LOGGER.info('Checking threads!!!')
        print(threading.current_thread().getName(), threading.active_count(), '<<<<<<')

        bar = tqdm(range(f_size),
                  f"Getting {file_name}",
                  unit="B", unit_scale=True,
                  unit_divisor=CHUNK_SIZE)
                
        data = []
        rec_count = 0
        while f_size > rec_count:
            chunk = self.sock.recv(CHUNK_SIZE)
            self.sock.send(b'ack')

            rec_count += len(chunk)
            data.append(chunk)
            bar.update(len(chunk))        


        LOGGER.info("first_chunk size: %d, last_chuck size: %d", len(data[0]), len(data[-1]))
        data = b''.join(data)
        LOGGER.info("Total data received: %d", len(data))
        LOGGER.info("Decrypt data.")
        #data = self.enc_key.decrypt(data)
        LOGGER.info("File size after decrypt: %d", len(data))

        LOGGER.info('Writing data to file.')
        with open(file_name, 'wb') as f:
            # Receive the chunks one by one and write them to the file
            f.write(data)

        LOGGER.info('%s: transfer completed!', file_name)
    
    def read_data(self):
        data = b''
        tmp = self.sock.recv(CHUNK_SIZE)
        d_size = struct.unpack('Q', tmp[0:8])[0]
        data = tmp[8:]

        while len(data) < d_size:
            data += self.sock.recv(CHUNK_SIZE)

        return pickle.loads(data)

    def receive(self):
        while True:
            # if self.rendering:
            #     time.sleep(0.5)
            #     continue
            #data = pickle.loads(self.sock.recv(CHUNK_SIZE))
            data = self.read_data()
            
            if comm := data.get('comm'):
                self.active_users = comm
                LOGGER.info('active users: %s', self.active_users.keys())
                continue
            
            if data.get('send_file'):
                LOGGER.info('Server ACK transfer')
                th = threading.Thread(target=self.send_file, daemon=True, name='SendFile')
                th.start()
                th.join()
                LOGGER.info('Thread finished., %s', not th.isAlive())
                continue
            
            if filename := data.get('get_file'):
                LOGGER.info('Preparing to get file.')
                th2 = threading.Thread(target=self.get_file,
                                       daemon=True,
                                       args=(filename, data['size'],),
                                       name='GetFile')
                th2.start()
                th2.join()
                LOGGER.info('Thread finished., %s', not th2.isAlive())
                continue
            
            if data.get('start_stream'):
                LOGGER.info('Preparing to stream video.')
                # th3 = threading.Thread(target=self.stream, daemon=True, name='Stream')
                # th3.start()
                # th3.join()
                # LOGGER.info('Thread finished., %s', not th3.isAlive())
                # continue
                self.rendering = True
                continue
            
            if data.get('get_stream'):
                print('Please type /y, to accept stream!')
                self.rendering = True
                continue
            
            frame = data.get('frame')
            if frame is not None: #:= data.get('frame'):
                self.queue.put(frame)
                continue
            
            msg = self.keys.decrypt(data['msg'])
            for e_code, emoji in EMOJI.items():
                msg = msg.replace(e_code, emoji)
            
            msg = f"{data['from']}:- {msg}"
            
            #LOGGER.info(msg)
            print(colored(msg, 'green'))
            
    def prep_file(self, file_id):
        file_name = self.files.get(int(file_id))

        LOGGER.info("Preparing %s", file_name)
        with open(os.path.join(PROJECT_DIR, 'from', file_name), 'rb') as f:
            # Read the file contents into memory
            file_data = f.read()
            LOGGER.info('Total file size %d', len(file_data))
            #file_data = self.enc_key.encrypt(file_data)

            total = len(file_data)
            file_data = [file_data[i:i+CHUNK_SIZE] for i in range(0, total, CHUNK_SIZE)]
        
        self.file_q.append({'filename': file_name, 'file_data': file_data})

        LOGGER.info("first_chunk: %d, last_chuck size: %d", len(file_data[0]), len(file_data[-1]))
        return file_name, total
    
    
    def video_stream_gen(self):
        file_name = self.files.get(int(self.file_st.pop()))
        file_name = os.path.join(PROJECT_DIR, 'from', file_name)

        LOGGER.info('Getting source file %s', file_name)

        video = cv.VideoCapture(file_name)
        
        video.set(cv.CAP_PROP_FRAME_WIDTH, 480)
        video.set(cv.CAP_PROP_FRAME_HEIGHT, 720)

        ret = 1
        while ret != 0:
            try:
                ret, frame = video.read()
                frame = imutils.resize(frame, height=400)
                self.queue.put(frame)
            except:
                self.rendering = False
                pass
        video.release()


    def get_stream(self):
        
        label = 'Receiving Video'
        
        cv.namedWindow(label)  
        cv.startWindowThread()      
        cv.moveWindow(label, 600, 500)

        while True:
            if self.queue.empty() and not self.rendering: break

            try:
                frame = self.queue.get(timeout=5)
                cv.imshow(label,frame)
                if cv.waitKey(1) & 0xFF == ord('q'):
                    LOGGER.info('stoping video')
                    break
            except:
                break
        
        LOGGER.info('EOF!!.')
        #self.rendering = False
        cv.destroyAllWindows()



    def stream(self):
        label = 'Streaming Video'
        
        cv.namedWindow(label)
        cv.startWindowThread()
        cv.moveWindow(label, 600, 60) 
        
        while self.rendering or not self.queue.empty():
            # ret, frame = video.read()
            try:
                frame = self.queue.get(timeout=5)
                # if (ret == 0):
                #     print("End of video")
                #     break
                #frame = cv.resize(frame, (480, 720))
                #_, buffer = cv.imencode('.jpeg', frame, [cv.IMWRITE_JPEG_QUALITY,80])
                # Encode data
                #data = base64.b64encode(buffer)
                data = pickle.dumps({'frame': frame})
                
                self.sock.sendall(self.append_size(data))
                    
                cv.imshow(label, frame)
                if cv.waitKey(1) & 0xFF == ord('q'):
                    LOGGER.info('stoping video')
                    break
            except:
                break
        cv.destroyAllWindows()


    def send(self):
        main_th = threading.current_thread()
        main_th.setName('Console')
        LOGGER.info('Send data in the format <USER:Message>')
        while True:
            data = input('')
            # Skip empty messages.
            if not data:
                continue
            if data == 'q!':
                LOGGER.info('Leaving chat!')
                os._exit(0)
            
            if data == '/ls':
                print(self.list_files())
                continue
            elif data == '/info':
                for i in threading.enumerate():
                    print(i.getName(), i.is_alive(), i.isDaemon())
                continue
            elif data == '/y':
                self.get_stream()
                continue
            
            data = data.split(':')
            if data[1].startswith('/'):
                cmd = data[1].split(' ')
                if cmd[0] == '/send':
                    file_name, size = self.prep_file(data[1].split(' ')[-1])
                    data = {'to': data[0], 'file': file_name, 'size': size} 
                    data = pickle.dumps(data)
                    self.sock.sendall(data)

                    LOGGER.info('waiting for server to be ready...')
                    continue
                elif cmd[0] == '/stream':
                    self.file_st.append(data[1].split(' ')[-1])
                    threading.Thread(target=self.video_stream_gen, daemon=True, name='VideoGen').start()

                    data = {'to': data[0], 'stream': True} 
                    data = pickle.dumps(data)
                    self.sock.sendall(data)


                    LOGGER.info('waiting for server to be ready...')

                    while not self.rendering:
                        time.sleep(0.1)
                    
                    # self.rendering = False
                    self.stream()
                    
                    continue

            if len(data) < 2 or data[0] not in self.active_users:
                LOGGER.error("Coulnd't find user")
                continue
            
        
            data[1] = ':'.join(data[1::])

            data[1] = self.keys.encrypt(data[1], self.active_users[data[0]])
            data = {'to': data[0], 'msg': data[1], 'from': self.user_data.user} 
            data = pickle.dumps(data)

            self.sock.sendall(data)
            