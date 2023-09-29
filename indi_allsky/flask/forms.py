import os
from pathlib import Path
import io
import re
import json
import time
from datetime import datetime
import tempfile
import subprocess
import pycurl

from passlib.hash import argon2

from .. import constants

from flask_wtf import FlaskForm
from wtforms import IntegerField
from wtforms import FloatField
from wtforms import BooleanField
from wtforms import SelectField
from wtforms import StringField
from wtforms import PasswordField
from wtforms import TextAreaField
from wtforms import HiddenField
from wtforms import DateTimeLocalField
from wtforms.widgets import PasswordInput
from wtforms.validators import DataRequired
from wtforms.validators import ValidationError

from sqlalchemy import extract
#from sqlalchemy import asc
from sqlalchemy import func
#from sqlalchemy.types import DateTime
#from sqlalchemy.types import Date
from sqlalchemy import and_
from sqlalchemy import or_
from sqlalchemy.orm.exc import NoResultFound
from sqlalchemy.sql.expression import true as sa_true
from sqlalchemy.sql.expression import false as sa_false
from sqlalchemy.sql.expression import null as sa_null

from flask import current_app as app

from .models import IndiAllSkyDbCameraTable
from .models import IndiAllSkyDbImageTable
from .models import IndiAllSkyDbVideoTable
from .models import IndiAllSkyDbKeogramTable
from .models import IndiAllSkyDbStarTrailsTable
from .models import IndiAllSkyDbStarTrailsVideoTable
from .models import IndiAllSkyDbFitsImageTable
from .models import IndiAllSkyDbRawImageTable

from . import db


def SQLALCHEMY_DATABASE_URI_validator(form, field):
    host_regex = r'^[a-zA-Z0-9_\.\-\:\/\@]+$'

    if not re.search(host_regex, field.data):
        raise ValidationError('Invalid URI')


def CAMERA_INTERFACE_validator(form, field):
    if field.data not in (
        'indi',
        'indi_passive',
        'libcamera_imx477',
        'libcamera_imx378',
        'libcamera_ov5647',
        'libcamera_imx219',
        'libcamera_imx519',
        'libcamera_64mp_hawkeye',
        'libcamera_imx708',
        'libcamera_imx296_gs',
        'libcamera_imx290',
        'libcamera_imx462',
    ):
        raise ValidationError('Invalid camera interface')


def INDI_SERVER_validator(form, field):
    if not field.data:
        return

    host_regex = r'^[a-zA-Z0-9_\.\-]+$'  # include _ for docker

    if not re.search(host_regex, field.data):
        raise ValidationError('Invalid host name')


def INDI_PORT_validator(form, field):
    if not isinstance(field.data, int):
        raise ValidationError('Please enter valid number')

    if field.data < 0:
        raise ValidationError('Port must be 0 or greater')

    if field.data > 65535:
        raise ValidationError('Port must be less than 65535')


def INDI_CAMERA_NAME_validator(form, field):
    if not field.data:
        return

    camera_regex = r'^[a-zA-Z0-9\ \-]+$'

    if not re.search(camera_regex, field.data):
        raise ValidationError('Invalid camera name')


def OWNER_validator(form, field):
    if not field.data:
        return

    owner_regex = r'^[a-zA-Z0-9\_\.\ \-\@]+$'

    if not re.search(owner_regex, field.data):
        raise ValidationError('Invalid characters in owner name')


def LENS_NAME_validator(form, field):
    if not field.data:
        return

    lens_regex = r'^[a-zA-Z0-9\.\ \-\/]+$'

    if not re.search(lens_regex, field.data):
        raise ValidationError('Invalid lens name')


def LENS_FOCAL_LENGTH_validator(form, field):
    if not isinstance(field.data, (int, float)):
        raise ValidationError('Please enter valid number')

    if field.data <= 0.0:
        raise ValidationError('Focal length must be greater than 0')


def LENS_FOCAL_RATIO_validator(form, field):
    if not isinstance(field.data, (int, float)):
        raise ValidationError('Please enter valid number')

    if field.data <= 0.0:
        raise ValidationError('Focal ratio must be greater than 0')


def LENS_IMAGE_CIRCLE_validator(form, field):
    if not isinstance(field.data, int):
        raise ValidationError('Please enter valid number')

    if field.data <= 0:
        raise ValidationError('Focal ratio must be greater than 0')


def LENS_ALTITUDE_validator(form, field):
    if not isinstance(field.data, (int, float)):
        raise ValidationError('Please enter valid number')

    if field.data < 0.0:
        raise ValidationError('Altitude must be 0 or greater')

    if field.data > 90.0:
        raise ValidationError('Altitude must be 90 or less')


def LENS_AZIMUTH_validator(form, field):
    if not isinstance(field.data, (int, float)):
        raise ValidationError('Please enter valid number')

    if field.data < 0.0:
        raise ValidationError('Azimuth must be 0 or greater')

    if field.data > 360.0:
        raise ValidationError('Azimuth must be 360 or less')


def ccd_GAIN_validator(form, field):
    if not isinstance(field.data, int):
        raise ValidationError('Please enter valid number')

    if field.data < 0:
        raise ValidationError('Gain must be 0 or higher')


def ccd_BINNING_validator(form, field):
    if field.data <= 0:
        raise ValidationError('Bin mode must be more than 0')

    if field.data > 4:
        raise ValidationError('Bin mode must be less than 4')


def CCD_EXPOSURE_MAX_validator(form, field):
    if field.data <= 0.0:
        raise ValidationError('Max Exposure must be more than 0')

    if field.data > 60.0:
        raise ValidationError('Max Exposure cannot be more than 60')


def CCD_EXPOSURE_DEF_validator(form, field):
    if not isinstance(field.data, (int, float)):
        raise ValidationError('Please enter valid number')

    if field.data < 0.0:
        raise ValidationError('Default Exposure must be 0 or more')

    if field.data > 60.0:
        raise ValidationError('Default Exposure cannot be more than 60')


def CCD_EXPOSURE_MIN_validator(form, field):
    if not isinstance(field.data, (int, float)):
        raise ValidationError('Please enter valid number')

    if field.data < 0.0:
        raise ValidationError('Minimum Exposure must be 0 or more')

    if field.data > 60.0:
        raise ValidationError('Minimum Exposure cannot be more than 60')


def EXPOSURE_PERIOD_validator(form, field):
    if not isinstance(field.data, (int, float)):
        raise ValidationError('Please enter valid number')

    if field.data < 1.0:
        raise ValidationError('Exposure period must be 1.0 or more')


def EXPOSURE_PERIOD_DAY_validator(form, field):
    if not isinstance(field.data, (int, float)):
        raise ValidationError('Please enter valid number')

    if field.data < 1.0:
        raise ValidationError('Exposure period must be 1.0 or more')


def CCD_BIT_DEPTH_validator(form, field):
    if int(field.data) not in (0, 8, 10, 12, 14, 16):
        raise ValidationError('Bits must be 0, 8, 10, 12, 14, or 16 ')


def CCD_TEMP_validator(form, field):
    if not isinstance(field.data, (int, float)):
        raise ValidationError('Please enter valid number')

    if field.data < -50:
        raise ValidationError('Temperature must be greater than -50')


def FOCUS_DELAY_validator(form, field):
    if not isinstance(field.data, (int, float)):
        raise ValidationError('Please enter valid number')

    if field.data < 1.0:
        raise ValidationError('Focus delay must be 1.0 or more')


def CFA_PATTERN_validator(form, field):
    if not field.data:
        return

    cfa_list = ('GRBG', 'RGGB', 'BGGR', 'GBRG')
    if field.data not in cfa_list:
        raise ValidationError('Please select a valid pattern')


def WB_FACTOR_validator(form, field):
    if not isinstance(field.data, (int, float)):
        raise ValidationError('Please enter valid number')

    if field.data < 0.0:
        raise ValidationError('Balance factor must be 0 or greater')

    if field.data > 4.0:
        raise ValidationError('Balance factor must be less than 4.0')


def SATURATION_FACTOR_validator(form, field):
    if not isinstance(field.data, (int, float)):
        raise ValidationError('Please enter valid number')

    if field.data < 0.0:
        raise ValidationError('Saturation factor must be 0 or greater')

    if field.data > 4.0:
        raise ValidationError('Saturation factor must be less than 4.0')


def SCNR_ALGORITHM_validator(form, field):
    if not field.data:
        return

    scnr_list = ('average_neutral', 'maximum_neutral')
    if field.data not in scnr_list:
        raise ValidationError('Please select a valid algorithm')


def TEMP_DISPLAY_validator(form, field):
    if field.data not in ('c', 'f', 'k'):
        raise ValidationError('Please select the temperature system for display')


