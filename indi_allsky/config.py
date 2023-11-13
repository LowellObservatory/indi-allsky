import sys
import os
import time
import io
import json
import tempfile
import random
from pathlib import Path
from collections import OrderedDict
from prettytable import PrettyTable
import logging

from cryptography.fernet import Fernet
#from cryptography.fernet import InvalidToken

from .flask.models import IndiAllSkyDbConfigTable
from .flask.models import IndiAllSkyDbUserTable

from .flask import create_app
from .flask import db

from sqlalchemy.orm.exc import NoResultFound

from .version import __config_level__


app = create_app()

logger = logging.getLogger('indi_allsky')


class IndiAllSkyConfigBase(object):

    _base_config = OrderedDict({
        "ENCRYPT_PASSWORDS_comment" : "Do not manually adjust",
        "ENCRYPT_PASSWORDS" : False,
        "CAMERA_INTERFACE" : "indi",
        "INDI_SERVER" : "localhost",
        "INDI_PORT"   : 7624,
        "INDI_CAMERA_NAME" : "",
        "OWNER" : "",
        "LENS_NAME" : "AllSky Lens",
        "LENS_FOCAL_LENGTH" : 2.5,
        "LENS_FOCAL_RATIO"  : 2.0,
        "LENS_IMAGE_CIRCLE" : 4000,
        "LENS_ALTITUDE"     : 90.0,
        "LENS_AZIMUTH"      : 0.0,
        "CCD_CONFIG" : {
            "NIGHT" : {
                "GAIN"    : 100,
                "BINNING" : 1,
            },
            "MOONMODE" : {
                "GAIN"    : 75,
                "BINNING" : 1,
            },
            "DAY" : {
                "GAIN"    : 0,
                "BINNING" : 1,
            }
        },
        "INDI_CONFIG_DEFAULTS" : {
            "SWITCHES" : {},
            "PROPERTIES" : {},
            "TEXT" : {},
        },
        "CCD_EXPOSURE_MAX"     : 15.00000,
        "CCD_EXPOSURE_DEF"     : 0.0,
        "CCD_EXPOSURE_MIN"     : 0.0,
        "CCD_BIT_DEPTH"        : 0,  # 0 is auto
        "EXPOSURE_PERIOD"      : 15.00000,
        "EXPOSURE_PERIOD_DAY"  : 15.00000,
        "FOCUS_MODE"           : False,
        "FOCUS_DELAY"          : 4.0,
        "CFA_PATTERN"      : "",  # None, GRBG, RGGB, BGGR, GBRG
        "SCNR_ALGORITHM"   : "",  # empty string, average_neutral, or maximum_neutral
        "WBR_FACTOR"       : 1.0,
        "WBG_FACTOR"       : 1.0,
        "WBB_FACTOR"       : 1.0,
        "AUTO_WB"          : False,
        "SATURATION_FACTOR": 1.0,
        "CCD_COOLING"      : False,
        "CCD_TEMP"         : 15.0,
        "TEMP_DISPLAY"     : "c",  # c = celcius, f = fahrenheit, k = kelvin",
        "CCD_TEMP_SCRIPT"  : "",
        "GPS_ENABLE"       : False,
        "TARGET_ADU"         : 75,
        "TARGET_ADU_DAY"     : 75,
        "TARGET_ADU_DEV"     : 10,
        "TARGET_ADU_DEV_DAY" : 20,
        "ADU_ROI" : [],
        "ADU_FOV_DIV" : 4,
        "DETECT_STARS" : True,
        "DETECT_STARS_THOLD" : 0.6,
        "DETECT_METEORS" : False,
        "DETECT_MASK" : "",
        "DETECT_DRAW" : False,
        "LOGO_OVERLAY" : "",
        "SQM_ROI" : [],
        "SQM_FOV_DIV" : 4,
        "LOCATION_NAME"      : "",
        "LOCATION_LATITUDE"  : 33.0,
        "LOCATION_LONGITUDE" : -84.0,
        "LOCATION_ELEVATION" : 300.0,
        "TIMELAPSE_ENABLE"         : True,
        "DAYTIME_CAPTURE"          : True,
        "DAYTIME_TIMELAPSE"        : True,
        "DAYTIME_CONTRAST_ENHANCE" : False,
        "NIGHT_CONTRAST_ENHANCE"   : False,
        "CONTRAST_ENHANCE_16BIT"   : False,
        "CLAHE_CLIPLIMIT"          : 3.0,
        "CLAHE_GRIDSIZE"           : 8,
        "NIGHT_SUN_ALT_DEG"        : -6.0,
        "NIGHT_MOONMODE_ALT_DEG"   : 0,
        "NIGHT_MOONMODE_PHASE"     : 33,
        "WEB_EXTRA_TEXT"           : "",
        "WEB_NONLOCAL_IMAGES"      : False,
        "WEB_LOCAL_IMAGES_ADMIN"   : False,
        "IMAGE_STRETCH" : {
            "MODE1_ENABLE"   : False,
            "MODE1_GAMMA"    : 3.0,
            "MODE1_STDDEVS"  : 2.25,
            "SPLIT"          : False,
            "MOONMODE"       : False,
            "DAYTIME"        : False,
        },
        "KEOGRAM_ANGLE"    : 0,
        "KEOGRAM_H_SCALE"  : 100,
        "KEOGRAM_V_SCALE"  : 33,
        "KEOGRAM_LABEL"    : True,
        "STARTRAILS_MAX_ADU"    : 65,
        "STARTRAILS_MASK_THOLD" : 190,
        "STARTRAILS_PIXEL_THOLD": 1.0,
        "STARTRAILS_TIMELAPSE"  : True,
        "STARTRAILS_TIMELAPSE_MINFRAMES" : 250,
        "STARTRAILS_SUN_ALT_THOLD"       : -15.0,
        "STARTRAILS_MOONMODE_THOLD"      : True,
        "STARTRAILS_MOON_ALT_THOLD"      : 91.0,
        "STARTRAILS_MOON_PHASE_THOLD"    : 101.0,
        "IMAGE_FILE_TYPE" : "jpg",  # jpg, png, or tif
        "IMAGE_FILE_COMPRESSION" : {
            "jpg"   : 90,
            "png"   : 5,
            "tif"   : 5,  # 5 = LZW
        },
        "IMAGE_FOLDER"     : "/var/www/html/allsky/images",
        "IMAGE_LABEL_TEMPLATE": "# size:30 [Use 60 for higher resolution cameras]\n# xy:-15,15 (Upper Right)\n# anchor:ra (Right Justified)\n# color:150,0,0\n{timestamp:%Y.%m.%d %H:%M:%S}\n# color:100,100,0\nLat {latitude:0.0f} Long {longitude:0.0f}\n# color:150,150,150\nHubble {hst_up:s} [{hst_next_h:0.1f}h/{hst_next_alt:0.0f}\u00b0]\nISS {iss_up:s} [{iss_next_h:0.1f}h/{iss_next_alt:0.0f}\u00b0]\n# xy:-15,-240 (Lower Right) [Use -15,-450 for size 60]\n# color:175,175,0\nSun {sun_alt:0.0f}\u00b0\n# color:125,0,0\nMercury {mercury_alt:0.0f}\u00b0\n# color:100,150,150\nVenus {venus_alt:0.0f}\u00b0\n# color:150,0,0\nMars {mars_alt:0.0f}\u00b0\n# color:100,100,0\nJupiter {jupiter_alt:0.0f}\u00b0\n# color:100,100,150\nSaturn {saturn_alt:0.0f}\u00b0\n# color:150,150,150\nMoon {moon_phase:0.0f}% {moon_alt:0.0f}\u00b0\n# xy:15,-120 (Lower Left)  [Use 15,-210 for size 60]\n# anchor:la (Left Justified)\n# color:0,150,150\nStars {stars:d}\n# color:150,50,50\nKp-index {kpindex:0.2f}\n# color:150,150,150\nSmoke {smoke_rating:s}\n# xy:15,15 (Upper Left)\n# color:0,150,0\nExposure {exposure:0.6f}\n# color:150,50,0\nGain {gain:d}\n# color:50,50,150\nTemp {temp:0.1f}{temp_unit:s}\n# color:150,0,150\nStretch {stretch:s}\nStacking {stack_method:s}\n# color:200,200,200 (default color)\n# additional labels will be added here",
        "URL_TEMPLATE": "https://{bucket}.s3.{region}.{host}",
        "IMAGE_EXTRA_TEXT" : "",
        "IMAGE_CROP_ROI"   : [],
        "IMAGE_ROTATE"     : "",  # empty, ROTATE_90_CLOCKWISE, ROTATE_90_COUNTERCLOCKWISE, ROTATE_180
        "IMAGE_ROTATE_ANGLE" : 0,
        "IMAGE_FLIP_V"     : True,
        "IMAGE_FLIP_H"     : True,
        "IMAGE_SCALE"      : 100,
        "NIGHT_GRAYSCALE"  : False,
        "DAYTIME_GRAYSCALE": False,
        "IMAGE_CIRCLE_MASK" : {
            "ENABLE"   : False,
            "DIAMETER" : 1500,
            "OFFSET_X" : 0,
            "OFFSET_Y" : 0,
            "BLUR"     : 35,
            "OPACITY"  : 100,
            "OUTLINE"  : False,
        },
        "FISH2PANO" : {
            "ENABLE"   : False,
            "DIAMETER" : 3000,
            "OFFSET_X" : 0,
            "OFFSET_Y" : 0,
            "SCALE"    : 0.3,
        },
        "IMAGE_SAVE_FITS"     : False,
        "IMAGE_EXPORT_RAW"    : "",  # png or tif (or empty)
        "IMAGE_EXPORT_FOLDER" : "/var/www/html/allsky/images/export",
        "IMAGE_STACK_METHOD"  : "maximum",  # maximum, average, or minimum
        "IMAGE_STACK_COUNT"   : 1,
        "IMAGE_STACK_ALIGN"   : False,
        "IMAGE_ALIGN_DETECTSIGMA" : 5,
        "IMAGE_ALIGN_POINTS" : 50,
        "IMAGE_ALIGN_SOURCEMINAREA" : 10,
        "IMAGE_STACK_SPLIT"   : False,
        "IMAGE_EXPIRE_DAYS"     : 30,
        "TIMELAPSE_EXPIRE_DAYS" : 365,
        "FFMPEG_FRAMERATE" : 25,
        "FFMPEG_BITRATE"   : "2500k",
        "FFMPEG_VFSCALE"   : "",
        "FFMPEG_CODEC"     : "libx264",
        "FITSHEADERS" : [
            [ "INSTRUME", "indi-allsky" ],
            [ "OBSERVER", "" ],
            [ "SITE", "" ],
            [ "OBJECT", "" ],
            [ "NOTES", "" ],
        ],
        "IMAGE_LABEL_SYSTEM" : "pillow",
        "TEXT_PROPERTIES" : {
            "DATE_FORMAT"    : "%Y%m%d %H:%M:%S",
            "FONT_FACE"      : "FONT_HERSHEY_SIMPLEX",
            "FONT_AA"        : "LINE_AA",
            "FONT_SCALE"     : 0.8,
            "FONT_THICKNESS" : 1,
            "FONT_OUTLINE"   : True,
            "FONT_HEIGHT"    : 30,
            "FONT_X"         : 30,
            "FONT_Y"         : 30,
            "FONT_COLOR"     : [200, 200, 200],
            "PIL_FONT_FILE"  : "fonts-freefont-ttf/FreeMonoBold.ttf",
            "PIL_FONT_CUSTOM": "",
            "PIL_FONT_SIZE"  : 30,
        },
        "COMPASS_DIRECTIONS" : {
            "ENABLE"         : False,
            "FONT_COLOR"     : [200, 0, 0],
            "SWAP_NS"        : False,
            "SWAP_EW"        : False,
            "CHAR_NORTH"     : "N",
            "CHAR_EAST"      : "E",
            "CHAR WEST"      : "W",
            "CHAR_SOUTH"     : "S",
            "OFFSET_TOP"     : 3,
            "OFFSET_LEFT"    : 5,
            "OFFSET_RIGHT"   : 20,
            "OFFSET_BOTTOM"  : 30,
            "OPENCV_FONT_SCALE" : 0.8,
            "PIL_FONT_SIZE"  : 30,
        },
        "ORB_PROPERTIES" : {
            "MODE"           : "ha",  # ha = hour angle, az = azimuth, alt = altitude, off = off
            "RADIUS"         : 9,
            "SUN_COLOR"      : [200, 200, 0],
            "MOON_COLOR"     : [128, 128, 128],
        },
        "UPLOAD_WORKERS" : 2,
        "FILETRANSFER" : {
            "CLASSNAME"              : "pycurl_sftp",  # pycurl_sftp, pycurl_ftps, pycurl_ftpes, paramiko_sftp, python_ftp, python_ftpes
            "HOST"                   : "",
            "PORT"                   : 0,
            "USERNAME"               : "",
            "PASSWORD"               : "",
            "PASSWORD_E"             : "",
            "PRIVATE_KEY"            : "",
            "PUBLIC_KEY"             : "",
            "TIMEOUT"                : 5.0,
            "CERT_BYPASS"            : True,
            "REMOTE_IMAGE_NAME"      : "image.{0}",
            "REMOTE_IMAGE_FOLDER"        : "allsky",
            "REMOTE_METADATA_NAME"       : "latest_metadata.json",
            "REMOTE_METADATA_FOLDER"     : "allsky",
            "REMOTE_VIDEO_FOLDER"        : "allsky/videos",
            "REMOTE_KEOGRAM_FOLDER"      : "allsky/keograms",
            "REMOTE_STARTRAIL_FOLDER"    : "allsky/startrails",
            "REMOTE_STARTRAIL_VIDEO_FOLDER" : "allsky/videos",
            "REMOTE_ENDOFNIGHT_FOLDER"   : "allsky",
            "UPLOAD_IMAGE"           : 0,
            "UPLOAD_METADATA"        : False,
            "UPLOAD_VIDEO"           : False,
            "UPLOAD_KEOGRAM"         : False,
            "UPLOAD_STARTRAIL"       : False,
            "UPLOAD_STARTRAIL_VIDEO" : False,
            "UPLOAD_ENDOFNIGHT"      : False,
            "LIBCURL_OPTIONS"        : {},
        },
        "S3UPLOAD" : {
            "ENABLE"                 : False,
            "CLASSNAME"              : "boto3_s3",
            "ACCESS_KEY"             : "",
            "SECRET_KEY"             : "",
            "SECRET_KEY_E"           : "",
            "CREDS_FILE"             : "",
            "BUCKET"                 : "change-me",
            "REGION"                 : "us-east-2",
            "HOST"                   : "amazonaws.com",
            "PORT"                   : 0,
            "URL_TEMPLATE"           : "https://{bucket}.s3.{region}.{host}",
            "ACL"                    : "public-read",  # s3: public-read, gcp: publicRead
            "STORAGE_CLASS"          : "STANDARD",
            "TLS"                    : True,
            "CERT_BYPASS"            : False,
            "UPLOAD_FITS"            : False,
            "UPLOAD_RAW"             : False,
        },
        "MQTTPUBLISH" : {
            "ENABLE"                 : False,
            "TRANSPORT"              : "tcp",  # tcp or websockets
            "HOST"                   : "localhost",
            "PORT"                   : 8883,  # 1883 = mqtt, 8883 = TLS
            "USERNAME"               : "indi-allsky",
            "PASSWORD"               : "",
            "PASSWORD_E"             : "",
            "BASE_TOPIC"             : "indi-allsky",
            "QOS"                    : 0,  # 0, 1, or 2
            "TLS"                    : True,
            "CERT_BYPASS"            : True,
        },
        "SYNCAPI" : {
            "ENABLE"                 : False,
            "BASEURL"                : "https://example.com/indi-allsky",
            "USERNAME"               : "",
            "APIKEY"                 : "",
            "APIKEY_E"               : "",
            "CERT_BYPASS"            : False,
            "POST_S3"                : False,
            "EMPTY_FILE"             : False,
            "UPLOAD_IMAGE"           : 1,
            #"UPLOAD_VIDEO"           : True,  # this cannot be changed
            "TIMEOUT"                : 5.0,
        },
        "LIBCAMERA" : {
            "IMAGE_FILE_TYPE"        : "dng",
            "AWB"                    : "auto",
            "AWB_DAY"                : "auto",
            "AWB_ENABLE"             : False,
            "AWB_ENABLE_DAY"         : False,
            "EXTRA_OPTIONS"          : "",
            "EXTRA_OPTIONS_DAY"      : "",
        },
        "PYCURL_CAMERA" : {
            "URL"                    : '',
            "USERNAME"               : "",
            "PASSWORD"               : "",
            "PASSWORD_E"             : "",
        },
    })


    @property
    def base_config(self):
        return self._base_config

    @base_config.setter
    def base_config(self, new_base_config):
        pass  # read only


