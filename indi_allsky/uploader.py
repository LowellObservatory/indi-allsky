import sys
import time
from pathlib import Path
from multiprocessing import Process
#from threading import Thread
import queue
import logging
import traceback

from . import filetransfer

logger = logging.getLogger('indi_allsky')


def unhandled_exception(exc_type, exc_value, exc_traceback):
    # Do not print exception when user cancels the program
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return

    logger.error("An uncaught exception occurred:")
    logger.error("Type: %s", exc_type)
    logger.error("Value: %s", exc_value)

    if exc_traceback:
        format_exception = traceback.format_tb(exc_traceback)
        for line in format_exception:
            logger.error(repr(line))


#log unhandled exceptions
sys.excepthook = unhandled_exception



class FileUploader(Process):
    def __init__(self, idx, config, upload_q):
        super(FileUploader, self).__init__()

        #self.threadID = idx
        self.name = 'FileUploader{0:03d}'.format(idx)

        self.config = config

        self.upload_q = upload_q


    def run(self):
        while True:
            time.sleep(1.0)  # sleep every loop

            try:
                u_dict = self.upload_q.get_nowait()
            except queue.Empty:
                continue


            if u_dict.get('stop'):
                return


            action = u_dict['action']
            local_file = u_dict.get('local_file')
            remote_file = u_dict.get('remote_file')
            remove_local = u_dict.get('remove_local')

            mq_data = u_dict.get('mq_data')


            # Build parameters
            if action == 'upload':
                connect_kwargs = {
                    'hostname' : self.config['FILETRANSFER']['HOST'],
                    'username' : self.config['FILETRANSFER']['USERNAME'],
                    'password' : self.config['FILETRANSFER']['PASSWORD'],
                }

                put_kwargs = {
                    'local_file'  : Path(local_file),
                    'remote_file' : Path(remote_file),
                }

                try:
                    client_class = getattr(filetransfer, self.config['FILETRANSFER']['CLASSNAME'])
                except AttributeError:
                    logger.error('Unknown filetransfer class: %s', self.config['FILETRANSFER']['CLASSNAME'])
                    return

                client = client_class()
                client.timeout = self.config['FILETRANSFER']['TIMEOUT']

                if self.config['FILETRANSFER']['PORT']:
                    client.port = self.config['FILETRANSFER']['PORT']

            elif action == 'mqttpub':
                connect_kwargs = {
                    'transport'   : self.config['MQTTPUBLISH']['TRANSPORT'],
                    'hostname'    : self.config['MQTTPUBLISH']['HOST'],
                    'username'    : self.config['MQTTPUBLISH']['USERNAME'],
                    'password'    : self.config['MQTTPUBLISH']['PASSWORD'],
                    'tls'         : self.config['MQTTPUBLISH']['TLS'],
                    'cert_bypass' : self.config['MQTTPUBLISH']['CERT_BYPASS'],
                }

                put_kwargs = {
                    'local_file'  : Path(local_file),
                    'base_topic'  : self.config['MQTTPUBLISH']['BASE_TOPIC'],
                    'qos'         : self.config['MQTTPUBLISH']['QOS'],
                    'mq_data'     : mq_data,
                }

                try:
                    client_class = getattr(filetransfer, 'paho_mqtt')
                except AttributeError:
                    logger.error('Unknown filetransfer class: %s', 'paho_mqtt')
                    return

                client = client_class()

                if self.config['MQTTPUBLISH']['PORT']:
                    client.port = self.config['MQTTPUBLISH']['PORT']

            else:
                raise Exception('Invalid transfer action')



            start = time.time()

            try:
                client.connect(**connect_kwargs)
            except filetransfer.exceptions.ConnectionFailure as e:
                logger.error('Connection failure: %s', e)
                client.close()
                return
            except filetransfer.exceptions.AuthenticationFailure as e:
                logger.error('Authentication failure: %s', e)
                client.close()
                return


            # Upload file
            try:
                client.put(**put_kwargs)
            except filetransfer.exceptions.ConnectionFailure as e:
                logger.error('Connection failure: %s', e)
                client.close()
                return
            except filetransfer.exceptions.AuthenticationFailure as e:
                logger.error('Authentication failure: %s', e)
                client.close()
                return
            except filetransfer.exceptions.TransferFailure as e:
                logger.error('Tranfer failure: %s', e)
                client.close()
                return
            except filetransfer.exceptions.PermissionFailure as e:
                logger.error('Permission failure: %s', e)
                client.close()
                return


            # close file transfer client
            client.close()

            upload_elapsed_s = time.time() - start
            logger.info('Upload transaction completed in %0.4f s', upload_elapsed_s)


            if remove_local:
                local_file_p = Path(local_file)

                try:
                    local_file_p.unlink()
                except PermissionError as e:
                    logger.error('Cannot remove local file: %s', str(e))
                    return
                except FileNotFoundError as e:
                    logger.error('Cannot remove local file: %s', str(e))
                    return


            #raise Exception('Testing uncaught exception')

