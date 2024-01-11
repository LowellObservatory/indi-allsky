#!/usr/bin/env python3

import sys
from pathlib import Path
from pprint import pformat  # noqa: F401
import time
import json
import re
import psutil
import ssl
import paho.mqtt.publish as publish
import logging

from sqlalchemy.orm.exc import NoResultFound

sys.path.append(str(Path(__file__).parent.absolute().parent))

from indi_allsky.config import IndiAllSkyConfig
from indi_allsky.flask import create_app


logger = logging.getLogger('indi_allsky')
logger.setLevel(logging.INFO)


app = create_app()


class HADiscovery(object):


    discovery_base_topic = 'homeassistant'
    unique_id_base = '001'


    def __init__(self):
        with app.app_context():
            try:
                self._config_obj = IndiAllSkyConfig()
                #logger.info('Loaded config id: %d', self._config_obj.config_id)
            except NoResultFound:
                logger.error('No config file found, please import a config')
                sys.exit(1)

            self.config = self._config_obj.config

        self._port = 1883


    def main(self):
        if not self.config['MQTTPUBLISH'].get('ENABLE'):
            logger.error('MQ Publishing not enabled')
            sys.exit(1)


        transport = self.config['MQTTPUBLISH']['TRANSPORT']
        hostname = self.config['MQTTPUBLISH']['HOST']
        port = self.config['MQTTPUBLISH']['PORT']
        username = self.config['MQTTPUBLISH']['USERNAME']
        password = self.config['MQTTPUBLISH']['PASSWORD']
        tls = self.config['MQTTPUBLISH']['TLS']
        cert_bypass = self.config['MQTTPUBLISH'].get('CERT_BYPASS', True)


        if port:
            self._port = port



        print('')
        print('#################################################')
        print('##### Home Assistant Discovery Setup Script #####')
        print('#################################################')
        print('')
        print('Transport: {0}'.format(transport))
        print('Hostname: {0}'.format(hostname))
        print('Port: {0}'.format(port))
        print('TLS: {0}'.format(str(tls)))
        print('Username: {0}'.format(username))
        print('')

        print('Setup proceeding in 10 seconds... (control-c to cancel)')


        time.sleep(10.0)


        base_topic  = self.config['MQTTPUBLISH']['BASE_TOPIC']


        basic_sensor_list = [
            {
                'component' : 'image',
                'object_id' : 'latest',
                'config' : {
                    'name' : "indi-allsky Camera",
                    'unique_id' : 'indi_allsky_latest_{0}'.format(self.unique_id_base),
                    'content_type' : 'image/jpeg',
                    'image_topic' : '/'.join((base_topic, 'latest')),
                },
            },
            {
                'component' : 'sensor',
                'object_id' : 'exposure',
                'config' : {
                    'name' : 'Exposure',
                    'unit_of_measurement' : 's',
                    'unique_id' : 'indi_allsky_exposure_{0}'.format(self.unique_id_base),
                    'state_topic' : '/'.join((base_topic, 'exposure')),
                },
            },
            {
                'component' : 'sensor',
                'object_id' : 'gain',
                'config' : {
                    'name' : 'Camera Gain',
                    'unique_id' : 'indi_allsky_gain_{0}'.format(self.unique_id_base),
                    'state_topic' : '/'.join((base_topic, 'gain')),
                },
            },
            {
                'component' : 'sensor',
                'object_id' : 'bin',
                'config' : {
                    'name' : 'Camera Binmode',
                    'unique_id' : 'indi_allsky_bin_{0}'.format(self.unique_id_base),
                    'state_topic' : '/'.join((base_topic, 'bin')),
                },
            },
            {
                'component' : 'sensor',
                'object_id' : 'temp',
                'config' : {
                    'name' : 'Camera Temp',
                    'unit_of_measurement' : '°',
                    'unique_id' : 'indi_allsky_temp_{0}'.format(self.unique_id_base),
                    'state_topic' : '/'.join((base_topic, 'temp')),
                },
            },
            {
                'component' : 'sensor',
                'object_id' : 'sunalt',
                'config' : {
                    'name' : 'Sun Altitude',
                    'unit_of_measurement' : '°',
                    'unique_id' : 'indi_allsky_sunalt_{0}'.format(self.unique_id_base),
                    'state_topic' : '/'.join((base_topic, 'sunalt')),
                },
            },
            {
                'component' : 'sensor',
                'object_id' : 'moonalt',
                'config' : {
                    'name' : 'Moon Altitude',
                    'unit_of_measurement' : '°',
                    'unique_id' : 'indi_allsky_moonalt_{0}'.format(self.unique_id_base),
                    'state_topic' : '/'.join((base_topic, 'moonalt')),
                },
            },
            {
                'component' : 'sensor',
                'object_id' : 'moonphase',
                'config' : {
                    'name' : 'Moon Phase',
                    'unit_of_measurement' : '%',
                    'unique_id' : 'indi_allsky_moonphase_{0}'.format(self.unique_id_base),
                    'state_topic' : '/'.join((base_topic, 'moonphase')),
                },
            },
            {
                'component' : 'binary_sensor',
                'object_id' : 'moonmode',
                'config' : {
                    'name' : 'Moon Mode',
                    'payload_on' : True,
                    'payload_off' : False,
                    'unique_id' : 'indi_allsky_moonmode_{0}'.format(self.unique_id_base),
                    'state_topic' : '/'.join((base_topic, 'moonmode')),
                },
            },
            {
                'component' : 'binary_sensor',
                'object_id' : 'night',
                'config' : {
                    'name' : 'Night',
                    'payload_on' : True,
                    'payload_off' : False,
                    'unique_id' : 'indi_allsky_night_{0}'.format(self.unique_id_base),
                    'state_topic' : '/'.join((base_topic, 'night')),
                },
            },
            {
                'component' : 'sensor',
                'object_id' : 'sqm',
                'config' : {
                    'name' : 'SQM',
                    'unique_id' : 'indi_allsky_sqm_{0}'.format(self.unique_id_base),
                    'state_topic' : '/'.join((base_topic, 'sqm')),
                },
            },
            {
                'component' : 'sensor',
                'object_id' : 'stars',
                'config' : {
                    'name' : 'Stars',
                    'unique_id' : 'indi_allsky_stars_{0}'.format(self.unique_id_base),
                    'state_topic' : '/'.join((base_topic, 'stars')),
                },
            },
            {
                'component' : 'sensor',
                'object_id' : 'latitude',
                'config' : {
                    'name' : 'Latitude',
                    'unit_of_measurement' : '°',
                    'unique_id' : 'indi_allsky_latitude_{0}'.format(self.unique_id_base),
                    'state_topic' : '/'.join((base_topic, 'latitude')),
                },
            },
            {
                'component' : 'sensor',
                'object_id' : 'longitude',
                'config' : {
                    'name' : 'Longitude',
                    'unit_of_measurement' : '°',
                    'unique_id' : 'indi_allsky_longitude_{0}'.format(self.unique_id_base),
                    'state_topic' : '/'.join((base_topic, 'longitude')),
                },
            },
            {
                'component' : 'sensor',
                'object_id' : 'elevation',
                'config' : {
                    'name' : 'Elevation',
                    'unit_of_measurement' : 'm',
                    'unique_id' : 'indi_allsky_elevation_{0}'.format(self.unique_id_base),
                    'state_topic' : '/'.join((base_topic, 'elevation')),
                },
            },
            {
                'component' : 'sensor',
                'object_id' : 'kpindex',
                'config' : {
                    'name' : 'K-P Index',
                    'unique_id' : 'indi_allsky_kpindex_{0}'.format(self.unique_id_base),
                    'state_topic' : '/'.join((base_topic, 'kpindex')),
                },
            },
            {
                'component' : 'sensor',
                'object_id' : 'ovation_max',
                'config' : {
                    'name' : 'Aurora',
                    'unit_of_measurement' : '%',
                    'unique_id' : 'indi_allsky_ovation_max_{0}'.format(self.unique_id_base),
                    'state_topic' : '/'.join((base_topic, 'ovation_max')),
                },
            },
            {
                'component' : 'sensor',
                'object_id' : 'smoke_rating',
                'config' : {
                    'name' : 'Smoke Rating',
                    'unique_id' : 'indi_allsky_smoke_rating_{0}'.format(self.unique_id_base),
                    'state_topic' : '/'.join((base_topic, 'smoke_rating')),
                },
            },
            {
                'component' : 'sensor',
                'object_id' : 'sidereal_time',
                'config' : {
                    'name' : 'Sidereal Time',
                    'unique_id' : 'indi_allsky_sidereal_time_{0}'.format(self.unique_id_base),
                    'state_topic' : '/'.join((base_topic, 'sidereal_time')),
                },
            },

        ]


        extended_sensor_list = [
            {
                'component' : 'sensor',
                'object_id' : 'cpu_total',
                'config' : {
                    'name' : 'CPU Total',
                    'unique_id' : 'indi_allsky_cpu_total_{0}'.format(self.unique_id_base),
                    'state_topic' : '/'.join((base_topic, 'cpu', 'total')),
                },
            },
            {
                'component' : 'sensor',
                'object_id' : 'memory_total',
                'config' : {
                    'name' : 'Memory Total',
                    'unit_of_measurement' : '%',
                    'unique_id' : 'indi_allsky_memory_total_{0}'.format(self.unique_id_base),
                    'state_topic' : '/'.join((base_topic, 'memory', 'total')),
                },
            },
        ]


        fs_list = psutil.disk_partitions()

        for fs in fs_list:
            if fs.mountpoint.startswith('/snap/'):
                # skip snap filesystems
                continue

            try:
                psutil.disk_usage(fs.mountpoint)
            except PermissionError as e:
                logger.error('PermissionError: %s', str(e))
                continue

            if fs.mountpoint == '/':
                extended_sensor_list.append({
                    'component' : 'sensor',
                    'object_id' : 'root_fs',
                    'config' : {
                        'name' : 'Filesystem /',
                        'unit_of_measurement' : '%',
                        'unique_id' : 'indi_allsky_fs_root_{0}'.format(self.unique_id_base),
                        'state_topic' : '/'.join((base_topic, 'disk', 'root')),
                    },
                })


            else:
                # remove slashes
                fs_mountpoint_safe = re.sub(r'/', '__', fs.mountpoint)

                extended_sensor_list.append({
                    'component' : 'sensor',
                    'object_id' : '{0}_fs'.format(fs_mountpoint_safe),
                    'config' : {
                        'name' : 'Filesystem {0}'.format(fs.mountpoint),
                        'unit_of_measurement' : '%',
                        'unique_id' : 'indi_allsky_fs_{0}_{1}'.format(fs_mountpoint_safe, self.unique_id_base),
                        'state_topic' : '/'.join((base_topic, 'disk', re.sub(r'^/', '', fs.mountpoint))),  # remove slash prefix
                    },
                })




        temp_info = psutil.sensors_temperatures()

        for t_key in temp_info.keys():
            for i, t in enumerate(temp_info[t_key]):
                if not t.label:
                    # use index for label name
                    label = str(i)
                else:
                    label = t.label


                t_key_safe = re.sub(r'[#+\$\*\>\ ]', '_', t_key)
                label_safe = re.sub(r'[#+\$\*\>\ ]', '_', label)


                extended_sensor_list.append({
                    'component' : 'sensor',
                    'object_id' : '{0}_{1}_temp'.format(t_key_safe, label_safe),
                    'config' : {
                        'name' : 'Sensor {0} {1}'.format(t_key_safe, label_safe),
                        'unit_of_measurement' : '°',
                        'unique_id' : 'indi_allsky_temp_{0}_{1}'.format(t_key_safe, label_safe),
                        'state_topic' : '/'.join((base_topic, 'temp', t_key_safe, label_safe)),
                    },
                })



        message_list = list()
        for sensor in basic_sensor_list:
            message_list.append({
                'topic'    : '/'.join((self.discovery_base_topic, sensor['component'], sensor['object_id'], 'config')),
                'payload'  : json.dumps(sensor['config']),
                'qos'      : 0,
                'retain'   : False,
            })

        for sensor in extended_sensor_list:
            message_list.append({
                'topic'    : '/'.join((self.discovery_base_topic, sensor['component'], sensor['object_id'], 'config')),
                'payload'  : json.dumps(sensor['config']),
                'qos'      : 0,
                'retain'   : False,
            })



        #logger.warning('Messages: %s', pformat(message_list))


        mq_auth = None
        mq_tls = None

        if tls:
            mq_tls = {
                'ca_certs'    : '/etc/ssl/certs/ca-certificates.crt',
                #'tls_version' : ssl.PROTOCOL_TLSv1_2,
                'cert_reqs'   : ssl.CERT_REQUIRED,
                'insecure'    : False,
            }

            if cert_bypass:
                mq_tls['cert_reqs'] = ssl.CERT_NONE
                mq_tls['insecure'] = True



        if username:
            mq_auth = {
                'username' : username,
                'password' : password,
            }



        logger.warning('Publishing discovery data')
        publish.multiple(
            message_list,
            transport=transport,
            hostname=hostname,
            port=self._port,
            client_id='',
            keepalive=60,
            auth=mq_auth,
            tls=mq_tls,
        )


if __name__ == "__main__":
    had = HADiscovery()
    had.main()