class IndiAllSkyConfig(IndiAllSkyConfigBase):

    def __init__(self):
        self._config = self.base_config.copy()  # populate initial values

        # fetch latest config
        config_entry = self._getConfigEntry()

        # apply config on top of template
        self._config_id = config_entry.id
        self._config_level = config_entry.level
        self._config.update(config_entry.data)

        self._config = self._decrypt_passwords()


    @property
    def config(self):
        return self._config

    @config.setter
    def config(self, new_config):
        pass  # read only


    @property
    def config_id(self):
        return self._config_id

    @config_id.setter
    def config_id(self, new_config_id):
        pass  # read only


    @property
    def config_level(self):
        return self._config_level

    @config_level.setter
    def config_level(self, new_config_level):
        pass  # read only


    def _getConfigEntry(self, config_id=None):
        ### return the last saved config entry

        if config_id:
            # not catching NoResultFound
            config_entry = IndiAllSkyDbConfigTable.query\
                .filter(IndiAllSkyDbConfigTable.id == int(config_id))\
                .one()
        else:
            # not catching NoResultFound
            config_entry = IndiAllSkyDbConfigTable.query\
                .order_by(IndiAllSkyDbConfigTable.createDate.desc())\
                .limit(1)\
                .one()

        return config_entry


    def _setConfigEntry(self, config, user_entry, note, encrypted):
        config_entry = IndiAllSkyDbConfigTable(
            data=config,
            level=str(__config_level__),
            user_id=user_entry.id,
            note=str(note),
            encrypted=encrypted,
        )

        db.session.add(config_entry)
        db.session.commit()

        return config_entry


    def _decrypt_passwords(self):
        config = self._config.copy()

        if config['ENCRYPT_PASSWORDS']:
            f_key = Fernet(app.config['PASSWORD_KEY'].encode())

            filetransfer__password_e = config.get('FILETRANSFER', {}).get('PASSWORD_E', '')
            if filetransfer__password_e:
                # not catching InvalidToken
                filetransfer__password = f_key.decrypt(filetransfer__password_e.encode()).decode()
            else:
                filetransfer__password = config.get('FILETRANSFER', {}).get('PASSWORD', '')


            s3upload__secret_key_e = config.get('S3UPLOAD', {}).get('SECRET_KEY_E', '')
            if s3upload__secret_key_e:
                # not catching InvalidToken
                s3upload__secret_key = f_key.decrypt(s3upload__secret_key_e.encode()).decode()
            else:
                s3upload__secret_key = config.get('S3UPLOAD', {}).get('SECRET_KEY', '')


            mqttpublish__password_e = config.get('MQTTPUBLISH', {}).get('PASSWORD_E', '')
            if mqttpublish__password_e:
                # not catching InvalidToken
                mqttpublish__password = f_key.decrypt(mqttpublish__password_e.encode()).decode()
            else:
                mqttpublish__password = config.get('MQTTPUBLISH', {}).get('PASSWORD', '')


            syncapi__apikey_e = config.get('SYNCAPI', {}).get('APIKEY_E', '')
            if syncapi__apikey_e:
                # not catching InvalidToken
                syncapi__apikey = f_key.decrypt(syncapi__apikey_e.encode()).decode()
            else:
                syncapi__apikey = config.get('SYNCAPI', {}).get('APIKEY', '')


            pycurl_camera__password_e = config.get('PYCURL_CAMERA', {}).get('PASSWORD_E', '')
            if pycurl_camera__password_e:
                # not catching InvalidToken
                pycurl_camera__password = f_key.decrypt(pycurl_camera__password_e.encode()).decode()
            else:
                pycurl_camera__password = config.get('PYCURL_CAMERA', {}).get('PASSWORD', '')

        else:
            # passwords should not be encrypted
            filetransfer__password = config.get('FILETRANSFER', {}).get('PASSWORD', '')
            s3upload__secret_key = config.get('S3UPLOAD', {}).get('SECRET_KEY', '')
            mqttpublish__password = config.get('MQTTPUBLISH', {}).get('PASSWORD', '')
            syncapi__apikey = config.get('SYNCAPI', {}).get('APIKEY', '')
            pycurl_camera__password = config.get('PYCURL_CAMERA', {}).get('PASSWORD', '')


        config['FILETRANSFER']['PASSWORD'] = filetransfer__password
        config['FILETRANSFER']['PASSWORD_E'] = ''
        config['S3UPLOAD']['SECRET_KEY'] = s3upload__secret_key
        config['S3UPLOAD']['SECRET_KEY_E'] = ''
        config['MQTTPUBLISH']['PASSWORD'] = mqttpublish__password
        config['MQTTPUBLISH']['PASSWORD_E'] = ''
        config['SYNCAPI']['APIKEY'] = syncapi__apikey
        config['SYNCAPI']['APIKEY_E'] = ''
        config['PYCURL_CAMERA']['PASSWORD'] = pycurl_camera__password
        config['PYCURL_CAMERA']['PASSWORD_E'] = ''

        return config


    def save(self, username, note):
        user_entry = IndiAllSkyDbUserTable.query\
            .filter(IndiAllSkyDbUserTable.username == str(username))\
            .one()


        config, encrypted = self._encryptPasswords()

        config_entry = self._setConfigEntry(config, user_entry, note, encrypted)

        self._config_id = config_entry.id

        return config_entry


    def _encryptPasswords(self):
        config = self._config.copy()

        if config['ENCRYPT_PASSWORDS']:
            encrypted = True

            f_key = Fernet(app.config['PASSWORD_KEY'].encode())

            filetransfer__password = str(config['FILETRANSFER']['PASSWORD'])
            if filetransfer__password:
                filetransfer__password_e = f_key.encrypt(filetransfer__password.encode()).decode()
                filetransfer__password = ''
            else:
                filetransfer__password_e = ''
                filetransfer__password = ''


            s3upload__secret_key = str(config['S3UPLOAD']['SECRET_KEY'])
            if s3upload__secret_key:
                s3upload__secret_key_e = f_key.encrypt(s3upload__secret_key.encode()).decode()
                s3upload__secret_key = ''
            else:
                s3upload__secret_key_e = ''
                s3upload__secret_key = ''


            mqttpublish__password = str(config['MQTTPUBLISH']['PASSWORD'])
            if mqttpublish__password:
                mqttpublish__password_e = f_key.encrypt(mqttpublish__password.encode()).decode()
                mqttpublish__password = ''
            else:
                mqttpublish__password_e = ''
                mqttpublish__password = ''


            syncapi__apikey = str(config['SYNCAPI']['APIKEY'])
            if syncapi__apikey:
                syncapi__apikey_e = f_key.encrypt(syncapi__apikey.encode()).decode()
                syncapi__apikey = ''
            else:
                syncapi__apikey_e = ''
                syncapi__apikey = ''


            pycurl_camera__password = str(config['PYCURL_CAMERA']['PASSWORD'])
            if pycurl_camera__password:
                pycurl_camera__password_e = f_key.encrypt(pycurl_camera__password.encode()).decode()
                pycurl_camera__password = ''
            else:
                pycurl_camera__password_e = ''
                pycurl_camera__password = ''

        else:
            # passwords should not be encrypted
            encrypted = False

            filetransfer__password = str(config['FILETRANSFER']['PASSWORD'])
            filetransfer__password_e = ''
            s3upload__secret_key = str(config['S3UPLOAD']['SECRET_KEY'])
            s3upload__secret_key_e = ''
            mqttpublish__password = str(config['MQTTPUBLISH']['PASSWORD'])
            mqttpublish__password_e = ''
            syncapi__apikey = str(config['SYNCAPI']['APIKEY'])
            syncapi__apikey_e = ''
            pycurl_camera__password = str(config['PYCURL_CAMERA']['PASSWORD'])
            pycurl_camera__password_e = ''


        config['FILETRANSFER']['PASSWORD'] = filetransfer__password
        config['FILETRANSFER']['PASSWORD_E'] = filetransfer__password_e
        config['S3UPLOAD']['SECRET_KEY'] = s3upload__secret_key
        config['S3UPLOAD']['SECRET_KEY_E'] = s3upload__secret_key_e
        config['MQTTPUBLISH']['PASSWORD'] = mqttpublish__password
        config['MQTTPUBLISH']['PASSWORD_E'] = mqttpublish__password_e
        config['SYNCAPI']['APIKEY'] = syncapi__apikey
        config['SYNCAPI']['APIKEY_E'] = syncapi__apikey_e
        config['PYCURL_CAMERA']['PASSWORD'] = pycurl_camera__password
        config['PYCURL_CAMERA']['PASSWORD_E'] = pycurl_camera__password_e


        return config, encrypted