def CCD_TEMP_SCRIPT_validator(form, field):
    if not field.data:
        return


    temp_script_p = Path(field.data)

    if not temp_script_p.exists():
        raise ValidationError('Temperature script does not exist')

    if not temp_script_p.is_file():
        raise ValidationError('Temperature script is not a file')

    if temp_script_p.stat().st_size == 0:
        raise ValidationError('Temperature script is empty')

    if not os.access(str(temp_script_p), os.X_OK):
        raise ValidationError('Temperature script is not executable')


    # generate a tempfile for the data
    f_tmp_tempjson = tempfile.NamedTemporaryFile(mode='w', delete=True, suffix='.json')
    f_tmp_tempjson.close()

    tempjson_name_p = Path(f_tmp_tempjson.name)


    cmd = [
        str(temp_script_p),
    ]


    # the file used for the json data is communicated via environment variable
    cmd_env = {
        'TEMP_JSON' : str(tempjson_name_p),
    }

    try:
        temp_process = subprocess.Popen(
            cmd,
            env=cmd_env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except OSError:
        raise ValidationError('Temperature script failed to execute')


    try:
        temp_process.wait(timeout=3.0)
    except subprocess.TimeoutExpired:
        temp_process.kill()
        time.sleep(1.0)
        temp_process.poll()  # close out process
        raise ValidationError('Temperature script timed out')


    if temp_process.returncode != 0:
        raise ValidationError('Temperature script returned exited abnormally')


    try:
        with io.open(str(tempjson_name_p), 'r') as tempjson_name_f:
            temp_data = json.load(tempjson_name_f)

        tempjson_name_p.unlink()  # remove temp file
    except PermissionError as e:
        app.logger.error(str(e))
        raise ValidationError(str(e))
    except json.JSONDecodeError as e:
        app.logger.error('Error decoding json: %s', str(e))
        raise ValidationError(str(e))
    except FileNotFoundError as e:
        raise ValidationError(str(e))


    try:
        float(temp_data['temp'])
    except ValueError:
        raise ValidationError('Temperature script returned a non-numerical value')
    except KeyError:
        raise ValidationError('Temperature script returned incorrect data')



def TARGET_ADU_validator(form, field):
    if field.data <= 0:
        raise ValidationError('Target ADU must be greater than 0')

    if field.data > 255 :
        raise ValidationError('Target ADU must be less than 255')


def TARGET_ADU_DAY_validator(form, field):
    if field.data <= 0:
        raise ValidationError('Target ADU must be greater than 0')

    if field.data > 255 :
        raise ValidationError('Target ADU must be less than 255')


def TARGET_ADU_DEV_validator(form, field):
    if field.data <= 0:
        raise ValidationError('Target ADU Deviation must be greater than 0')

    if field.data > 100 :
        raise ValidationError('Target ADU must be less than 100')


def TARGET_ADU_DEV_DAY_validator(form, field):
    if field.data <= 0:
        raise ValidationError('Target ADU Deviation must be greater than 0')

    if field.data > 100 :
        raise ValidationError('Target ADU must be less than 100')


def ADU_ROI_validator(form, field):
    if not isinstance(field.data, int):
        raise ValidationError('Please enter valid number')

    if field.data < 0:
        raise ValidationError('ADU Region of Interest must be 0 or greater')


def SQM_ROI_validator(form, field):
    if not isinstance(field.data, int):
        raise ValidationError('Please enter valid number')

    if field.data < 0:
        raise ValidationError('SQM Region of Interest must be 0 or greater')


def ADU_FOV_DIV_validator(form, field):
    if int(field.data) not in (2, 3, 4, 6):
        raise ValidationError('ADU FoV divisor must be 2, 3, 4, 5, or 6')


def SQM_FOV_DIV_validator(form, field):
    if int(field.data) not in (2, 3, 4, 6):
        raise ValidationError('SQM FoV divisor must be 2, 3, 4, 5, or 6')


def DETECT_STARS_THOLD_validator(form, field):
    if not isinstance(field.data, (int, float)):
        raise ValidationError('Please enter valid number')

    if field.data <= 0.0:
        raise ValidationError('Threshold must be greater than 0')

    if field.data > 1.0:
        raise ValidationError('Threshold must be 1.0 or less')


def LOCATION_NAME_validator(form, field):
    if not field.data:
        return

    name_regex = r'^[a-zA-Z0-9_,\.\-\/\:\ ]+$'

    if not re.search(name_regex, field.data):
        raise ValidationError('Invalid name')


def LOCATION_LATITUDE_validator(form, field):
    if not isinstance(field.data, (int, float)):
        raise ValidationError('Please enter valid number')

    if field.data < -90:
        raise ValidationError('Latitude must be greater than -90')

    if field.data > 90:
        raise ValidationError('Latitude must be less than 90')


def LOCATION_LONGITUDE_validator(form, field):
    if not isinstance(field.data, (int, float)):
        raise ValidationError('Please enter valid number')

    if field.data < -180:
        raise ValidationError('Longitude must be greater than -180')

    if field.data > 180:
        raise ValidationError('Longitude must be less than 180')


def LOCATION_ELEVATION_validator(form, field):
    if not isinstance(field.data, int):
        raise ValidationError('Please enter valid number')


def CLAHE_CLIPLIMIT_validator(form, field):
    if not isinstance(field.data, (int, float)):
        raise ValidationError('Please enter valid number')

    if field.data <= 0:
        raise ValidationError('Clip limit must be greater than 0')

    if field.data > 60:
        raise ValidationError('Clip limit must be less than 60')


def CLAHE_GRIDSIZE_validator(form, field):
    if not isinstance(field.data, int):
        raise ValidationError('Please enter valid number')

    if field.data < 4:
        raise ValidationError('Grid size must be 4 or greater')

    if field.data > 64:
        raise ValidationError('Clip limit must be 64 or less')


def NIGHT_SUN_ALT_DEG_validator(form, field):
    if not isinstance(field.data, (int, float)):
        raise ValidationError('Please enter valid number')

    if field.data < -90:
        raise ValidationError('Sun altitude must be greater than -90')

    if field.data > 90:
        raise ValidationError('Sun altitude must be less than 90')


def NIGHT_MOONMODE_ALT_DEG_validator(form, field):
    if not isinstance(field.data, (int, float)):
        raise ValidationError('Please enter valid number')

    if field.data < -90:
        raise ValidationError('Moon altitude must be greater than -90')

    # 91 is disabled
    if field.data > 91:
        raise ValidationError('Moon altitude must be less than 90')


def NIGHT_MOONMODE_PHASE_validator(form, field):
    if not isinstance(field.data, (int, float)):
        raise ValidationError('Please enter valid number')

    if field.data < 0:
        raise ValidationError('Moon illumination must be 0 or greater')

    if field.data > 100:
        raise ValidationError('Moon illumination must be 100 or less')


def IMAGE_LABEL_SYSTEM_validator(form, field):
    if not field.data:
        return

    if field.data not in ['opencv', 'pillow']:
        raise ValidationError('Unknown label system')


def IMAGE_LABEL_TEMPLATE_validator(form, field):
    now = datetime.now()

    test_data = {
        'timestamp'  : now,
        'ts'         : now,
        'day_date'   : now.date(),
        'exposure'   : 1.0,
        'rational_exp' : '',
        'gain'       : 1,
        'temp'       : -5.1,
        'temp_unit'  : 'C',
        'sqm'        : 8000.0,
        'stars'      : 1,
        'detections' : 'True',
        'owner'      : 'foobar',
        'sun_alt'    : 0.0,
        'moon_alt'   : 0.0,
        'moon_phase' : 0.0,
        'moon_up'    : 'No',
        'sun_moon_sep' : 0.0,
        'mercury_alt'  : 0.0,
        'mercury_up'   : 'No',
        'venus_alt'    : 0.0,
        'venus_phase'  : 0.0,
        'venus_up'     : 'No',
        'mars_alt'     : 0.0,
        'mars_up'      : 'No',
        'jupiter_alt'  : 0.0,
        'jupiter_up'   : 'No',
        'saturn_alt'   : 0.0,
        'saturn_up'    : 'No',
        'iss_alt'      : 0.0,
        'iss_up'       : 'No',
        'iss_next_h'   : 0.0,
        'iss_next_alt' : 0.0,
        'hst_alt'      : 0.0,
        'hst_up'       : 'No',
        'hst_next_h'   : 0.0,
        'hst_next_alt' : 0.0,
        'location'     : 'here',
        'kpindex'      : 0.0,
        'ovation_max'  : 0,
        'smoke_rating' : 'foobar',
        'latitude'     : 0.0,
        'longitude'    : 0.0,
        'stack_method' : 'foo',
        'stack_count'  : 1,
        'sidereal_time' : 'foo',
        'stretch' : 'Off',
        'stretch_m1_gamma' : 0.0,
        'stretch_m1_stddevs' : 0.0,
    }

    try:
        field.data.format(**test_data)
    except KeyError as e:
        raise ValidationError('KeyError: {0:s}'.format(str(e)))
    except ValueError as e:
        raise ValidationError('ValueError: {0:s}'.format(str(e)))


def WEB_EXTRA_TEXT_validator(form, field):
    if not field.data:
        return

    folder_regex = r'^[a-zA-Z0-9_\.\-\/\ ]+$'

    if not re.search(folder_regex, field.data):
        raise ValidationError('Invalid file name')


    web_extra_text_p = Path(field.data)

    try:
        if not web_extra_text_p.exists():
            raise ValidationError('File does not exist')

        if not web_extra_text_p.is_file():
            raise ValidationError('Not a file')

        # Sanity check
        if web_extra_text_p.stat().st_size > 10000:
            raise ValidationError('File is too large')

        with io.open(str(web_extra_text_p), 'r'):
            pass
    except PermissionError as e:
        raise ValidationError(str(e))


def IMAGE_STRETCH__MODE1_GAMMA_validator(form, field):
    if not isinstance(field.data, (int, float)):
        raise ValidationError('Please enter valid number')

    if field.data < 0:
        raise ValidationError('Gamma must be 0 or greater')


def IMAGE_STRETCH__MODE1_STDDEVS_validator(form, field):
    if not isinstance(field.data, (int, float)):
        raise ValidationError('Please enter valid number')

    if field.data < 1:
        raise ValidationError('Standard deviations must be 1.0 or greater')


def IMAGE_ROTATE_validator(form, field):
    import cv2

    if not field.data:
        return

    if field.data not in ['ROTATE_90_CLOCKWISE', 'ROTATE_90_COUNTERCLOCKWISE', 'ROTATE_180']:
        raise ValidationError('Unknown rotation option')

    # sanity check
    try:
        getattr(cv2, field.data)
    except AttributeError as e:
        raise ValidationError(str(e))


def IMAGE_ROTATE_ANGLE_validator(form, field):
    if not isinstance(field.data, int):
        raise ValidationError('Please enter valid number')


    if field.data < -180:
        raise ValidationError('Rotation angle must be -180 or greater')

    if field.data > 180:
        raise ValidationError('Rotation angle must be 180 or less')


def KEOGRAM_ANGLE_validator(form, field):
    if not isinstance(field.data, (int, float)):
        raise ValidationError('Please enter valid number')

    if field.data < -180:
        raise ValidationError('Rotation angle must be -180 or greater')

    if field.data > 180:
        raise ValidationError('Rotation angle must be 180 or less')


def KEOGRAM_H_SCALE_validator(form, field):
    if field.data <= 0:
        raise ValidationError('Keogram Horizontal Scaling factor must be greater than 0')

    if field.data > 100:
        raise ValidationError('Keogram Horizontal Scaling factor must be 100 or less')


def KEOGRAM_V_SCALE_validator(form, field):
    if field.data <= 0:
        raise ValidationError('Keogram Verticle Scaling factor must be greater than 0')

    if field.data > 100:
        raise ValidationError('Keogram Verticle Scaling factor must be 100 or less')


def STARTRAILS_MAX_ADU_validator(form, field):
    if field.data <= 0:
        raise ValidationError('Star Trails Max ADU must be greater than 0')

    if field.data > 255:
        raise ValidationError('Star Trails Max ADU must be 255 or less')


def STARTRAILS_MASK_THOLD_validator(form, field):
    if field.data <= 0:
        raise ValidationError('Star Trails Mask Threshold must be greater than 0')

    if field.data > 255:
        raise ValidationError('Star Trails Mask Threshold must be 255 or less')


def STARTRAILS_PIXEL_THOLD_validator(form, field):
    if not isinstance(field.data, (int, float)):
        raise ValidationError('Please enter valid number')

    if field.data < 0:
        raise ValidationError('Star Trails Pixel Threshold must be 0 or greater')

    if field.data > 100:
        raise ValidationError('Star Trails Pixel Threshold must be 100 or less')


def STARTRAILS_TIMELAPSE_MINFRAMES_validator(form, field):
    if not isinstance(field.data, int):
        raise ValidationError('Please enter valid number')

    if field.data < 25:
        raise ValidationError('Star Trails Timelapse Minimum Frames must be 25 or more')


def STARTRAILS_SUN_ALT_THOLD_validator(form, field):
    if not isinstance(field.data, (int, float)):
        raise ValidationError('Please enter valid number')

    if field.data < -90:
        raise ValidationError('Sun altitude must be greater than -90')

    if field.data > 90:
        raise ValidationError('Sun altitude must be less than 90')


def STARTRAILS_MOON_ALT_THOLD_validator(form, field):
    if not isinstance(field.data, (int, float)):
        raise ValidationError('Please enter valid number')

    if field.data < -90:
        raise ValidationError('Moon altitude must be greater than -90')

    if field.data > 91:
        raise ValidationError('Moon altitude must be less than 91')


def STARTRAILS_MOON_PHASE_THOLD_validator(form, field):
    if not isinstance(field.data, (int, float)):
        raise ValidationError('Please enter valid number')

    if field.data < 0:
        raise ValidationError('Moon phase must be greater than 0')

    if field.data > 101:
        raise ValidationError('Moon phase must be less than 101')


def IMAGE_FILE_TYPE_validator(form, field):
    if field.data not in ('jpg', 'png', 'tif', 'webp'):
        raise ValidationError('Please select a valid file type')


def IMAGE_FILE_COMPRESSION__JPG_validator(form, field):
    if field.data < 1:
        raise ValidationError('JPEG compression must be 1 or greater')

    if field.data > 100:
        raise ValidationError('JPEG compression must be 100 or less')


def IMAGE_FILE_COMPRESSION__PNG_validator(form, field):
    if field.data < 1:
        raise ValidationError('PNG compression must be 1 or greater')

    if field.data > 9:
        raise ValidationError('PNG compression must be 9 or less')


def IMAGE_FOLDER_validator(form, field):
    folder_regex = r'^[a-zA-Z0-9_\.\-\/]+$'

    if not re.search(folder_regex, field.data):
        raise ValidationError('Invalid folder name')

    if re.search(r'\/$', field.data):
        raise ValidationError('Directory cannot end with slash')


    image_folder_p = Path(field.data)

    try:
        if not image_folder_p.exists():
            image_folder_p.mkdir(mode=0o755, parents=True)

        if not image_folder_p.is_dir():
            raise ValidationError('Path is not a directory')
    except PermissionError as e:
        raise ValidationError(str(e))


def IMAGE_EXPORT_FOLDER_validator(form, field):
    folder_regex = r'^[a-zA-Z0-9_\.\-\/]+$'

    if not re.search(folder_regex, field.data):
        raise ValidationError('Invalid folder name')

    if re.search(r'\/$', field.data):
        raise ValidationError('Directory cannot end with slash')


    image_folder_p = Path(field.data)

    try:
        if not image_folder_p.exists():
            image_folder_p.mkdir(mode=0o755, parents=True)

        if not image_folder_p.is_dir():
            raise ValidationError('Path is not a directory')
    except PermissionError as e:
        raise ValidationError(str(e))


def IMAGE_EXPORT_RAW_validator(form, field):
    if not field.data:
        return

    if field.data not in ('png', 'tif', 'jpg', 'jp2', 'webp'):
        raise ValidationError('Please select a valid file type')


def IMAGE_EXTRA_TEXT_validator(form, field):
    if not field.data:
        return

    folder_regex = r'^[a-zA-Z0-9_\.\-\/\ ]+$'

    if not re.search(folder_regex, field.data):
        raise ValidationError('Invalid file name')


    image_extra_text_p = Path(field.data)

    try:
        if not image_extra_text_p.exists():
            raise ValidationError('File does not exist')

        if not image_extra_text_p.is_file():
            raise ValidationError('Not a file')

        # Sanity check
        if image_extra_text_p.stat().st_size > 10000:
            raise ValidationError('File is too large')

        with io.open(str(image_extra_text_p), 'r'):
            pass
    except PermissionError as e:
        raise ValidationError(str(e))


def DETECT_MASK_validator(form, field):
    import numpy
    import cv2

    if not field.data:
        return

    folder_regex = r'^[a-zA-Z0-9_\.\-\/\ ]+$'
    if not re.search(folder_regex, field.data):
        raise ValidationError('Invalid file name')

    ext_regex = r'\.png$'
    if not re.search(ext_regex, field.data, re.IGNORECASE):
        raise ValidationError('Mask file must be a PNG')

    detect_mask_p = Path(field.data)

    try:
        if not detect_mask_p.exists():
            raise ValidationError('File does not exist')

        if not detect_mask_p.is_file():
            raise ValidationError('Not a file')

        with io.open(str(detect_mask_p), 'r'):
            pass
    except PermissionError as e:
        raise ValidationError(str(e))


    mask_data = cv2.imread(str(detect_mask_p), cv2.IMREAD_GRAYSCALE)
    if isinstance(mask_data, type(None)):
        raise ValidationError('File is not a valid image')

    if numpy.count_nonzero(mask_data == 255) == 0:
        raise ValidationError('Mask image is all black')


def LOGO_OVERLAY_validator(form, field):
    import cv2

    if not field.data:
        return

    folder_regex = r'^[a-zA-Z0-9_\.\-\/\ ]+$'
    if not re.search(folder_regex, field.data):
        raise ValidationError('Invalid file name')

    ext_regex = r'\.png$'
    if not re.search(ext_regex, field.data, re.IGNORECASE):
        raise ValidationError('Mask file must be a PNG')

    detect_mask_p = Path(field.data)

    try:
        if not detect_mask_p.exists():
            raise ValidationError('File does not exist')

        if not detect_mask_p.is_file():
            raise ValidationError('Not a file')

        with io.open(str(detect_mask_p), 'r'):
            pass
    except PermissionError as e:
        raise ValidationError(str(e))


    mask_data = cv2.imread(str(detect_mask_p), cv2.IMREAD_UNCHANGED)
    if isinstance(mask_data, type(None)):
        raise ValidationError('File is not a valid image')

    try:
        if mask_data.shape[2] != 4:
            raise ValidationError('Mask does not contain an alpha channel')
    except IndexError:
        raise ValidationError('Mask does not contain an alpha channel')


def IMAGE_SCALE_validator(form, field):
    if field.data < 1:
        raise ValidationError('Image Scaling must be 1 or greater')

    if field.data > 100:
        raise ValidationError('Image Scaling must be 100 or less')


def IMAGE_CIRCLE_MASK__DIAMETER_validator(form, field):
    if not isinstance(field.data, int):
        raise ValidationError('Please enter valid number')

    if field.data < 100:
        raise ValidationError('Diameter must be 100 or greater')


def IMAGE_CIRCLE_MASK__OFFSET_X_validator(form, field):
    if not isinstance(field.data, int):
        raise ValidationError('Please enter valid number')


def IMAGE_CIRCLE_MASK__OFFSET_Y_validator(form, field):
    if not isinstance(field.data, int):
        raise ValidationError('Please enter valid number')


def IMAGE_CIRCLE_MASK__BLUR_validator(form, field):
    if not isinstance(field.data, int):
        raise ValidationError('Please enter valid number')

    if field.data < 0:
        raise ValidationError('Blur must be 0 or more')

    if field.data == 0:
        # 0 is disabled, but technically an even number
        pass
    elif field.data % 2 == 0:
        raise ValidationError('Blur must be an odd number')


def IMAGE_CIRCLE_MASK__OPACITY_validator(form, field):
    if not isinstance(field.data, int):
        raise ValidationError('Please enter valid number')

    if field.data < 0:
        raise ValidationError('Opacity must be 0 or more')


    if field.data > 100:
        raise ValidationError('Blur must be 100 or less')


def IMAGE_CROP_ROI_validator(form, field):
    if not isinstance(field.data, int):
        raise ValidationError('Please enter valid number')

    if field.data < 0:
        raise ValidationError('Crop Region of Interest must be 0 or greater')


def IMAGE_STACK_METHOD_validator(form, field):
    stack_methods = (
        'maximum',
        'average',
        'minimum',
    )

    if field.data not in stack_methods:
        raise ValidationError('Invalid selection')


def IMAGE_STACK_COUNT_validator(form, field):
    try:
        stack_count = int(field.data)
    except ValueError:
        raise ValidationError('Invalid data')

    if stack_count < 1:
        raise ValidationError('Stack count too low')

    # not validating max


def IMAGE_ALIGN_DETECTSIGMA_validator(form, field):
    if not isinstance(field.data, int):
        raise ValidationError('Please enter valid number')

    if field.data < 2:
        raise ValidationError('Detection Sigma must be 3 or greater')

    if field.data > 20:
        raise ValidationError('Detection Sigma must be 20 or less')


def IMAGE_ALIGN_POINTS_validator(form, field):
    if not isinstance(field.data, int):
        raise ValidationError('Please enter valid number')

    if field.data < 25:
        raise ValidationError('Detection points must be 25 or greater')

    if field.data > 200:
        raise ValidationError('Detection points must be 200 or less')


def IMAGE_ALIGN_SOURCEMINAREA_validator(form, field):
    if not isinstance(field.data, int):
        raise ValidationError('Please enter valid number')

    if field.data < 3:
        raise ValidationError('Source min area must be 3 or greater')

    if field.data > 25:
        raise ValidationError('Source min area must be 25 or less')


def IMAGE_EXPIRE_DAYS_validator(form, field):
    if not isinstance(field.data, int):
        raise ValidationError('Please enter valid number')

    if field.data < 1:
        raise ValidationError('Image Expiration must be 1 or greater')


def TIMELAPSE_EXPIRE_DAYS_validator(form, field):
    if not isinstance(field.data, int):
        raise ValidationError('Please enter valid number')

    if field.data < 1:
        raise ValidationError('Timelapse Expiration must be 1 or greater')


def FFMPEG_FRAMERATE_validator(form, field):
    # guessing
    if field.data < 10:
        raise ValidationError('FFMPEG frame rate must be 10 or greater')

    if field.data > 50:
        raise ValidationError('FFMPEG frame rate must be 50 or less')


def FFMPEG_BITRATE_validator(form, field):
    bitrate_regex = r'^\d+[km]$'

    if not re.search(bitrate_regex, field.data):
        raise ValidationError('Invalid bitrate syntax')


def FFMPEG_VFSCALE_validator(form, field):
    if not field.data:
        return

    scale_regex = r'^[a-z0-9\-\*\.]+\:[a-z0-9\-\*\.]+$'
    if not re.search(scale_regex, field.data):
        raise ValidationError('Invalid scale option')


def FFMPEG_CODEC_validator(form, field):
    if field.data not in list(zip(*form.FFMPEG_CODEC_choices))[0]:
        raise ValidationError('Invalid codec option')


def TEXT_PROPERTIES__FONT_FACE_validator(form, field):
    fonts = (
        'FONT_HERSHEY_SIMPLEX',
        'FONT_HERSHEY_PLAIN',
        'FONT_HERSHEY_DUPLEX',
        'FONT_HERSHEY_COMPLEX',
        'FONT_HERSHEY_TRIPLEX',
        'FONT_HERSHEY_COMPLEX_SMALL',
        'FONT_HERSHEY_SCRIPT_SIMPLEX',
        'FONT_HERSHEY_SCRIPT_COMPLEX',
    )

    if field.data not in fonts:
        raise ValidationError('Invalid selection')


def TEXT_PROPERTIES__FONT_HEIGHT_validator(form, field):
    if field.data < 1:
        raise ValidationError('Font height must be greater than 1')


def TEXT_PROPERTIES__FONT_X_validator(form, field):
    if field.data < 1:
        raise ValidationError('Font offset must be greater than 1')


def TEXT_PROPERTIES__FONT_Y_validator(form, field):
    if field.data < 1:
        raise ValidationError('Font offset must be greater than 1')


def TEXT_PROPERTIES__PIL_FONT_FILE_validator(form, field):
    if field.data not in list(zip(*form.TEXT_PROPERTIES__PIL_FONT_FILE_choices))[0]:
        raise ValidationError('Invalid font selection')


def TEXT_PROPERTIES__PIL_FONT_CUSTOM_validator(form, field):
    from PIL import ImageFont

    if not field.data:
        return

    font_file_p = Path(field.data)

    try:
        if not font_file_p.exists():
            raise ValidationError('File does not exist')

        if not font_file_p.is_file():
            raise ValidationError('Path is not a file')
    except PermissionError as e:
        raise ValidationError(str(e))


    try:
        ImageFont.truetype(str(font_file_p), 30)
    except OSError as e:
        raise ValidationError(str(e))


def TEXT_PROPERTIES__PIL_FONT_SIZE_validator(form, field):
    if not isinstance(field.data, int):
        raise ValidationError('Please enter valid number')

    if field.data < 10:
        raise ValidationError('Size must be 10 or greater')


def RGB_COLOR_validator(form, field):
    color_regex = r'^\d+\,\d+\,\d+$'

    if not re.search(color_regex, field.data):
        raise ValidationError('Invalid syntax')

    rgb = field.data.split(',')
    for c in rgb:
        if int(c) < 0:
            raise ValidationError('Invalid syntax')
        elif int(c) > 255:
            raise ValidationError('Invalid syntax')


def TEXT_PROPERTIES__FONT_SCALE_validator(form, field):
    if field.data < 0.1:
        raise ValidationError('Font scale must be greater than 0.1')

    if field.data > 100:
        raise ValidationError('Font scale too large')


def TEXT_PROPERTIES__FONT_THICKNESS_validator(form, field):
    if field.data < 1:
        raise ValidationError('Font thickness must be 1 or more')

    if field.data > 20:
        raise ValidationError('Font thickness must be less than 20')


def ORB_PROPERTIES__MODE_validator(form, field):
    if field.data not in ('ha', 'az', 'alt', 'off'):
        raise ValidationError('Please select a valid orb mode')


def ORB_PROPERTIES__RADIUS_validator(form, field):
    if field.data < 1:
        raise ValidationError('Orb radius must be 1 or more')


def UPLOAD_WORKERS_validator(form, field):
    if not isinstance(field.data, int):
        raise ValidationError('Please enter valid number')

    if field.data < 1:
        raise ValidationError('Worker count must be 1 or greater')

    if field.data > 4:
        raise ValidationError('Worker count must be less than 5')


def FILETRANSFER__CLASSNAME_validator(form, field):
    class_names = (
        'pycurl_sftp',
        'paramiko_sftp',
        'pycurl_ftpes',
        'pycurl_ftps',
        'pycurl_ftp',
        'python_ftp',
        'python_ftpes',
        'pycurl_webdav_https',
    )

    if field.data not in class_names:
        raise ValidationError('Invalid selection')


def FILETRANSFER__HOST_validator(form, field):
    if not field.data:
        return

    host_regex = r'^[a-zA-Z0-9_\.\-]+$'  # include _ for docker

    if not re.search(host_regex, field.data):
        raise ValidationError('Invalid host name')


def MQTTPUBLISH__TRANSPORT_validator(form, field):
    valid_transports = (
        'tcp',
        'websockets',
    )

    if field.data not in valid_transports:
        raise ValidationError('Invalid transport')


def MQTTPUBLISH__HOST_validator(form, field):
    if not field.data:
        return

    host_regex = r'^[a-zA-Z0-9_\.\-]+$'  # include _ for docker

    if not re.search(host_regex, field.data):
        raise ValidationError('Invalid host name')


def FILETRANSFER__PORT_validator(form, field):
    if not isinstance(field.data, int):
        raise ValidationError('Please enter valid number')

    if field.data < 0:
        raise ValidationError('Port must be 0 or greater')

    if field.data > 65535:
        raise ValidationError('Port must be less than 65535')


def MQTTPUBLISH__PORT_validator(form, field):
    if not isinstance(field.data, int):
        raise ValidationError('Please enter valid number')

    if field.data < 1:
        raise ValidationError('Port must be 1 or greater')

    if field.data > 65535:
        raise ValidationError('Port must be less than 65535')


def FILETRANSFER__USERNAME_validator(form, field):
    if not field.data:
        return

    username_regex = r'^[a-zA-Z0-9_\@\.\-\\]+$'

    if not re.search(username_regex, field.data):
        raise ValidationError('Invalid username')


def MQTTPUBLISH__USERNAME_validator(form, field):
    if not field.data:
        return

    username_regex = r'^[a-zA-Z0-9_\@\.\-]+$'

    if not re.search(username_regex, field.data):
        raise ValidationError('Invalid username')


def SYNCAPI__USERNAME_validator(form, field):
    if not field.data:
        return

    username_regex = r'^[a-zA-Z0-9_\@\.\-]+$'

    if not re.search(username_regex, field.data):
        raise ValidationError('Invalid username')


def FILETRANSFER__PASSWORD_validator(form, field):
    pass


def MQTTPUBLISH__PASSWORD_validator(form, field):
    pass


def SYNCAPI__APIKEY_validator(form, field):
    pass


def FILETRANSFER__TIMEOUT_validator(form, field):
    if field.data < 1:
        raise ValidationError('Timeout must be 1.0 or greater')

    if field.data > 1200:
        raise ValidationError('Timeout must be 1200 or less')


def SYNCAPI__TIMEOUT_validator(form, field):
    if field.data < 1:
        raise ValidationError('Timeout must be 1.0 or greater')

    if field.data > 1200:
        raise ValidationError('Timeout must be 1200 or less')


def FILETRANSFER__PRIVATE_KEY_validator(form, field):
    if not field.data:
        return

    file_name_regex = r'^[a-zA-Z0-9_\.\-\/]+$'

    if not re.search(file_name_regex, field.data):
        raise ValidationError('Invalid filename syntax')


    file_name_p = Path(field.data)

    try:
        if not file_name_p.exists():
            raise ValidationError('File does not exist')

        if not file_name_p.is_file():
            raise ValidationError('Not a file')

        with io.open(str(file_name_p), 'r'):
            pass
    except PermissionError as e:
        raise ValidationError(str(e))


def FILETRANSFER__PUBLIC_KEY_validator(form, field):
    if not field.data:
        return

    file_name_regex = r'^[a-zA-Z0-9_\.\-\/]+$'

    if not re.search(file_name_regex, field.data):
        raise ValidationError('Invalid filename syntax')


    file_name_p = Path(field.data)

    try:
        if not file_name_p.exists():
            raise ValidationError('File does not exist')

        if not file_name_p.is_file():
            raise ValidationError('Not a file')

        with io.open(str(file_name_p), 'r'):
            pass
    except PermissionError as e:
        raise ValidationError(str(e))


def FILETRANSFER__REMOTE_IMAGE_NAME_validator(form, field):
    image_name_regex = r'^[a-zA-Z0-9_\.\-\{\}\:\%]+$'

    if not re.search(image_name_regex, field.data):
        raise ValidationError('Invalid filename syntax')


    now = datetime.now()

    test_list = ['jpg']
    test_data = {
        'timestamp'  : now,
        'ts'         : now,
        'ext'        : 'jpg',
        'day_date'   : now.date(),
    }

    try:
        field.data.format(*test_list, **test_data)
    except KeyError as e:
        raise ValidationError('KeyError: {0:s}'.format(str(e)))
    except ValueError as e:
        raise ValidationError('ValueError: {0:s}'.format(str(e)))


def FILETRANSFER__REMOTE_METADATA_NAME_validator(form, field):
    metadata_name_regex = r'^[a-zA-Z0-9_\.\-\{\}\:\%]+$'

    if not re.search(metadata_name_regex, field.data):
        raise ValidationError('Invalid filename syntax')


    now = datetime.now()

    test_data = {
        'timestamp'  : now,
        'ts'         : now,
        'day_date'   : now.date(),
    }

    try:
        field.data.format(**test_data)
    except KeyError as e:
        raise ValidationError('KeyError: {0:s}'.format(str(e)))
    except ValueError as e:
        raise ValidationError('ValueError: {0:s}'.format(str(e)))


def REMOTE_FOLDER_validator(form, field):
    folder_regex = r'^[a-zA-Z0-9_\.\-\/\{\}\:\%\~]+$'

    if not re.search(folder_regex, field.data):
        raise ValidationError('Invalid filename syntax')


    now = datetime.now()

    test_data = {
        'timestamp'  : now,
        'ts'         : now,
        'day_date'   : now.date(),
    }

    try:
        field.data.format(**test_data)
    except KeyError as e:
        raise ValidationError('KeyError: {0:s}'.format(str(e)))
    except ValueError as e:
        raise ValidationError('ValueError: {0:s}'.format(str(e)))


def FILETRANSFER__UPLOAD_IMAGE_validator(form, field):
    if not isinstance(field.data, int):
        raise ValidationError('Please enter valid number')

    if field.data < 0:
        raise ValidationError('Image Upload must be 0 or greater')


def SYNCAPI__UPLOAD_IMAGE_validator(form, field):
    if not isinstance(field.data, int):
        raise ValidationError('Please enter valid number')

    if field.data < 0:
        raise ValidationError('Image Upload must be 0 or greater')


def FILETRANSFER__LIBCURL_OPTIONS_validator(form, field):
    try:
        json_data = json.loads(field.data)
    except json.decoder.JSONDecodeError as e:
        raise ValidationError(str(e))


    client = pycurl.Curl()  # test client

    for k, v in json_data.items():
        if not isinstance(k, str):
            raise ValidationError('Property names must be a str')

        if not isinstance(v, (str, int)):
            raise ValidationError('Property {0:s} value must be a str or int'.format(k))


        if k.startswith('#'):
            # comment
            continue


        if k.startswith('CURLOPT_'):
            # remove CURLOPT_ prefix
            k = k[8:]


        try:
            curlopt = getattr(pycurl, k)
        except AttributeError:
            raise ValidationError('Invalid libcurl property: {0:s}'.format(k))

        try:
            client.setopt(curlopt, v)
        except pycurl.error as e:
            rc, msg = e.args

            if rc in [pycurl.E_UNKNOWN_OPTION]:
                raise ValidationError('Unknown libcurl option {0:s}'.format(k))
            else:
                raise ValidationError('Error: {0:s}'.format(msg))
        except TypeError as e:
            raise ValidationError('TypeError: {0:s} -  {1:s}'.format(k, str(e)))


def S3UPLOAD__CLASSNAME_validator(form, field):
    class_names = (
        'boto3_s3',
        'libcloud_s3',
    )

    if field.data not in class_names:
        raise ValidationError('Invalid selection')


def S3UPLOAD__ACCESS_KEY_validator(form, field):
    if not field.data:
        return

    s3accesskey_regex = r'^[a-zA-Z0-9]+$'

    if not re.search(s3accesskey_regex, field.data):
        raise ValidationError('Invalid access key')


def S3UPLOAD__SECRET_KEY_validator(form, field):
    if not field.data:
        return

    s3secretkey_regex = r'^[a-zA-Z0-9\/\+]+$'

    if not re.search(s3secretkey_regex, field.data):
        raise ValidationError('Invalid secret key')


def S3UPLOAD__HOST_validator(form, field):
    host_regex = r'^[a-zA-Z0-9_\.\-]+$'  # include _ for docker

    if not re.search(host_regex, field.data):
        raise ValidationError('Invalid host name')


def S3UPLOAD__PORT_validator(form, field):
    if not isinstance(field.data, int):
        raise ValidationError('Please enter valid number')

    if field.data < 0:
        raise ValidationError('Port must be 0 or greater')

    if field.data > 65535:
        raise ValidationError('Port must be less than 65535')


def S3UPLOAD__REGION_validator(form, field):
    region_regex = r'^[a-zA-Z0-9\-]+$'

    if not re.search(region_regex, field.data):
        raise ValidationError('Invalid region name')


def S3UPLOAD__BUCKET_validator(form, field):
    bucket_regex = r'^[a-zA-Z0-9\.\-]+$'

    if not re.search(bucket_regex, field.data):
        raise ValidationError('Invalid bucket name')


def S3UPLOAD__URL_TEMPLATE_validator(form, field):
    urlt_regex = r'^[a-zA-Z0-9\.\-\:\/\{\}]+$'

    if not re.search(urlt_regex, field.data):
        raise ValidationError('Invalid URL template')


    slash_regex = r'\/$'

    if re.search(slash_regex, field.data):
        raise ValidationError('URL Template cannot end with a slash')


    test_data = {
        'host'   : 'foobar',
        'bucket' : 'foobar',
        'region' : 'foobar',
    }

    try:
        field.data.format(**test_data)
    except KeyError as e:
        raise ValidationError('KeyError: {0:s}'.format(str(e)))
    except ValueError as e:
        raise ValidationError('ValueError: {0:s}'.format(str(e)))


def S3UPLOAD__ACL_validator(form, field):
    acl_regex = r'^[a-zA-Z0-9\-]+$'

    if not re.search(acl_regex, field.data):
        raise ValidationError('Invalid ACL name')


def S3UPLOAD__STORAGE_CLASS_validator(form, field):
    if not field.data:
        return

    class_regex = r'^[a-zA-Z0-9\-]+$'

    if not re.search(class_regex, field.data):
        raise ValidationError('Invalid storage class syntax')


def MQTTPUBLISH__BASE_TOPIC_validator(form, field):
    topic_regex = r'^[a-zA-Z0-9_\-\/]+$'

    if not re.search(topic_regex, field.data):
        raise ValidationError('Invalid characters in base topic')

    if re.search(r'^\/', field.data):
        raise ValidationError('Base topic cannot begin with slash')

    if re.search(r'\/$', field.data):
        raise ValidationError('Base topic cannot end with slash')


def MQTTPUBLISH__QOS_validator(form, field):
    if not isinstance(field.data, int):
        raise ValidationError('Please enter valid number')

    if field.data not in (0, 1, 2):
        raise ValidationError('Invalid QoS')


def SYNCAPI__BASEURL_validator(form, field):
    url_regex = r'^[a-zA-Z0-9\-\/\.\:\\]+$'

    if not re.search(url_regex, field.data):
        raise ValidationError('Invalid characters in URL')

    if not re.search(r'^https?\:\/\/', field.data):
        raise ValidationError('URL should begin with https://')

    if re.search(r'\/$', field.data):
        raise ValidationError('URL cannot end with slash')

    if re.search(r'localhost', field.data):
        raise ValidationError('Do not sync to localhost, bad things happen')

    if re.search(r'127\.0\.0\.1', field.data):
        raise ValidationError('Do not sync to localhost, bad things happen')

    if re.search(r'\:\:1', field.data):
        raise ValidationError('Do not sync to localhost, bad things happen')


def FITSHEADER_KEY_validator(form, field):
    header_regex = r'^[a-zA-Z0-9\-]+$'

    if not re.search(header_regex, field.data):
        raise ValidationError('Invalid characters in header')

    if len(field.data) > 8:
        raise ValidationError('Header must be 8 characters or less')


def LIBCAMERA__IMAGE_FILE_TYPE_validator(form, field):
    if field.data not in ('dng', 'jpg', 'png'):
        raise ValidationError('Please select a valid file type')


def LIBCAMERA__AWB_validator(form, field):
    if field.data not in list(zip(*form.LIBCAMERA__AWB_choices))[0]:
        raise ValidationError('Please select a valid AWB')


def LIBCAMERA__EXTRA_OPTIONS_validator(form, field):
    if not field.data:
        return

    options_regex = r'^[a-zA-Z0-9_\.\-\:\/\ ]+$'
    if not re.search(options_regex, field.data):
        raise ValidationError('Invalid characters')


def INDI_CONFIG_DEFAULTS_validator(form, field):
    try:
        json_data = json.loads(field.data)
    except json.decoder.JSONDecodeError as e:
        raise ValidationError(str(e))


    for k in json_data.keys():
        if k.startswith('#'):
            # comment
            continue

        if k not in ('PROPERTIES', 'TEXT', 'SWITCHES'):
            raise ValidationError('Only PROPERTIES, TEXT, and SWITCHES attributes allowed')


    for k, v in json_data.get('PROPERTIES', {}).items():
        if not isinstance(v, dict):
            raise ValidationError('Number property {0:s} value must be a dict'.format(k))

        for k2 in v.keys():
            if k2.startswith('#'):
                # comment
                continue

    for k, v in json_data.get('TEXT', {}).items():
        if not isinstance(v, dict):
            raise ValidationError('Text property {0:s} value must be a dict'.format(k))

        for k2 in v.keys():
            if k2.startswith('#'):
                # comment
                continue

    for k, v in json_data.get('SWITCHES', {}).items():
        if not isinstance(v, dict):
            raise ValidationError('Switch {0:s} value must be a dict'.format(k))

        for k2 in v.keys():
            if k2.startswith('#'):
                # comment
                continue

            if k2 not in ('on', 'off'):
                raise ValidationError('Invalid switch configuration {0:s}'.format(k2))

            if not isinstance(v[k2], list):
                raise ValidationError('Switch {0:s} "{1:s}" value must be a list'.format(k, k2))

            #if k2 == 'on':
            #    if len(v[k2]) == 0:
            #        raise ValidationError('Switch {0:s} "on" value have at least one item'.format(k))


        #if 'on' not in v.keys():
        #    raise ValidationError('Switch {0:s} requires at least one "on" key'.format(k))


class IndiAllskyConfigForm(FlaskForm):
    CAMERA_INTERFACE_choices = (
        ('indi', 'INDI'),
        ('indi_passive', 'INDI (Passive)'),
        ('libcamera_imx477', 'libcamera IMX477'),
        ('libcamera_imx378', 'libcamera IMX378'),
        ('libcamera_ov5647', 'libcamera OV5647'),
        ('libcamera_imx219', 'libcamera IMX219'),
        ('libcamera_imx519', 'libcamera IMX519'),
        ('libcamera_64mp_hawkeye', 'libcamera 64mp Hawkeye'),
        ('libcamera_imx708', 'libcamera IMX708'),
        ('libcamera_imx296_gs', 'libcamera IMX296 GS'),
        ('libcamera_imx290', 'libcamera IMX290'),
        ('libcamera_imx462', 'libcamera IMX462'),
    )

    CCD_BIT_DEPTH_choices = (
        ('0', 'Auto Detect'),
        ('8', '8'),
        ('10', '10'),
        ('12', '12'),
        ('14', '14'),
        ('16', '16'),
    )

    TEMP_DISPLAY_choices = (
        ('c', 'Celcius'),
        ('f', 'Fahrenheit'),
        ('k', 'Kelvin'),
    )

    IMAGE_FILE_TYPE_choices = (
        ('jpg', 'JPEG'),
        ('png', 'PNG'),
        #('webp', 'WebP'),  # ffmpeg support broken
        ('tif', 'TIFF'),
    )

    CFA_PATTERN_choices = (
        ('', 'Auto Detect'),
        ('RGGB', 'RGGB'),
        ('GRBG', 'GRBG'),
        ('BGGR', 'BGGR'),
        ('GBRG', 'GBRG'),
    )

    SCNR_ALGORITHM_choices = (
        ('', 'Disabled'),
        ('average_neutral', 'Average Neutral'),
        ('maximum_neutral', 'Maximum Neutral'),
    )

    IMAGE_EXPORT_RAW_choices = (
        ('', 'Disabled'),
        ('png', 'PNG'),
        ('tif', 'TIFF'),
        ('jp2', 'JPEG 2000'),
        ('webp', 'WEBP'),
        ('jpg', 'JPEG'),
    )

    ADU_FOV_DIV_choices = (
        ('2', '100%'),
        ('3', '66%'),
        ('4', '50%'),
        ('6', '33%'),
    )

    SQM_FOV_DIV_choices = (
        ('2', '100%'),
        ('3', '66%'),
        ('4', '50%'),
        ('6', '33%'),
    )

    IMAGE_STACK_METHOD_choices = (
        ('maximum', 'Maximum'),
        ('average', 'Average'),
        ('minimum', 'Minimum'),
    )

    IMAGE_STACK_COUNT_choices = (
        ('1', 'Disabled'),
        ('2', '2'),
        ('3', '3'),
        ('4', '4'),
        ('5', '5'),
    )

    IMAGE_ROTATE_choices = (
        ('', 'Disabled'),
        ('ROTATE_90_CLOCKWISE', '90° Clockwise'),
        ('ROTATE_90_COUNTERCLOCKWISE', '90° Counterclockwise'),
        ('ROTATE_180', '180°'),
    )

    FFMPEG_VFSCALE_choices = (
        ('', 'None'),
        ('-1:2304', 'V 2304px (imx477)'),
        ('-1:1520', 'V 1520px (imx477)'),
        ('-1:760', 'V 760px (imx477)'),
        ('iw*.75:ih*.75', '75%'),
        ('iw*.5:ih*.5', '50%'),
        ('iw*.25:ih*.25', '25%'),
    )

    FFMPEG_CODEC_choices = (
        ('libx264', 'x264'),
        ('libvpx', 'webm')
    )

    ORB_PROPERTIES__MODE_choices = (
        ('ha', 'Local Hour Angle'),
        ('az', 'Azimuth'),
        ('alt', 'Altitude'),
        ('off', 'Off'),
    )

    IMAGE_LABEL_SYSTEM_choices = (
        ('', 'Off'),
        ('opencv', 'OpenCV'),
        ('pillow', 'Pillow'),
    )

    TEXT_PROPERTIES__FONT_FACE_choices = (
        ('FONT_HERSHEY_SIMPLEX', 'Sans-Serif'),
        ('FONT_HERSHEY_PLAIN', 'Sans-Serif (small)'),
        ('FONT_HERSHEY_DUPLEX', 'Sans-Serif (complex)'),
        ('FONT_HERSHEY_COMPLEX', 'Serif'),
        ('FONT_HERSHEY_TRIPLEX', 'Serif (complex)'),
        ('FONT_HERSHEY_COMPLEX_SMALL', 'Serif (small)'),
        ('FONT_HERSHEY_SCRIPT_SIMPLEX', 'Script'),
        ('FONT_HERSHEY_SCRIPT_COMPLEX', 'Script (complex)'),
    )

    TEXT_PROPERTIES__PIL_FONT_FILE_choices = (
        ('fonts-freefont-ttf/FreeSans.ttf', 'Free Sans'),
        ('fonts-freefont-ttf/FreeSansBold.ttf', 'Free Sans Bold'),
        ('fonts-freefont-ttf/FreeSansOblique.ttf', 'Free Oblique'),
        ('fonts-freefont-ttf/FreeSansBoldOblique.ttf', 'Free Bold Oblique'),
        ('fonts-freefont-ttf/FreeSerif.ttf', 'Free Serif'),
        ('fonts-freefont-ttf/FreeSerifBold.ttf', 'Free Serif Bold'),
        ('fonts-freefont-ttf/FreeSerifItalic.ttf', 'Free Serif Italic'),
        ('fonts-freefont-ttf/FreeSerifBoldItalic.ttf', 'Free Serif Bold Italic'),
        ('fonts-freefont-ttf/FreeMono.ttf', 'Free Mono'),
        ('fonts-freefont-ttf/FreeMonoBold.ttf', 'Free Mono Bold'),
        ('fonts-freefont-ttf/FreeMonoOblique.ttf', 'Free Mono Oblique'),
        ('fonts-freefont-ttf/FreeMonoBoldOblique.ttf', 'Free Mono Bold Oblique'),
        ('liberation2/LiberationMono-Regular.ttf', 'Liberation Mono'),
        ('liberation2/LiberationMono-Italic.ttf', 'Liberation Mono Italic'),
        ('liberation2/LiberationMono-Bold.ttf', 'Liberation Mono Bold'),
        ('liberation2/LiberationMono-BoldItalic.ttf', 'Liberation Mono Bold Italic'),
        ('liberation2/LiberationSans-Regular.ttf', 'Liberation Sans'),
        ('liberation2/LiberationSans-Italic.ttf', 'Liberation Sans Italic'),
        ('liberation2/LiberationSans-Bold.ttf', 'Liberation Sans Bold'),
        ('liberation2/LiberationSans-BoldItalic.ttf', 'Liberation Sans Bold Italic'),
        ('liberation2/LiberationSerif-Regular.ttf', 'Liberation Serif'),
        ('liberation2/LiberationSerif-Italic.ttf', 'Liberation Serif Italic'),
        ('liberation2/LiberationSerif-Bold.ttf', 'Liberation Serif Bold'),
        ('liberation2/LiberationSerif-BoldItalic.ttf', 'Liberation Serif Bold Italic'),
        ('hack/Hack-Regular.ttf', 'Hack Sans Mono'),
        ('hack/Hack-Italic.ttf', 'Hack Sans Mono Italic'),
        ('hack/Hack-Bold.ttf', 'Hack Sans Mono Bold'),
        ('hack/Hack-BoldItalic.ttf', 'Hack Sans Mono Bold Italic'),
        ('intel-one-mono/intelone-mono-font-family-regular.ttf', 'Intel One Mono Regular'),
        ('intel-one-mono/intelone-mono-font-family-italic.ttf', 'Intel One Mono Italic'),
        ('intel-one-mono/intelone-mono-font-family-light.ttf', 'Intel One Mono Light'),
        ('intel-one-mono/intelone-mono-font-family-lightitalic.ttf', 'Intel One Mono Light Italic'),
        ('intel-one-mono/intelone-mono-font-family-medium.ttf', 'Intel One Mono Medium'),
        ('intel-one-mono/intelone-mono-font-family-mediumitalic.ttf', 'Intel One Mono Medium Italic'),
        ('intel-one-mono/intelone-mono-font-family-bold.ttf', 'Intel One Mono Bold '),
        ('intel-one-mono/intelone-mono-font-family-bolditalic.ttf', 'Intel One Mono Bold Italic'),
        ('custom', 'Custom (below)'),
    )

    FILETRANSFER__CLASSNAME_choices = (
        ('pycurl_sftp', 'PycURL SFTP [22]'),
        ('paramiko_sftp', 'Paramiko SFTP [22]'),
        ('pycurl_ftpes', 'PycURL FTPES [21]'),
        ('pycurl_ftps', 'PycURL FTPS [990]'),
        ('pycurl_ftp', 'PycURL FTP [21] *no encryption*'),
        ('python_ftp', 'Python FTP [21] *no encryption*'),
        ('python_ftpes', 'Python FTPES [21]'),
        ('pycurl_webdav_https', 'PycURL WebDAV HTTPS [443]'),
    )

    S3UPLOAD__CLASSNAME_choices = (
        ('boto3_s3', 'Boto3 (AWS)'),
        ('libcloud_s3', 'Apache Libcloud (AWS)'),
    )

    MQTTPUBLISH__TRANSPORT_choices = (
        ('tcp', 'tcp'),
        ('websockets', 'websockets'),
    )

    LIBCAMERA__IMAGE_FILE_TYPE_choices = (
        ('dng', 'DNG (raw)'),
        ('jpg', 'JPEG'),
        ('png', 'PNG'),
    )

    LIBCAMERA__AWB_choices = (
        ('auto', 'Auto'),
        ('incandescent', 'Incandescent'),
        ('tungsten', 'Tungsten'),
        ('fluorescent', 'Fluorescent'),
        ('indoor', 'Indoor'),
        ('daylight', 'Daylight'),
        ('cloudy', 'Cloudy'),
        ('custom', 'Custom'),
    )


    ENCRYPT_PASSWORDS                = BooleanField('Encrypt Passwords')
    CAMERA_INTERFACE                 = SelectField('Camera Interface', choices=CAMERA_INTERFACE_choices, validators=[DataRequired(), CAMERA_INTERFACE_validator])
    INDI_SERVER                      = StringField('INDI Server', validators=[DataRequired(), INDI_SERVER_validator])
    INDI_PORT                        = IntegerField('INDI port', validators=[DataRequired(), INDI_PORT_validator])
    INDI_CAMERA_NAME                 = StringField('INDI Camera Name', validators=[INDI_CAMERA_NAME_validator])
    OWNER                            = StringField('Owner', validators=[OWNER_validator])
    LENS_NAME                        = StringField('Lens Name', validators=[LENS_NAME_validator])
    LENS_FOCAL_LENGTH                = FloatField('Focal Length', validators=[LENS_FOCAL_LENGTH_validator])
    LENS_FOCAL_RATIO                 = FloatField('Focal Ratio', validators=[LENS_FOCAL_RATIO_validator])
    LENS_IMAGE_CIRCLE                = IntegerField('Image Circle', validators=[LENS_IMAGE_CIRCLE_validator])
    LENS_ALTITUDE                    = FloatField('Altitude', validators=[LENS_ALTITUDE_validator])
    LENS_AZIMUTH                     = FloatField('Azimuth', validators=[LENS_AZIMUTH_validator])
    CCD_CONFIG__NIGHT__GAIN          = IntegerField('Night Gain', validators=[ccd_GAIN_validator])
    CCD_CONFIG__NIGHT__BINNING       = IntegerField('Night Bin Mode', validators=[DataRequired(), ccd_BINNING_validator])
    CCD_CONFIG__MOONMODE__GAIN       = IntegerField('Moon Mode Gain', validators=[ccd_GAIN_validator])
    CCD_CONFIG__MOONMODE__BINNING    = IntegerField('Moon Mode Bin Mode', validators=[DataRequired(), ccd_BINNING_validator])
    CCD_CONFIG__DAY__GAIN            = IntegerField('Daytime Gain', validators=[ccd_GAIN_validator])
    CCD_CONFIG__DAY__BINNING         = IntegerField('Daytime Bin Mode', validators=[DataRequired(), ccd_BINNING_validator])
    CCD_EXPOSURE_MAX                 = FloatField('Max Exposure', validators=[DataRequired(), CCD_EXPOSURE_MAX_validator])
    CCD_EXPOSURE_DEF                 = FloatField('Default Exposure', validators=[CCD_EXPOSURE_DEF_validator])
    CCD_EXPOSURE_MIN                 = FloatField('Min Exposure', validators=[CCD_EXPOSURE_MIN_validator])
    CCD_BIT_DEPTH                    = SelectField('Camera Bit Depth', choices=CCD_BIT_DEPTH_choices, validators=[CCD_BIT_DEPTH_validator])
    EXPOSURE_PERIOD                  = FloatField('Exposure Period (Night)', validators=[DataRequired(), EXPOSURE_PERIOD_validator])
    EXPOSURE_PERIOD_DAY              = FloatField('Exposure Period (Day)', validators=[DataRequired(), EXPOSURE_PERIOD_DAY_validator])
    FOCUS_MODE                       = BooleanField('Focus Mode')
    FOCUS_DELAY                      = FloatField('Focus Delay', validators=[DataRequired(), FOCUS_DELAY_validator])
    CFA_PATTERN                      = SelectField('Bayer Pattern', choices=CFA_PATTERN_choices, validators=[CFA_PATTERN_validator])
    SCNR_ALGORITHM                   = SelectField('SCNR (green reduction)', choices=SCNR_ALGORITHM_choices, validators=[SCNR_ALGORITHM_validator])
    WBR_FACTOR                       = FloatField('Red Balance Factor', validators=[WB_FACTOR_validator])
    WBG_FACTOR                       = FloatField('Green Balance Factor', validators=[WB_FACTOR_validator])
    WBB_FACTOR                       = FloatField('Blue Balance Factor', validators=[WB_FACTOR_validator])
    AUTO_WB                          = BooleanField('Auto White Balance')
    SATURATION_FACTOR                = FloatField('Saturation Factor', validators=[SATURATION_FACTOR_validator])
    CCD_COOLING                      = BooleanField('CCD Cooling')
    CCD_TEMP                         = FloatField('Target CCD Temp', validators=[CCD_TEMP_validator])
    TEMP_DISPLAY                     = SelectField('Temperature Display', choices=TEMP_DISPLAY_choices, validators=[DataRequired(), TEMP_DISPLAY_validator])
    CCD_TEMP_SCRIPT                  = StringField('External Temperature Script', validators=[CCD_TEMP_SCRIPT_validator])
    GPS_ENABLE                       = BooleanField('GPS Enable')
    GPS_TIMESYNC                     = BooleanField('GPS Time Sync')
    TARGET_ADU                       = IntegerField('Target ADU (night)', validators=[DataRequired(), TARGET_ADU_validator])
    TARGET_ADU_DAY                   = IntegerField('Target ADU (day)', validators=[DataRequired(), TARGET_ADU_DAY_validator])
    TARGET_ADU_DEV                   = IntegerField('Target ADU Deviation (night)', validators=[DataRequired(), TARGET_ADU_DEV_validator])
    TARGET_ADU_DEV_DAY               = IntegerField('Target ADU Deviation (day)', validators=[DataRequired(), TARGET_ADU_DEV_DAY_validator])
    ADU_ROI_X1                       = IntegerField('ADU ROI x1', validators=[ADU_ROI_validator])
    ADU_ROI_Y1                       = IntegerField('ADU ROI y1', validators=[ADU_ROI_validator])
    ADU_ROI_X2                       = IntegerField('ADU ROI x2', validators=[ADU_ROI_validator])
    ADU_ROI_Y2                       = IntegerField('ADU ROI y2', validators=[ADU_ROI_validator])
    ADU_FOV_DIV                      = SelectField('ADU FoV', choices=ADU_FOV_DIV_choices, validators=[ADU_FOV_DIV_validator])
    DETECT_STARS                     = BooleanField('Star Detection')
    DETECT_STARS_THOLD               = FloatField('Star Detection Threshold', validators=[DataRequired(), DETECT_STARS_THOLD_validator])
    DETECT_METEORS                   = BooleanField('Meteor Detection')
    DETECT_MASK                      = StringField('Detection Mask', validators=[DETECT_MASK_validator])
    DETECT_DRAW                      = BooleanField('Mark Detections on Image')
    LOGO_OVERLAY                     = StringField('Logo Overlay', validators=[LOGO_OVERLAY_validator])
    SQM_ROI_X1                       = IntegerField('SQM ROI x1', validators=[SQM_ROI_validator])
    SQM_ROI_Y1                       = IntegerField('SQM ROI y1', validators=[SQM_ROI_validator])
    SQM_ROI_X2                       = IntegerField('SQM ROI x2', validators=[SQM_ROI_validator])
    SQM_ROI_Y2                       = IntegerField('SQM ROI y2', validators=[SQM_ROI_validator])
    SQM_FOV_DIV                      = SelectField('SQM FoV', choices=SQM_FOV_DIV_choices, validators=[SQM_FOV_DIV_validator])
    LOCATION_NAME                    = StringField('Location', validators=[LOCATION_NAME_validator])
    LOCATION_LATITUDE                = FloatField('Latitude', validators=[LOCATION_LATITUDE_validator])
    LOCATION_LONGITUDE               = FloatField('Longitude', validators=[LOCATION_LONGITUDE_validator])
    LOCATION_ELEVATION               = IntegerField('Elevation', validators=[LOCATION_ELEVATION_validator])
    TIMELAPSE_ENABLE                 = BooleanField('Enable Timelapse Creation')
    DAYTIME_CAPTURE                  = BooleanField('Daytime Capture')
    DAYTIME_TIMELAPSE                = BooleanField('Daytime Timelapse')
    DAYTIME_CONTRAST_ENHANCE         = BooleanField('Daytime Contrast Enhance')
    NIGHT_CONTRAST_ENHANCE           = BooleanField('Night time Contrast Enhance')
    CONTRAST_ENHANCE_16BIT           = BooleanField('16-bit Contrast Enhance')
    CLAHE_CLIPLIMIT                  = FloatField('CLAHE Clip Limit', validators=[CLAHE_CLIPLIMIT_validator])
    CLAHE_GRIDSIZE                   = IntegerField('CLAHE Grid Size', validators=[CLAHE_GRIDSIZE_validator])
    NIGHT_SUN_ALT_DEG                = FloatField('Sun altitude', validators=[NIGHT_SUN_ALT_DEG_validator])
    NIGHT_MOONMODE_ALT_DEG           = FloatField('Moonmode Moon Altitude', validators=[NIGHT_MOONMODE_ALT_DEG_validator])
    NIGHT_MOONMODE_PHASE             = FloatField('Moonmode Moon Phase', validators=[NIGHT_MOONMODE_PHASE_validator])
    WEB_EXTRA_TEXT                   = StringField('Extra HTML Info File', validators=[WEB_EXTRA_TEXT_validator])
    WEB_NONLOCAL_IMAGES              = BooleanField('Non-Local Images')
    WEB_LOCAL_IMAGES_ADMIN           = BooleanField('Local Images from Admin Networks')
    IMAGE_STRETCH__MODE1_ENABLE      = BooleanField('Enable Stretching')
    IMAGE_STRETCH__MODE1_GAMMA       = FloatField('Stretching Gamma', validators=[IMAGE_STRETCH__MODE1_GAMMA_validator])
    IMAGE_STRETCH__MODE1_STDDEVS     = FloatField('Stretching Std Deviations', validators=[DataRequired(), IMAGE_STRETCH__MODE1_STDDEVS_validator])
    IMAGE_STRETCH__SPLIT             = BooleanField('Stretching split screen')
    IMAGE_STRETCH__MOONMODE          = BooleanField('Moon Mode Stretching')
    IMAGE_STRETCH__DAYTIME           = BooleanField('Daytime Stretching')
    KEOGRAM_ANGLE                    = FloatField('Keogram Rotation Angle', validators=[KEOGRAM_ANGLE_validator])
    KEOGRAM_H_SCALE                  = IntegerField('Keogram Horizontal Scaling', validators=[DataRequired(), KEOGRAM_H_SCALE_validator])
    KEOGRAM_V_SCALE                  = IntegerField('Keogram Vertical Scaling', validators=[DataRequired(), KEOGRAM_V_SCALE_validator])
    KEOGRAM_LABEL                    = BooleanField('Label Keogram')
    STARTRAILS_SUN_ALT_THOLD         = FloatField('Star Trails Max Sun Altitude', validators=[DataRequired(), STARTRAILS_SUN_ALT_THOLD_validator])
    STARTRAILS_MOONMODE_THOLD        = BooleanField('Star Trails Exclude Moon Mode')
    STARTRAILS_MOON_ALT_THOLD        = FloatField('Custom Max Moon Altitude', validators=[DataRequired(), STARTRAILS_MOON_ALT_THOLD_validator])
    STARTRAILS_MOON_PHASE_THOLD      = FloatField('Custom Max Moon Phase', validators=[DataRequired(), STARTRAILS_MOON_PHASE_THOLD_validator])
    STARTRAILS_MAX_ADU               = IntegerField('Star Trails Max ADU', validators=[DataRequired(), STARTRAILS_MAX_ADU_validator])
    STARTRAILS_MASK_THOLD            = IntegerField('Star Trails Mask Threshold', validators=[DataRequired(), STARTRAILS_MASK_THOLD_validator])
    STARTRAILS_PIXEL_THOLD           = FloatField('Star Trails Pixel Threshold', validators=[STARTRAILS_PIXEL_THOLD_validator])
    STARTRAILS_TIMELAPSE             = BooleanField('Star Trails Timelapse')
    STARTRAILS_TIMELAPSE_MINFRAMES   = IntegerField('Star Trails Timelapse Minimum Frames', validators=[DataRequired(), STARTRAILS_TIMELAPSE_MINFRAMES_validator])
    IMAGE_FILE_TYPE                  = SelectField('Image file type', choices=IMAGE_FILE_TYPE_choices, validators=[DataRequired(), IMAGE_FILE_TYPE_validator])
    IMAGE_FILE_COMPRESSION__JPG      = IntegerField('JPEG Quality', validators=[DataRequired(), IMAGE_FILE_COMPRESSION__JPG_validator])
    IMAGE_FILE_COMPRESSION__PNG      = IntegerField('PNG Compression', validators=[DataRequired(), IMAGE_FILE_COMPRESSION__PNG_validator])
    IMAGE_FILE_COMPRESSION__TIF      = StringField('TIFF Compression', render_kw={'readonly' : True, 'disabled' : 'disabled'})
    IMAGE_FOLDER                     = StringField('Image folder', validators=[DataRequired(), IMAGE_FOLDER_validator])
    IMAGE_LABEL_TEMPLATE             = TextAreaField('Label Template', validators=[DataRequired(), IMAGE_LABEL_TEMPLATE_validator])
    IMAGE_EXTRA_TEXT                 = StringField('Extra Image Text File', validators=[IMAGE_EXTRA_TEXT_validator])
    IMAGE_ROTATE                     = SelectField('Rotate Image', choices=IMAGE_ROTATE_choices, validators=[IMAGE_ROTATE_validator])
    IMAGE_ROTATE_ANGLE               = IntegerField('Rotation Angle', validators=[IMAGE_ROTATE_ANGLE_validator])
    IMAGE_FLIP_V                     = BooleanField('Flip Image Vertically')
    IMAGE_FLIP_H                     = BooleanField('Flip Image Horizontally')
    IMAGE_SCALE                      = IntegerField('Image Scaling', validators=[DataRequired(), IMAGE_SCALE_validator])
    IMAGE_CIRCLE_MASK__ENABLE        = BooleanField('Enable Image Circle Mask')
    IMAGE_CIRCLE_MASK__DIAMETER      = IntegerField('Mask Diameter', validators=[DataRequired(), IMAGE_CIRCLE_MASK__DIAMETER_validator])
    IMAGE_CIRCLE_MASK__OFFSET_X      = IntegerField('Mask X Offset', validators=[IMAGE_CIRCLE_MASK__OFFSET_X_validator])
    IMAGE_CIRCLE_MASK__OFFSET_Y      = IntegerField('Mask Y Offset', validators=[IMAGE_CIRCLE_MASK__OFFSET_Y_validator])
    IMAGE_CIRCLE_MASK__BLUR          = IntegerField('Mask Blur', validators=[IMAGE_CIRCLE_MASK__BLUR_validator])
    IMAGE_CIRCLE_MASK__OPACITY       = IntegerField('Mask Opacity %', validators=[IMAGE_CIRCLE_MASK__OPACITY_validator])
    IMAGE_CIRCLE_MASK__OUTLINE       = BooleanField('Mask Outline')
    IMAGE_CROP_ROI_X1                = IntegerField('Image Crop ROI x1', validators=[IMAGE_CROP_ROI_validator])
    IMAGE_CROP_ROI_Y1                = IntegerField('Image Crop ROI y1', validators=[IMAGE_CROP_ROI_validator])
    IMAGE_CROP_ROI_X2                = IntegerField('Image Crop ROI x2', validators=[IMAGE_CROP_ROI_validator])
    IMAGE_CROP_ROI_Y2                = IntegerField('Image Crop ROI y2', validators=[IMAGE_CROP_ROI_validator])
    IMAGE_SAVE_FITS                  = BooleanField('Save FITS data')
    NIGHT_GRAYSCALE                  = BooleanField('Save in Grayscale at Night')
    DAYTIME_GRAYSCALE                = BooleanField('Save in Grayscale during Day')
    IMAGE_EXPORT_RAW                 = SelectField('Export raw image type', choices=IMAGE_EXPORT_RAW_choices, validators=[IMAGE_EXPORT_RAW_validator])
    IMAGE_EXPORT_FOLDER              = StringField('Export folder', validators=[DataRequired(), IMAGE_EXPORT_FOLDER_validator])
    IMAGE_STACK_METHOD               = SelectField('Image stacking method', choices=IMAGE_STACK_METHOD_choices, validators=[DataRequired(), IMAGE_STACK_METHOD_validator])
    IMAGE_STACK_COUNT                = SelectField('Stack count', choices=IMAGE_STACK_COUNT_choices, validators=[DataRequired(), IMAGE_STACK_COUNT_validator])
    IMAGE_STACK_ALIGN                = BooleanField('Register images')
    IMAGE_ALIGN_DETECTSIGMA          = IntegerField('Alignment sensitivity', validators=[DataRequired(), IMAGE_ALIGN_DETECTSIGMA_validator])
    IMAGE_ALIGN_POINTS               = IntegerField('Alignment points', validators=[DataRequired(), IMAGE_ALIGN_POINTS_validator])
    IMAGE_ALIGN_SOURCEMINAREA        = IntegerField('Minimum point area', validators=[DataRequired(), IMAGE_ALIGN_SOURCEMINAREA_validator])
    IMAGE_STACK_SPLIT                = BooleanField('Stack split screen')
    IMAGE_EXPIRE_DAYS                = IntegerField('Image expiration (days)', validators=[DataRequired(), IMAGE_EXPIRE_DAYS_validator])
    TIMELAPSE_EXPIRE_DAYS            = IntegerField('Timelapse expiration (days)', validators=[DataRequired(), TIMELAPSE_EXPIRE_DAYS_validator])
    FFMPEG_FRAMERATE                 = IntegerField('FFMPEG Framerate', validators=[DataRequired(), FFMPEG_FRAMERATE_validator])
    FFMPEG_BITRATE                   = StringField('FFMPEG Bitrate', validators=[DataRequired(), FFMPEG_BITRATE_validator])
    FFMPEG_VFSCALE                   = SelectField('FFMPEG Scaling', choices=FFMPEG_VFSCALE_choices, validators=[FFMPEG_VFSCALE_validator])
    FFMPEG_CODEC                     = SelectField('FFMPEG Codec', choices=FFMPEG_CODEC_choices, validators=[FFMPEG_CODEC_validator])
    IMAGE_LABEL_SYSTEM               = SelectField('Label Images', choices=IMAGE_LABEL_SYSTEM_choices, validators=[IMAGE_LABEL_SYSTEM_validator])
    TEXT_PROPERTIES__FONT_FACE       = SelectField('OpenCV Font', choices=TEXT_PROPERTIES__FONT_FACE_choices, validators=[DataRequired(), TEXT_PROPERTIES__FONT_FACE_validator])
    #TEXT_PROPERTIES__FONT_AA
    TEXT_PROPERTIES__FONT_SCALE      = FloatField('Font Scale', validators=[DataRequired(), TEXT_PROPERTIES__FONT_SCALE_validator])
    TEXT_PROPERTIES__FONT_THICKNESS  = IntegerField('Font Thickness', validators=[DataRequired(), TEXT_PROPERTIES__FONT_THICKNESS_validator])
    TEXT_PROPERTIES__FONT_OUTLINE    = BooleanField('Font Outline')
    TEXT_PROPERTIES__FONT_HEIGHT     = IntegerField('Text Height Offset', validators=[DataRequired(), TEXT_PROPERTIES__FONT_HEIGHT_validator])
    TEXT_PROPERTIES__FONT_X          = IntegerField('Text X Offset', validators=[DataRequired(), TEXT_PROPERTIES__FONT_X_validator])
    TEXT_PROPERTIES__FONT_Y          = IntegerField('Text Y Offset', validators=[DataRequired(), TEXT_PROPERTIES__FONT_Y_validator])
    TEXT_PROPERTIES__FONT_COLOR      = StringField('Text Color (r,g,b)', validators=[DataRequired(), RGB_COLOR_validator])
    TEXT_PROPERTIES__PIL_FONT_FILE   = SelectField('Pillow Font', choices=TEXT_PROPERTIES__PIL_FONT_FILE_choices, validators=[DataRequired(), TEXT_PROPERTIES__PIL_FONT_FILE_validator])
    TEXT_PROPERTIES__PIL_FONT_CUSTOM = StringField('Custom Font', validators=[TEXT_PROPERTIES__PIL_FONT_CUSTOM_validator])
    TEXT_PROPERTIES__PIL_FONT_SIZE   = IntegerField('Font Size', validators=[DataRequired(), TEXT_PROPERTIES__PIL_FONT_SIZE_validator])
    ORB_PROPERTIES__MODE             = SelectField('Orb Mode', choices=ORB_PROPERTIES__MODE_choices, validators=[DataRequired(), ORB_PROPERTIES__MODE_validator])
    ORB_PROPERTIES__RADIUS           = IntegerField('Orb Radius', validators=[DataRequired(), ORB_PROPERTIES__RADIUS_validator])
    ORB_PROPERTIES__SUN_COLOR        = StringField('Sun Orb Color (r,g,b)', validators=[DataRequired(), RGB_COLOR_validator])
    ORB_PROPERTIES__MOON_COLOR       = StringField('Moon Orb Color (r,g,b)', validators=[DataRequired(), RGB_COLOR_validator])
    UPLOAD_WORKERS                   = IntegerField('Upload Workers', validators=[DataRequired(), UPLOAD_WORKERS_validator])
    FILETRANSFER__CLASSNAME          = SelectField('Protocol', choices=FILETRANSFER__CLASSNAME_choices, validators=[DataRequired(), FILETRANSFER__CLASSNAME_validator])
    FILETRANSFER__HOST               = StringField('Host', validators=[FILETRANSFER__HOST_validator])
    FILETRANSFER__PORT               = IntegerField('Port', validators=[FILETRANSFER__PORT_validator])
    FILETRANSFER__USERNAME           = StringField('Username', validators=[FILETRANSFER__USERNAME_validator])
    FILETRANSFER__PASSWORD           = PasswordField('Password', widget=PasswordInput(hide_value=False), validators=[FILETRANSFER__PASSWORD_validator])
    FILETRANSFER__PRIVATE_KEY        = StringField('Private Key', validators=[FILETRANSFER__PRIVATE_KEY_validator])
    FILETRANSFER__PUBLIC_KEY         = StringField('Public Key', validators=[FILETRANSFER__PUBLIC_KEY_validator])
    FILETRANSFER__TIMEOUT            = FloatField('Timeout', validators=[DataRequired(), FILETRANSFER__TIMEOUT_validator])
    FILETRANSFER__CERT_BYPASS        = BooleanField('Disable Certificate Validation')
    FILETRANSFER__LIBCURL_OPTIONS    = TextAreaField('PycURL Options', validators=[DataRequired(), FILETRANSFER__LIBCURL_OPTIONS_validator])
    FILETRANSFER__REMOTE_IMAGE_NAME  = StringField('Remote Image Name', validators=[DataRequired(), FILETRANSFER__REMOTE_IMAGE_NAME_validator])
    FILETRANSFER__REMOTE_IMAGE_FOLDER      = StringField('Remote Image Folder', validators=[DataRequired(), REMOTE_FOLDER_validator])
    FILETRANSFER__REMOTE_METADATA_NAME     = StringField('Remote Metadata Name', validators=[DataRequired(), FILETRANSFER__REMOTE_METADATA_NAME_validator])
    FILETRANSFER__REMOTE_METADATA_FOLDER   = StringField('Remote Metadata Folder', validators=[DataRequired(), REMOTE_FOLDER_validator])
    FILETRANSFER__REMOTE_VIDEO_FOLDER      = StringField('Remote Video Folder', validators=[DataRequired(), REMOTE_FOLDER_validator])
    FILETRANSFER__REMOTE_KEOGRAM_FOLDER    = StringField('Remote Keogram Folder', validators=[DataRequired(), REMOTE_FOLDER_validator])
    FILETRANSFER__REMOTE_STARTRAIL_FOLDER  = StringField('Remote Star Trails Folder', validators=[DataRequired(), REMOTE_FOLDER_validator])
    FILETRANSFER__REMOTE_STARTRAIL_VIDEO_FOLDER = StringField('Remote Star Trail Video Folder', validators=[DataRequired(), REMOTE_FOLDER_validator])
    FILETRANSFER__REMOTE_ENDOFNIGHT_FOLDER = StringField('Remote EndOfNight Folder', validators=[DataRequired(), REMOTE_FOLDER_validator])
    FILETRANSFER__UPLOAD_IMAGE       = IntegerField('Transfer images', validators=[FILETRANSFER__UPLOAD_IMAGE_validator])
    FILETRANSFER__UPLOAD_METADATA    = BooleanField('Transfer metadata')
    FILETRANSFER__UPLOAD_VIDEO       = BooleanField('Transfer videos')
    FILETRANSFER__UPLOAD_KEOGRAM     = BooleanField('Transfer keograms')
    FILETRANSFER__UPLOAD_STARTRAIL   = BooleanField('Transfer star trails')
    FILETRANSFER__UPLOAD_STARTRAIL_VIDEO = BooleanField('Transfer star trail videos')
    FILETRANSFER__UPLOAD_ENDOFNIGHT  = BooleanField('Transfer AllSky EndOfNight data')
    S3UPLOAD__CLASSNAME              = SelectField('S3 Utility', choices=S3UPLOAD__CLASSNAME_choices, validators=[DataRequired(), S3UPLOAD__CLASSNAME_validator])
    S3UPLOAD__ENABLE                 = BooleanField('Enable S3 Uploading')
    S3UPLOAD__ACCESS_KEY             = StringField('Access Key', validators=[S3UPLOAD__ACCESS_KEY_validator])
    S3UPLOAD__SECRET_KEY             = PasswordField('Secret Key', widget=PasswordInput(hide_value=False), validators=[S3UPLOAD__SECRET_KEY_validator])
    S3UPLOAD__BUCKET                 = StringField('Bucket', validators=[DataRequired(), S3UPLOAD__BUCKET_validator])
    S3UPLOAD__REGION                 = StringField('Region', validators=[DataRequired(), S3UPLOAD__REGION_validator])
    S3UPLOAD__HOST                   = StringField('Host', validators=[DataRequired(), S3UPLOAD__HOST_validator])
    S3UPLOAD__PORT                   = IntegerField('Port', validators=[S3UPLOAD__PORT_validator])
    S3UPLOAD__URL_TEMPLATE           = StringField('URL Template', validators=[DataRequired(), S3UPLOAD__URL_TEMPLATE_validator])
    S3UPLOAD__ACL                    = StringField('S3 ACL', validators=[S3UPLOAD__ACL_validator])
    S3UPLOAD__STORAGE_CLASS          = StringField('S3 Storage Class', validators=[S3UPLOAD__STORAGE_CLASS_validator])
    S3UPLOAD__TLS                    = BooleanField('Use TLS')
    S3UPLOAD__CERT_BYPASS            = BooleanField('Disable Certificate Validation')
    MQTTPUBLISH__ENABLE              = BooleanField('Enable MQTT Publishing')
    MQTTPUBLISH__TRANSPORT           = SelectField('MQTT Transport', choices=MQTTPUBLISH__TRANSPORT_choices, validators=[DataRequired(), MQTTPUBLISH__TRANSPORT_validator])
    MQTTPUBLISH__HOST                = StringField('MQTT Host', validators=[MQTTPUBLISH__HOST_validator])
    MQTTPUBLISH__PORT                = IntegerField('Port', validators=[DataRequired(), MQTTPUBLISH__PORT_validator])
    MQTTPUBLISH__USERNAME            = StringField('Username', validators=[MQTTPUBLISH__USERNAME_validator])
    MQTTPUBLISH__PASSWORD            = PasswordField('Password', widget=PasswordInput(hide_value=False), validators=[MQTTPUBLISH__PASSWORD_validator])
    MQTTPUBLISH__BASE_TOPIC          = StringField('MQTT Base Topic', validators=[DataRequired(), MQTTPUBLISH__BASE_TOPIC_validator])
    MQTTPUBLISH__QOS                 = IntegerField('MQTT QoS', validators=[MQTTPUBLISH__QOS_validator])
    MQTTPUBLISH__TLS                 = BooleanField('Use TLS')
    MQTTPUBLISH__CERT_BYPASS         = BooleanField('Disable Certificate Validation')
    SYNCAPI__ENABLE                  = BooleanField('Enable Sync API')
    SYNCAPI__BASEURL                 = StringField('URL', validators=[SYNCAPI__BASEURL_validator])
    SYNCAPI__USERNAME                = StringField('Username', validators=[SYNCAPI__USERNAME_validator])
    SYNCAPI__APIKEY                  = PasswordField('API Key', widget=PasswordInput(hide_value=False), validators=[SYNCAPI__APIKEY_validator])
    SYNCAPI__CERT_BYPASS             = BooleanField('Disable Certificate Validation')
    SYNCAPI__POST_S3                 = BooleanField('Sync after S3 Upload')
    SYNCAPI__EMPTY_FILE              = BooleanField('Sync empty file')
    SYNCAPI__UPLOAD_IMAGE            = IntegerField('Transfer images', validators=[SYNCAPI__UPLOAD_IMAGE_validator])
    SYNCAPI__UPLOAD_VIDEO            = BooleanField('Transfer videos', render_kw={'disabled' : 'disabled'})
    SYNCAPI__TIMEOUT                 = FloatField('Timeout', validators=[DataRequired(), SYNCAPI__TIMEOUT_validator])
    FITSHEADERS__0__KEY              = StringField('FITS Header 1', validators=[DataRequired(), FITSHEADER_KEY_validator])
    FITSHEADERS__0__VAL              = StringField('FITS Header 1 Value', validators=[])
    FITSHEADERS__1__KEY              = StringField('FITS Header 2', validators=[DataRequired(), FITSHEADER_KEY_validator])
    FITSHEADERS__1__VAL              = StringField('FITS Header 2 Value', validators=[])
    FITSHEADERS__2__KEY              = StringField('FITS Header 3', validators=[DataRequired(), FITSHEADER_KEY_validator])
    FITSHEADERS__2__VAL              = StringField('FITS Header 3 Value', validators=[])
    FITSHEADERS__3__KEY              = StringField('FITS Header 4', validators=[DataRequired(), FITSHEADER_KEY_validator])
    FITSHEADERS__3__VAL              = StringField('FITS Header 4 Value', validators=[])
    FITSHEADERS__4__KEY              = StringField('FITS Header 5', validators=[DataRequired(), FITSHEADER_KEY_validator])
    FITSHEADERS__4__VAL              = StringField('FITS Header 5 Value', validators=[])
    LIBCAMERA__IMAGE_FILE_TYPE       = SelectField('libcamera image type', choices=LIBCAMERA__IMAGE_FILE_TYPE_choices, validators=[DataRequired(), LIBCAMERA__IMAGE_FILE_TYPE_validator])
    LIBCAMERA__AWB                   = SelectField('Night AWB', choices=LIBCAMERA__AWB_choices, validators=[DataRequired(), LIBCAMERA__AWB_validator])
    LIBCAMERA__AWB_DAY               = SelectField('Day AWB', choices=LIBCAMERA__AWB_choices, validators=[DataRequired(), LIBCAMERA__AWB_validator])
    LIBCAMERA__AWB_ENABLE            = BooleanField('Night Enable AWB')
    LIBCAMERA__AWB_ENABLE_DAY        = BooleanField('Day Enable AWB')
    LIBCAMERA__EXTRA_OPTIONS         = StringField('Night libcamera extra options', validators=[LIBCAMERA__EXTRA_OPTIONS_validator])
    LIBCAMERA__EXTRA_OPTIONS_DAY     = StringField('Day libcamera extra options', validators=[LIBCAMERA__EXTRA_OPTIONS_validator])
    INDI_CONFIG_DEFAULTS             = TextAreaField('INDI Camera Configuration', validators=[DataRequired(), INDI_CONFIG_DEFAULTS_validator])

    RELOAD_ON_SAVE                   = BooleanField('Reload on Save')
    CONFIG_NOTE                      = StringField('Config Note')

    ADMIN_NETWORKS_FLASK             = TextAreaField('Admin Networks', render_kw={'readonly' : True, 'disabled' : 'disabled'})


    #def __init__(self, *args, **kwargs):
    #    super(IndiAllskyConfigForm, self).__init__(*args, **kwargs)


    def validate(self):
        result = super(IndiAllskyConfigForm, self).validate()

        # exposure checking
        if self.CCD_EXPOSURE_DEF.data > self.CCD_EXPOSURE_MAX.data:
            self.CCD_EXPOSURE_DEF.errors.append('Default exposure cannot be greater than max exposure')
            self.CCD_EXPOSURE_MAX.errors.append('Max exposure is less than default exposure')
            result = False

        if self.CCD_EXPOSURE_MIN.data > self.CCD_EXPOSURE_MAX.data:
            self.CCD_EXPOSURE_DEF.errors.append('Minimum exposure cannot be greater than max exposure')
            self.CCD_EXPOSURE_MAX.errors.append('Max exposure is less than minimum exposure')
            result = False


        # require custom font to be defined
        if self.TEXT_PROPERTIES__PIL_FONT_FILE.data == 'custom':
            if not self.TEXT_PROPERTIES__PIL_FONT_CUSTOM.data:
                self.TEXT_PROPERTIES__PIL_FONT_CUSTOM.errors.append('Please set a custom font')
                result = False


        # check cropping
        mod_image_crop_x = (self.IMAGE_CROP_ROI_X2.data - self.IMAGE_CROP_ROI_X1.data) % 2
        if mod_image_crop_x:
            self.IMAGE_CROP_ROI_X2.errors.append('X coordinates must be divisible by 2')
            result = False

        mod_image_crop_y = (self.IMAGE_CROP_ROI_Y2.data - self.IMAGE_CROP_ROI_Y1.data) % 2
        if mod_image_crop_y:
            self.IMAGE_CROP_ROI_Y2.errors.append('Y coordinates must be divisible by 2')
            result = False


        return result


class IndiAllskyImageViewer(FlaskForm):
    YEAR_SELECT          = SelectField('Year', choices=[], validators=[])
    MONTH_SELECT         = SelectField('Month', choices=[], validators=[])
    DAY_SELECT           = SelectField('Day', choices=[], validators=[])
    HOUR_SELECT          = SelectField('Hour', choices=[], validators=[])
    IMG_SELECT           = SelectField('Image', choices=[], validators=[])
    FILTER_DETECTIONS    = BooleanField('Detections')


    def __init__(self, *args, **kwargs):
        super(IndiAllskyImageViewer, self).__init__(*args, **kwargs)

        self.detections_count = kwargs.get('detections_count', 0)
        self.s3_prefix = kwargs.get('s3_prefix', '')
        self.camera_id = kwargs.get('camera_id')
        self.local = kwargs.get('local')


    def getYears(self):
        createDate_year = extract('year', IndiAllSkyDbImageTable.createDate).label('createDate_year')

        years_query = db.session.query(
            createDate_year,
        )\
            .join(IndiAllSkyDbImageTable.camera)\
            .filter(
                and_(
                    IndiAllSkyDbCameraTable.id == self.camera_id,
                    IndiAllSkyDbImageTable.detections >= self.detections_count,
                )
        )


        if not self.local:
            # Do not serve local assets
            years_query = years_query\
                .filter(
                    or_(
                        IndiAllSkyDbImageTable.remote_url != sa_null(),
                        IndiAllSkyDbImageTable.s3_key != sa_null(),
                    )
                )


        years_query = years_query\
            .distinct()\
            .order_by(createDate_year.desc())


        year_choices = []
        for y in years_query:
            entry = (y.createDate_year, str(y.createDate_year))
            year_choices.append(entry)


        return year_choices


    def getMonths(self, year):
        createDate_year = extract('year', IndiAllSkyDbImageTable.createDate).label('createDate_year')
        createDate_month = extract('month', IndiAllSkyDbImageTable.createDate).label('createDate_month')

        months_query = db.session.query(
            createDate_year,
            createDate_month,
        )\
            .join(IndiAllSkyDbImageTable.camera)\
            .filter(
                and_(
                    IndiAllSkyDbCameraTable.id == self.camera_id,
                    IndiAllSkyDbImageTable.detections >= self.detections_count,
                    createDate_year == year,
                )
        )\


        if not self.local:
            # Do not serve local assets
            months_query = months_query\
                .filter(
                    or_(
                        IndiAllSkyDbImageTable.remote_url != sa_null(),
                        IndiAllSkyDbImageTable.s3_key != sa_null(),
                    )
                )


        months_query = months_query\
            .distinct()\
            .order_by(createDate_month.desc())


        month_choices = []
        for m in months_query:
            month_name = datetime.strptime('{0} {1}'.format(year, m.createDate_month), '%Y %m')\
                .strftime('%B')
            entry = (m.createDate_month, month_name)
            month_choices.append(entry)


        return month_choices


    def getDays(self, year, month):
        createDate_year = extract('year', IndiAllSkyDbImageTable.createDate).label('createDate_year')
        createDate_month = extract('month', IndiAllSkyDbImageTable.createDate).label('createDate_month')
        createDate_day = extract('day', IndiAllSkyDbImageTable.createDate).label('createDate_day')

        days_query = db.session.query(
            createDate_year,
            createDate_month,
            createDate_day,
        )\
            .join(IndiAllSkyDbImageTable.camera)\
            .filter(
                and_(
                    IndiAllSkyDbCameraTable.id == self.camera_id,
                    IndiAllSkyDbImageTable.detections >= self.detections_count,
                    createDate_year == year,
                    createDate_month == month,
                )
        )


        if not self.local:
            # Do not serve local assets
            days_query = days_query\
                .filter(
                    or_(
                        IndiAllSkyDbImageTable.remote_url != sa_null(),
                        IndiAllSkyDbImageTable.s3_key != sa_null(),
                    )
                )


        days_query = days_query\
            .distinct()\
            .order_by(createDate_day.desc())


        day_choices = []
        for d in days_query:
            entry = (d.createDate_day, str(d.createDate_day))
            day_choices.append(entry)


        return day_choices


    def getHours(self, year, month, day):
        createDate_year = extract('year', IndiAllSkyDbImageTable.createDate).label('createDate_year')
        createDate_month = extract('month', IndiAllSkyDbImageTable.createDate).label('createDate_month')
        createDate_day = extract('day', IndiAllSkyDbImageTable.createDate).label('createDate_day')
        createDate_hour = extract('hour', IndiAllSkyDbImageTable.createDate).label('createDate_hour')

        hours_query = db.session.query(
            createDate_year,
            createDate_month,
            createDate_day,
            createDate_hour,
        )\
            .join(IndiAllSkyDbImageTable.camera)\
            .filter(
                and_(
                    IndiAllSkyDbCameraTable.id == self.camera_id,
                    IndiAllSkyDbImageTable.detections >= self.detections_count,
                    createDate_year == year,
                    createDate_month == month,
                    createDate_day == day,
                )
        )


        if not self.local:
            # Do not serve local assets
            hours_query = hours_query\
                .filter(
                    or_(
                        IndiAllSkyDbImageTable.remote_url != sa_null(),
                        IndiAllSkyDbImageTable.s3_key != sa_null(),
                    )
                )


        hours_query = hours_query\
            .distinct()\
            .order_by(createDate_hour.desc())


        hour_choices = []
        for h in hours_query:
            entry = (h.createDate_hour, str(h.createDate_hour))
            hour_choices.append(entry)


        return hour_choices


    def getImages(self, year, month, day, hour):
        createDate_year = extract('year', IndiAllSkyDbImageTable.createDate).label('createDate_year')
        createDate_month = extract('month', IndiAllSkyDbImageTable.createDate).label('createDate_month')
        createDate_day = extract('day', IndiAllSkyDbImageTable.createDate).label('createDate_day')
        createDate_hour = extract('hour', IndiAllSkyDbImageTable.createDate).label('createDate_hour')

        images_query = IndiAllSkyDbImageTable.query\
            .join(IndiAllSkyDbImageTable.camera)\
            .filter(
                and_(
                    IndiAllSkyDbCameraTable.id == self.camera_id,
                    IndiAllSkyDbImageTable.detections >= self.detections_count,
                    createDate_year == year,
                    createDate_month == month,
                    createDate_day == day,
                    createDate_hour == hour,
                )
            )


        if not self.local:
            # Do not serve local assets
            images_query = images_query\
                .filter(
                    or_(
                        IndiAllSkyDbImageTable.remote_url != sa_null(),
                        IndiAllSkyDbImageTable.s3_key != sa_null(),
                    )
                )


        images_query = images_query\
            .order_by(IndiAllSkyDbImageTable.createDate.desc())


        images_data = list()
        for img in images_query:
            try:
                url = img.getUrl(s3_prefix=self.s3_prefix, local=self.local)
            except ValueError as e:
                app.logger.error('Error determining relative file name: %s', str(e))
                continue

            if img.detections:
                entry_str = '{0:s} [*]'.format(img.createDate.strftime('%H:%M:%S'))
            else:
                entry_str = img.createDate.strftime('%H:%M:%S')

            image_dict = dict()
            image_dict['url'] = str(url)
            image_dict['date'] = entry_str
            image_dict['ts'] = int(img.createDate.timestamp())
            image_dict['width'] = img.width
            image_dict['height'] = img.height
            image_dict['exclude'] = img.exclude


            # look for fits
            try:
                fits_image = IndiAllSkyDbFitsImageTable.query\
                    .filter(IndiAllSkyDbFitsImageTable.createDate == img.createDate)\
                    .one()

                image_dict['fits'] = str(fits_image.getUrl(s3_prefix=self.s3_prefix))
            except NoResultFound:
                image_dict['fits'] = None


            # look for raw exports
            try:
                fits_image = IndiAllSkyDbRawImageTable.query\
                    .filter(IndiAllSkyDbRawImageTable.createDate == img.createDate)\
                    .one()

                image_dict['raw'] = str(fits_image.getUrl(s3_prefix=self.s3_prefix))
            except NoResultFound:
                image_dict['raw'] = None
            except ValueError:
                # this can happen when RAW files are exported outside of the document root
                image_dict['raw'] = None

            images_data.append(image_dict)


        return images_data


class IndiAllskyImageViewerPreload(IndiAllskyImageViewer):
    def __init__(self, *args, **kwargs):
        super(IndiAllskyImageViewerPreload, self).__init__(*args, **kwargs)

        last_image = IndiAllSkyDbImageTable.query\
            .join(IndiAllSkyDbImageTable.camera)\
            .filter(
                and_(
                    IndiAllSkyDbCameraTable.id == self.camera_id,
                    IndiAllSkyDbImageTable.detections >= self.detections_count,
                )
            )\
            .order_by(IndiAllSkyDbImageTable.createDate.desc())\
            .first()

        if not last_image:
            app.logger.warning('No images found in DB')

            self.YEAR_SELECT.choices = (('', 'None'),)
            self.MONTH_SELECT.choices = (('', 'None'),)
            self.DAY_SELECT.choices = (('', 'None'),)
            self.HOUR_SELECT.choices = (('', 'None'),)
            self.IMG_SELECT.choices = (('', 'None'),)

            return


        dates_start = time.time()

        self.YEAR_SELECT.choices = self.getYears()
        self.MONTH_SELECT.choices = (('', 'Loading'),)
        self.DAY_SELECT.choices = (('', 'Loading'),)
        self.HOUR_SELECT.choices = (('', 'Loading'),)
        self.IMG_SELECT.choices = (('', 'Loading'),)

        dates_elapsed_s = time.time() - dates_start
        app.logger.info('Dates processed in %0.4f s', dates_elapsed_s)



class IndiAllskyVideoViewer(FlaskForm):
    TIMEOFDAY_SELECT_choices = (
        ('all', 'All'),
        ('day', 'Day'),
        ('night', 'Night'),
    )

    YEAR_SELECT          = SelectField('Year', choices=[], validators=[])
    MONTH_SELECT         = SelectField('Month', choices=[], validators=[])
    TIMEOFDAY_SELECT     = SelectField('Time of Day', choices=TIMEOFDAY_SELECT_choices, validators=[])


    def __init__(self, *args, **kwargs):
        super(IndiAllskyVideoViewer, self).__init__(*args, **kwargs)

        self.s3_prefix = kwargs.get('s3_prefix', '')
        self.camera_id = kwargs.get('camera_id')
        self.local = kwargs.get('local')


    def getYears(self):
        dayDate_year = extract('year', IndiAllSkyDbVideoTable.dayDate).label('dayDate_year')

        years_query = db.session.query(
            dayDate_year,
        )\
            .join(IndiAllSkyDbVideoTable.camera)\
            .filter(IndiAllSkyDbCameraTable.id == self.camera_id)


        if not self.local:
            # Do not serve local assets
            years_query = years_query\
                .filter(
                    or_(
                        IndiAllSkyDbVideoTable.remote_url != sa_null(),
                        IndiAllSkyDbVideoTable.s3_key != sa_null(),
                    )
                )


        years_query = years_query\
            .distinct()\
            .order_by(dayDate_year.desc())


        year_choices = []
        for y in years_query:
            entry = (y.dayDate_year, str(y.dayDate_year))
            year_choices.append(entry)


        return year_choices


    def getMonths(self, year):
        dayDate_year = extract('year', IndiAllSkyDbVideoTable.dayDate).label('dayDate_year')
        dayDate_month = extract('month', IndiAllSkyDbVideoTable.dayDate).label('dayDate_month')

        months_query = db.session.query(
            dayDate_year,
            dayDate_month,
        )\
            .join(IndiAllSkyDbVideoTable.camera)\
            .filter(
                and_(
                    IndiAllSkyDbCameraTable.id == self.camera_id,
                    dayDate_year == year,
                )
        )


        if not self.local:
            # Do not serve local assets
            months_query = months_query\
                .filter(
                    or_(
                        IndiAllSkyDbVideoTable.remote_url != sa_null(),
                        IndiAllSkyDbVideoTable.s3_key != sa_null(),
                    )
                )


        months_query = months_query\
            .distinct()\
            .order_by(dayDate_month.desc())


        month_choices = []
        for m in months_query:
            month_name = datetime.strptime('{0} {1}'.format(year, m.dayDate_month), '%Y %m')\
                .strftime('%B')
            entry = (m.dayDate_month, month_name)
            month_choices.append(entry)


        return month_choices



    def getVideos(self, year, month, timeofday):
        dayDate_year = extract('year', IndiAllSkyDbVideoTable.dayDate).label('dayDate_year')
        dayDate_month = extract('month', IndiAllSkyDbVideoTable.dayDate).label('dayDate_month')

        videos_query = IndiAllSkyDbVideoTable.query\
            .join(IndiAllSkyDbVideoTable.camera)\
            .filter(
                and_(
                    IndiAllSkyDbCameraTable.id == self.camera_id,
                    dayDate_year == year,
                    dayDate_month == month,
                )
            )


        # add time of day filter
        if timeofday == 'day':
            videos_query = videos_query.filter(IndiAllSkyDbVideoTable.night == sa_false())
        elif timeofday == 'night':
            videos_query = videos_query.filter(IndiAllSkyDbVideoTable.night == sa_true())
        else:
            pass


        if not self.local:
            # Do not serve local assets
            videos_query = videos_query\
                .filter(
                    or_(
                        IndiAllSkyDbVideoTable.remote_url != sa_null(),
                        IndiAllSkyDbVideoTable.s3_key != sa_null(),
                    )
                )


        # set order
        videos_query = videos_query.order_by(
            IndiAllSkyDbVideoTable.dayDate.desc(),
            IndiAllSkyDbVideoTable.night.desc(),
        )


        videos_data = []
        for v in videos_query:
            try:
                url = v.getUrl(s3_prefix=self.s3_prefix, local=self.local)
            except ValueError as e:
                app.logger.error('Error determining relative file name: %s', str(e))
                continue


            if v.data:
                data = v.data
            else:
                data = {}

            entry = {
                'url'               : str(url),
                'dayDate'           : v.dayDate.strftime('%B %d, %Y'),
                'night'             : v.night,
                'max_smoke_rating'  : constants.SMOKE_RATING_MAP_STR[data.get('max_smoke_rating', constants.SMOKE_RATING_NODATA)],
                'max_kpindex'       : data.get('max_kpindex', 0.0),
                'max_ovation_max'   : data.get('max_ovation_max', 0),
                'max_moonphase'     : data.get('max_moonphase', 0),  # might be null
                'avg_stars'         : int(data.get('avg_stars', 0)),
                'avg_sqm'           : int(data.get('avg_sqm', 0)),
            }
            videos_data.append(entry)

        # cannot query the DB from inside the DB query
        for entry in videos_data:
            dayDate = datetime.strptime(entry['dayDate'], '%B %d, %Y').date()

            # Querying the oldest due to a bug where regeneated files are added with the wrong dayDate
            # fix is inbound

            ### Keogram
            keogram_entry_q = IndiAllSkyDbKeogramTable.query\
                .join(IndiAllSkyDbKeogramTable.camera)\
                .filter(
                    and_(
                        IndiAllSkyDbCameraTable.id == self.camera_id,
                        IndiAllSkyDbKeogramTable.dayDate == dayDate,
                        IndiAllSkyDbKeogramTable.night == entry['night'],
                    )
                )


            if not self.local:
                # Do not serve local assets
                keogram_entry_q = keogram_entry_q\
                    .filter(
                        or_(
                            IndiAllSkyDbKeogramTable.remote_url != sa_null(),
                            IndiAllSkyDbKeogramTable.s3_key != sa_null(),
                        )
                    )


            keogram_entry = keogram_entry_q\
                .order_by(IndiAllSkyDbKeogramTable.dayDate.asc())\
                .first()  # use the oldest (asc)


            if keogram_entry:
                try:
                    keogram_url = keogram_entry.getUrl(s3_prefix=self.s3_prefix, local=self.local)
                except ValueError as e:
                    app.logger.error('Error determining relative file name: %s', str(e))
                    keogram_url = None
            else:
                keogram_url = None


            ### Star trail
            startrail_entry_q = IndiAllSkyDbStarTrailsTable.query\
                .join(IndiAllSkyDbStarTrailsTable.camera)\
                .filter(
                    and_(
                        IndiAllSkyDbCameraTable.id == self.camera_id,
                        IndiAllSkyDbStarTrailsTable.dayDate == dayDate,
                        IndiAllSkyDbStarTrailsTable.night == entry['night'],
                    )
                )


            if not self.local:
                # Do not serve local assets
                startrail_entry_q = startrail_entry_q\
                    .filter(
                        or_(
                            IndiAllSkyDbStarTrailsTable.remote_url != sa_null(),
                            IndiAllSkyDbStarTrailsTable.s3_key != sa_null(),
                        )
                    )


            startrail_entry = startrail_entry_q\
                .order_by(IndiAllSkyDbStarTrailsTable.dayDate.asc())\
                .first()  # use the oldest (asc)


            if startrail_entry:
                try:
                    startrail_url = startrail_entry.getUrl(s3_prefix=self.s3_prefix, local=self.local)
                except ValueError as e:
                    app.logger.error('Error determining relative file name: %s', str(e))
                    startrail_url = None
            else:
                startrail_url = None


            ### Star trail timelapses
            startrail_video_entry_q = IndiAllSkyDbStarTrailsVideoTable.query\
                .join(IndiAllSkyDbStarTrailsVideoTable.camera)\
                .filter(
                    and_(
                        IndiAllSkyDbCameraTable.id == self.camera_id,
                        IndiAllSkyDbStarTrailsVideoTable.dayDate == dayDate,
                        IndiAllSkyDbStarTrailsVideoTable.night == entry['night'],
                    )
                )


            if not self.local:
                # Do not serve local assets
                startrail_video_entry_q = startrail_video_entry_q\
                    .filter(
                        or_(
                            IndiAllSkyDbStarTrailsVideoTable.remote_url != sa_null(),
                            IndiAllSkyDbStarTrailsVideoTable.s3_key != sa_null(),
                        )
                    )


            startrail_video_entry = startrail_video_entry_q\
                .order_by(IndiAllSkyDbStarTrailsVideoTable.dayDate.asc())\
                .first()  # use the oldest (asc)


            if startrail_video_entry:
                try:
                    startrail_video_url = startrail_video_entry.getUrl(s3_prefix=self.s3_prefix, local=self.local)
                except ValueError as e:
                    app.logger.error('Error determining relative file name: %s', str(e))
                    startrail_video_url = None
            else:
                startrail_video_url = None


            entry['keogram']    = str(keogram_url)
            entry['startrail']  = str(startrail_url)
            entry['startrail_timelapse']  = str(startrail_video_url)


        return videos_data



class IndiAllskyVideoViewerPreload(IndiAllskyVideoViewer):
    def __init__(self, *args, **kwargs):
        super(IndiAllskyVideoViewerPreload, self).__init__(*args, **kwargs)

        last_video = IndiAllSkyDbVideoTable.query\
            .join(IndiAllSkyDbVideoTable.camera)\
            .filter(IndiAllSkyDbCameraTable.id == self.camera_id)\
            .order_by(IndiAllSkyDbVideoTable.dayDate.desc())\
            .first()

        if not last_video:
            app.logger.warning('No timelapses found in DB')

            self.YEAR_SELECT.choices = (('', 'None'),)
            self.MONTH_SELECT.choices = (('', 'None'),)

            return


        dates_start = time.time()

        self.YEAR_SELECT.choices = self.getYears()
        self.MONTH_SELECT.choices = (('', 'Loading'),)

        dates_elapsed_s = time.time() - dates_start
        app.logger.info('Dates processed in %0.4f s', dates_elapsed_s)



#def SERVICE_HIDDEN_validator(form, field):
#    services = (
#        'indiserver.service',
#        'indi-allsky.service',
#        'gunicorn-indi-allsky.service',
#    )
#
#    if field.data not in services:
#        raise ValidationError('Invalid service')



#def COMMAND_HIDDEN_validator(form, field):
#    commands = (
#        'restart',
#        'stop',
#        'start',
#        'hup',
#    )
#
#    if field.data not in commands:
#        raise ValidationError('Invalid command')



class IndiAllskyTimelapseGeneratorForm(FlaskForm):
    ACTION_SELECT_choices = (
        ('none', '(Please select an action)'),
        ('generate_video_k_st', 'Generate All'),
        ('generate_video', 'Generate Timelapse Only'),
        ('generate_k_st', 'Generate Keogram/Star Trails'),
        ('delete_video_k_st', 'Delete Timelapse/Keogram/Star Trails'),
        ('delete_video', 'Delete Timelapse Only'),
        ('delete_k_st', 'Delete Keogram/Star Trails'),
        ('upload_endofnight', 'Upload End-of-Night Data [today only]'),
        ('delete_images', 'Delete Images for date *DANGER*'),
    )

    ACTION_SELECT      = SelectField('Action', choices=ACTION_SELECT_choices, validators=[DataRequired()])
    DAY_SELECT         = SelectField('Day', choices=[], validators=[DataRequired()])
    CONFIRM1           = BooleanField('Confirm')


    def __init__(self, *args, **kwargs):
        super(IndiAllskyTimelapseGeneratorForm, self).__init__(*args, **kwargs)

        self.camera_id = kwargs['camera_id']

        dates_start = time.time()

        self.DAY_SELECT.choices = self.getDistinctDays(self.camera_id)

        dates_elapsed_s = time.time() - dates_start
        app.logger.info('Dates processed in %0.4f s', dates_elapsed_s)


    def getDistinctDays(self, camera_id):
        dayDate_day = func.distinct(IndiAllSkyDbImageTable.dayDate).label('day')

        days_query = db.session.query(
            dayDate_day
        )\
            .join(IndiAllSkyDbImageTable.camera)\
            .filter(IndiAllSkyDbCameraTable.id == camera_id)\
            .order_by(IndiAllSkyDbImageTable.dayDate.desc())


        day_list = list()
        for entry in days_query:
            # cannot query from inside a query
            if app.config['SQLALCHEMY_DATABASE_URI'].startswith('mysql'):
                day_list.append(entry.day)
            else:
                # assume sqlite
                day_list.append(datetime.strptime(entry.day, '%Y-%m-%d').date())


        day_choices = list()
        for day_date in day_list:
            day_str = day_date.strftime('%Y-%m-%d')

            # syntastic does not like booleans in queries directly
            true = True
            false = False

            day_night_str = '{0:s} Night'.format(day_str)
            day_day_str = '{0:s} Day'.format(day_str)


            # videos
            video_entry_night = IndiAllSkyDbVideoTable.query\
                .join(IndiAllSkyDbVideoTable.camera)\
                .filter(
                    and_(
                        IndiAllSkyDbCameraTable.id == camera_id,
                        IndiAllSkyDbVideoTable.dayDate == day_date,
                        IndiAllSkyDbVideoTable.night == true,
                    )
                )\
                .first()

            if video_entry_night:
                if not video_entry_night.success:
                    day_night_str = '{0:s} [!]'.format(day_night_str)
                else:
                    day_night_str = '{0:s} [T]'.format(day_night_str)
            else:
                day_night_str = '{0:s} [ ]'.format(day_night_str)


            video_entry_day = IndiAllSkyDbVideoTable.query\
                .join(IndiAllSkyDbVideoTable.camera)\
                .filter(
                    and_(
                        IndiAllSkyDbCameraTable.id == camera_id,
                        IndiAllSkyDbVideoTable.dayDate == day_date,
                        IndiAllSkyDbVideoTable.night == false,
                    )
                )\
                .first()

            if video_entry_day:
                if not video_entry_day.success:
                    day_day_str = '{0:s} [!]'.format(day_day_str)
                else:
                    day_day_str = '{0:s} [T]'.format(day_day_str)
            else:
                day_day_str = '{0:s} [ ]'.format(day_day_str)


            # keogram
            keogram_entry_night = IndiAllSkyDbKeogramTable.query\
                .join(IndiAllSkyDbKeogramTable.camera)\
                .filter(
                    and_(
                        IndiAllSkyDbCameraTable.id == camera_id,
                        IndiAllSkyDbKeogramTable.dayDate == day_date,
                        IndiAllSkyDbKeogramTable.night == true,
                    )
                )\
                .first()

            if keogram_entry_night:
                if not keogram_entry_night.success:
                    day_night_str = '{0:s} [!]'.format(day_night_str)
                else:
                    day_night_str = '{0:s} [K]'.format(day_night_str)
            else:
                day_night_str = '{0:s} [ ]'.format(day_night_str)


            keogram_entry_day = IndiAllSkyDbKeogramTable.query\
                .join(IndiAllSkyDbKeogramTable.camera)\
                .filter(
                    and_(
                        IndiAllSkyDbCameraTable.id == camera_id,
                        IndiAllSkyDbKeogramTable.dayDate == day_date,
                        IndiAllSkyDbKeogramTable.night == false,
                    )
                )\
                .first()

            if keogram_entry_day:
                if not keogram_entry_day.success:
                    day_day_str = '{0:s} [!]'.format(day_day_str)
                else:
                    day_day_str = '{0:s} [K]'.format(day_day_str)
            else:
                day_day_str = '{0:s} [ ]'.format(day_day_str)


            # star trail
            startrail_entry_night = IndiAllSkyDbStarTrailsTable.query\
                .join(IndiAllSkyDbStarTrailsTable.camera)\
                .filter(
                    and_(
                        IndiAllSkyDbCameraTable.id == camera_id,
                        IndiAllSkyDbStarTrailsTable.dayDate == day_date,
                        IndiAllSkyDbStarTrailsTable.night == true,
                    )
                )\
                .first()

            if startrail_entry_night:
                if not startrail_entry_night.success:
                    day_night_str = '{0:s} [!]'.format(day_night_str)
                else:
                    day_night_str = '{0:s} [S]'.format(day_night_str)
            else:
                day_night_str = '{0:s} [ ]'.format(day_night_str)


            # star trail video
            startrail_video_entry_night = IndiAllSkyDbStarTrailsVideoTable.query\
                .join(IndiAllSkyDbStarTrailsVideoTable.camera)\
                .filter(
                    and_(
                        IndiAllSkyDbCameraTable.id == camera_id,
                        IndiAllSkyDbStarTrailsVideoTable.dayDate == day_date,
                        IndiAllSkyDbStarTrailsVideoTable.night == true,
                    )
                )\
                .first()

            if startrail_video_entry_night:
                if not startrail_video_entry_night.success:
                    day_night_str = '{0:s} [!]'.format(day_night_str)
                else:
                    day_night_str = '{0:s} [ST]'.format(day_night_str)
            else:
                day_night_str = '{0:s} [ ]'.format(day_night_str)


            # images
            images_night = IndiAllSkyDbImageTable.query\
                .join(IndiAllSkyDbImageTable.camera)\
                .filter(
                    and_(
                        IndiAllSkyDbCameraTable.id == camera_id,
                        IndiAllSkyDbImageTable.dayDate == day_date,
                        IndiAllSkyDbImageTable.night == true,
                    )
                )

            day_night_str = '{0:s} - {1:d} images'.format(day_night_str, images_night.count())


            images_day = IndiAllSkyDbImageTable.query\
                .join(IndiAllSkyDbImageTable.camera)\
                .filter(
                    and_(
                        IndiAllSkyDbCameraTable.id == camera_id,
                        IndiAllSkyDbImageTable.dayDate == day_date,
                        IndiAllSkyDbImageTable.night == false,
                    )
                )

            day_day_str = '{0:s} - {1:d} images'.format(day_day_str, images_day.count())


            entry_night = ('{0:s}_night'.format(day_str), day_night_str)
            day_choices.append(entry_night)

            entry_day = ('{0:s}_day'.format(day_str), day_day_str)
            day_choices.append(entry_day)

        return day_choices



class IndiAllskySystemInfoForm(FlaskForm):
    # fake form to send commands to web application

    SERVICE_HIDDEN      = HiddenField('service_hidden', validators=[DataRequired()])
    COMMAND_HIDDEN      = HiddenField('command_hidden', validators=[DataRequired()])



class IndiAllskyHistoryForm(FlaskForm):
    HISTORY_SELECT_choices = (
        ('900', '15 Minutes'),
        ('1800', '30 Minutes'),
        ('2700', '45 Minutes'),
        ('3600', '1 Hour'),
        ('7200', '2 Hours'),
        ('10800', '3 Hours'),
        ('14400', '4 Hours'),
    )

    FRAMEDELAY_SELECT_choices = (
        ('25', 'Fast'),
        ('50', 'Medium'),
        ('75', 'Slow'),
        ('150', 'Very Slow'),
    )

    HISTORY_SELECT       = SelectField('History', choices=HISTORY_SELECT_choices, default=HISTORY_SELECT_choices[0][0], validators=[])
    FRAMEDELAY_SELECT    = SelectField('Speed', choices=FRAMEDELAY_SELECT_choices, default=FRAMEDELAY_SELECT_choices[2][0], validators=[])
    ROCK_CHECKBOX        = BooleanField('Rock', default=False)



class IndiAllskySetDateTimeForm(FlaskForm):

    NEW_DATETIME = DateTimeLocalField('New Datetime', render_kw={'step' : '1'}, format='%Y-%m-%dT%H:%M:%S', validators=[DataRequired()])



class IndiAllskyFocusForm(FlaskForm):
    ZOOM_SELECT_choices = (
        (2, 'Off'),
        (5, 'Low'),
        (10, 'Medium'),
        (20, 'High'),
        (40, 'Extreme'),
        (60, 'Ridiculous'),
        (80, 'Ludicrous'),
        (100, 'Plaid'),
    )
    REFRESH_SELECT_choices = (
        (2, '2s'),
        (3, '3s'),
        (4, '4s'),
        (5, '5s'),
        (10, '10s'),
        (15, '15s'),
    )


    ZOOM_SELECT       = SelectField('Zoom', choices=ZOOM_SELECT_choices, default=ZOOM_SELECT_choices[0][0], validators=[])
    REFRESH_SELECT    = SelectField('Refresh', choices=REFRESH_SELECT_choices, default=REFRESH_SELECT_choices[3][0], validators=[])
    X_OFFSET          = IntegerField('X Offset', default=0)
    Y_OFFSET          = IntegerField('Y Offset', default=0)


class IndiAllskyLogViewerForm(FlaskForm):
    LINES_SELECT_choices = (
        (25, '25'),
        (100, '100'),
        (500, '500'),
        (1000, '1000'),
        (2000, '2000'),
        (5000, '5000'),
    )
    REFRESH_SELECT_choices = (
        (5, '5s'),
        (15, '15s'),
        (30, '30s'),
        (60, '60s'),
    )


    LINES_SELECT      = SelectField('Lines', choices=LINES_SELECT_choices, default=LINES_SELECT_choices[0][0], validators=[])
    REFRESH_SELECT    = SelectField('Refresh', choices=REFRESH_SELECT_choices, default=REFRESH_SELECT_choices[1][0], validators=[])



def LOGIN__USERNAME_validator(form, field):
    username_regex = r'^[a-zA-Z0-9\@\.\-]+$'

    if not re.search(username_regex, field.data):
        raise ValidationError('Invalid username')


class IndiAllskyLoginForm(FlaskForm):
    USERNAME          = StringField('Username', validators=[DataRequired(), LOGIN__USERNAME_validator])
    PASSWORD          = PasswordField('Password', widget=PasswordInput(hide_value=False), validators=[DataRequired(), FILETRANSFER__PASSWORD_validator])
    NEXT              = HiddenField('Next')


class IndiAllskyCameraSelectForm(FlaskForm):
    CAMERA_SELECT     = SelectField('CAMERA', validators=[])


    def __init__(self, *args, **kwargs):
        super(IndiAllskyCameraSelectForm, self).__init__(*args, **kwargs)

        self.CAMERA_SELECT.choices = self.getCameras()


    def getCameras(self):
        cameras = IndiAllSkyDbCameraTable.query\
            .filter(IndiAllSkyDbCameraTable.hidden == sa_false())\
            .order_by(IndiAllSkyDbCameraTable.id.asc())

        camera_list = list()
        for camera in cameras:
            if camera.friendlyName:
                camera_name = camera.friendlyName
            else:
                camera_name = camera.name

            camera_list.append((camera.id, camera_name))

        return camera_list




def USER__NAME_validator(form, field):
    pass


def USER__EMAIL_validator(form, field):
    email_regex = r'[^@]+@[^@]+\.[^@]+'

    if not re.search(email_regex, field.data):
        raise ValidationError('Email address is not valid')


def USER__NEW_PASSWORD_validator(form, field):
    if not field.data:
        return

    if len(field.data) < 8:
        raise ValidationError('Password must be 8 characters or more')


class IndiAllskyUserInfoForm(FlaskForm):
    USERNAME          = StringField('Username', render_kw={'readonly' : True, 'disabled' : 'disabled'})
    NAME              = StringField('Name', validators=[DataRequired(), USER__NAME_validator])
    EMAIL             = StringField('Email', render_kw={'readonly' : True, 'disabled' : 'disabled'})
    ADMIN             = BooleanField('Admin', render_kw={'disabled' : 'disabled'})
    CURRENT_PASSWORD  = PasswordField('Current Password', widget=PasswordInput(), validators=[])
    NEW_PASSWORD      = PasswordField('New Password', widget=PasswordInput(), validators=[USER__NEW_PASSWORD_validator])
    NEW_PASSWORD2     = PasswordField('', widget=PasswordInput(), validators=[])


    def validate(self, user):
        result = super(IndiAllskyUserInfoForm, self).validate()

        if self.CURRENT_PASSWORD.data:
            if not argon2.verify(self.CURRENT_PASSWORD.data, user.password):
                self.CURRENT_PASSWORD.errors.append('Current password is not valid')
                result = False


        if self.NEW_PASSWORD.data != self.NEW_PASSWORD2.data:
            self.NEW_PASSWORD2.errors.append('Passwords do not match')
            result = False


        if argon2.verify(self.NEW_PASSWORD.data, user.password):
            self.NEW_PASSWORD.errors.append('Password cannot be the same as the old password')
            result = False

        return result


class IndiAllskyImageExcludeForm(FlaskForm):
    CAMERA_ID         = HiddenField('Camera ID', validators=[DataRequired()])
    IMAGE_ID          = HiddenField('Image ID', validators=[DataRequired()])
    EXCLUDE           = BooleanField('Exclude')


    def __init__(self, *args, **kwargs):
        super(IndiAllskyImageExcludeForm, self).__init__(*args, **kwargs)

        self.CAMERA_ID.data = kwargs.get('camera_id')