class IndiAllSkyConfigUtil(IndiAllSkyConfig):

    def __init__(self):
        # not calling parent constructor
        self._config = self.base_config.copy()  # populate initial values


    def bootstrap(self, **kwargs):
        with app.app_context():
            self._bootstrap(**kwargs)


    def _bootstrap(self, **kwargs):
        try:
            self._getConfigEntry()

            logger.warning('Configuration already initialized')

            sys.exit(1)
        except NoResultFound:
            pass


        self._createSystemAccount()


        logger.info('Creating initial configuration')
        self.save('system', 'Initial config')


    def list(self, **kwargs):
        with app.app_context():
            self._list(**kwargs)


    def _list(self, **kwargs):
        table = PrettyTable()
        table.field_names = ['ID', 'Create Date', 'User ID', 'Level', 'Note']

        config_list = IndiAllSkyDbConfigTable.query\
            .order_by(IndiAllSkyDbConfigTable.createDate.desc())

        for config in config_list:
            table.add_row([config.id, config.createDate, config.user_id, config.level, config.note])

        print(table)


    def load(self, **kwargs):
        with app.app_context():
            self._load(**kwargs)


    def _load(self, **kwargs):
        f_config = kwargs['config']
        force = kwargs['force']

        if not force:
            try:
                self._getConfigEntry()

                logger.error('Configuration already defined, not loading config')

                sys.exit(1)
            except NoResultFound:
                pass


        self._createSystemAccount()


        c = json.loads(f_config.read(), object_pairs_hook=OrderedDict)
        f_config.close()

        self.config.update(c)

        logger.info('Loading configuration from file')
        self.save('system', 'Load config: {0:s}'.format(f_config.name))


    def update_level(self, **kwargs):
        with app.app_context():
            self._update_level(**kwargs)


    def _update_level(self, **kwargs):
        # fetch latest config
        try:
            config_entry = self._getConfigEntry()
        except NoResultFound:
            logger.error('Configuration not loaded')
            sys.exit(1)


        self._config.update(config_entry.data)

        logger.info('Updating config level')
        self.save('system', 'Update config level: {0:s}'.format(__config_level__))


    def edit(self, **kwargs):
        with app.app_context():
            self._edit(**kwargs)


    def _edit(self, **kwargs):
        try:
            config_entry = self._getConfigEntry()
        except NoResultFound:
            logger.error('Configuration not loaded')
            sys.exit(1)


        self._config.update(config_entry.data)

        self._config = self._decrypt_passwords()

        config_temp_f = tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json')
        config_temp_f.write(json.dumps(self.config, indent=4))
        config_temp_f.close()

        config_temp_p = Path(config_temp_f.name)

        initial_mtime = config_temp_p.stat().st_mtime


        while True:
            # execute until JSON is correctly formatted
            os.system('editor {0:s}'.format(str(config_temp_p)))

            try:
                with io.open(str(config_temp_p), 'r') as f_config:
                    new_config = json.loads(f_config.read(), object_pairs_hook=OrderedDict)

                break
            except json.JSONDecodeError:
                logger.error('JSON formatting error')
                time.sleep(3.0)


        if config_temp_p.stat().st_mtime == initial_mtime:
            logger.info('Config not updated')
            config_temp_p.unlink()  # cleanup
            return


        self.config.update(new_config)

        logger.info('Saving new config')
        self.save('system', 'CLI config edit')

        config_temp_p.unlink()  # cleanup


    def revert(self, **kwargs):
        with app.app_context():
            self._revert(**kwargs)


    def _revert(self, **kwargs):
        revert_id = kwargs['config_id']

        try:
            revert_entry = self._getConfigEntry(config_id=revert_id)
        except NoResultFound:
            logger.error('Configuration ID %d not found', int(revert_id))
            sys.exit(1)


        self._config.update(revert_entry.data)

        logger.info('Reverting configuration')
        self.save('system', 'Revert to config: {0:d}'.format(revert_entry.id))


    def dump(self, **kwargs):
        with app.app_context():
            self._dump(**kwargs)


    def _dump(self, **kwargs):
        dump_id = kwargs['config_id']

        try:
            dump_entry = self._getConfigEntry(config_id=dump_id)
        except NoResultFound:
            logger.error('Configuration ID %d not found', int(dump_id))
            sys.exit(1)

        self._config.update(dump_entry.data)

        self._config = self._decrypt_passwords()

        logger.info('Dumping config')

        print(json.dumps(self._config, indent=4))


    def user_count(self, **kwargs):
        with app.app_context():
            self._user_count(**kwargs)


    def _user_count(self, **kwargs):
        user_count = IndiAllSkyDbUserTable.query.count()
        print('{0:d}'.format(user_count))


    def flush(self, **kwargs):
        with app.app_context():
            self._flush(**kwargs)


    def _flush(self, **kwargs):
        confirm1 = input('\nConfirm flushing all configs? [y/n] ')
        if confirm1.lower() != 'y':
            logger.warning('Cancel flush')
            sys.exit(1)

        confirm2 = input('\nAre you lying? [y/n] ')
        if confirm2.lower() != 'n':
            logger.warning('Cancel flush')
            sys.exit(1)

        rand_int = random.randint(1000, 9999)
        confirm3 = input('\nEnter the number {0:d} backwards to confirm: '.format(rand_int))
        if confirm3 != str(rand_int)[::-1]:
            logger.warning('Cancel flush')
            sys.exit(1)

        configs_all = IndiAllSkyDbConfigTable.query
        configs_all.delete()
        db.session.commit()

        logger.info('All configurations have been deleted')


    def _createSystemAccount(self):
        try:
            system_user = IndiAllSkyDbUserTable.query\
                .filter(IndiAllSkyDbUserTable.username == 'system')\
                .one()

            return system_user
        except NoResultFound:
            pass


        system_user = IndiAllSkyDbUserTable(
            username='system',
            password='disabled',
            name='Internal System Account',
            email='system@indi-allsky',
            active=False,
            admin=True,
        )

        db.session.add(system_user)
        db.session.commit()

        return system_user

