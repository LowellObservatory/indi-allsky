from pathlib import Path
from datetime import datetime
import logging

from . import constants

from .flask import db

from .flask.models import TaskQueueState
from .flask.models import TaskQueueQueue
from .flask.models import IndiAllSkyDbTaskQueueTable

logger = logging.getLogger('indi_allsky')


class miscUpload(object):

    def __init__(
        self,
        config,
        upload_q,
    ):

        self.config = config
        self.upload_q = upload_q


    def upload_image(self, image_entry):
        ### upload images
        if not self.config.get('FILETRANSFER', {}).get('UPLOAD_IMAGE'):
            #logger.warning('Image uploading disabled')
            return


        if not image_entry:
            # image was not saved
            return


        image_remain = image_entry.id % int(self.config['FILETRANSFER']['UPLOAD_IMAGE'])
        if image_remain != 0:
            next_image = int(self.config['FILETRANSFER']['UPLOAD_IMAGE']) - image_remain
            logger.info('Next image upload in %d images (%d s)', next_image, int(self.config['EXPOSURE_PERIOD'] * next_image))
            return


        # Parameters for string formatting
        file_data_list = [
            self.config['IMAGE_FILE_TYPE'],
        ]


        file_data_dict = {
            'timestamp'    : image_entry.createDate,
            'ts'           : image_entry.createDate,  # shortcut
            'ext'          : self.config['IMAGE_FILE_TYPE'],
            'camera_uuid'  : image_entry.camera.uuid,
            'day_date'     : image_entry.dayDate,
        }


        # Replace parameters in names
        remote_dir = self.config['FILETRANSFER']['REMOTE_IMAGE_FOLDER'].format(**file_data_dict)
        remote_file = self.config['FILETRANSFER']['REMOTE_IMAGE_NAME'].format(*file_data_list, **file_data_dict)


        remote_file_p = Path(remote_dir).joinpath(remote_file)


        # tell worker to upload file
        jobdata = {
            'action'      : constants.TRANSFER_UPLOAD,
            'model'       : image_entry.__class__.__name__,
            'id'          : image_entry.id,
            'asset_type'  : constants.ASSET_IMAGE,
            'remote_file' : str(remote_file_p),
        }

        upload_task = IndiAllSkyDbTaskQueueTable(
            queue=TaskQueueQueue.UPLOAD,
            state=TaskQueueState.QUEUED,
            data=jobdata,
        )
        db.session.add(upload_task)
        db.session.commit()

        self.upload_q.put({'task_id' : upload_task.id})


    def upload_video(self, video_entry):
        ### Upload video
        if not self.config.get('FILETRANSFER', {}).get('UPLOAD_VIDEO'):
            logger.warning('Video uploading disabled')
            return


        now = datetime.now()

        # Parameters for string formatting
        file_data_dict = {
            'timestamp'    : now,
            'ts'           : now,  # shortcut
            'camera_uuid'  : video_entry.camera.uuid,
        }


        # Replace parameters in names
        remote_dir = self.config['FILETRANSFER']['REMOTE_VIDEO_FOLDER'].format(**file_data_dict)

        video_file_p = Path(video_entry.getFilesystemPath())
        remote_file_p = Path(remote_dir).joinpath(video_file_p.name)

        # tell worker to upload file
        jobdata = {
            'action'      : constants.TRANSFER_UPLOAD,
            'model'       : video_entry.__class__.__name__,
            'id'          : video_entry.id,
            'asset_type'  : constants.ASSET_TIMELAPSE,  # this is generic
            'remote_file' : str(remote_file_p),
        }

        upload_task = IndiAllSkyDbTaskQueueTable(
            queue=TaskQueueQueue.UPLOAD,
            state=TaskQueueState.QUEUED,
            data=jobdata,
        )
        db.session.add(upload_task)
        db.session.commit()

        self.upload_q.put({'task_id' : upload_task.id})


    def upload_keogram(self, keogram_entry):
        ### Upload video
        if not self.config.get('FILETRANSFER', {}).get('UPLOAD_KEOGRAM'):
            logger.warning('Keogram uploading disabled')
            return


        now = datetime.now()

        # Parameters for string formatting
        file_data_dict = {
            'timestamp'    : now,
            'ts'           : now,  # shortcut
            'camera_uuid'  : keogram_entry.camera.uuid,
        }


        # Replace parameters in names
        remote_dir = self.config['FILETRANSFER']['REMOTE_KEOGRAM_FOLDER'].format(**file_data_dict)


        keogram_file_p = Path(keogram_entry.getFilesystemPath())
        remote_file_p = Path(remote_dir).joinpath(keogram_file_p.name)


        # tell worker to upload file
        jobdata = {
            'action'      : constants.TRANSFER_UPLOAD,
            'model'       : keogram_entry.__class__.__name__,
            'id'          : keogram_entry.id,
            'remote_file' : str(remote_file_p),
        }

        upload_task = IndiAllSkyDbTaskQueueTable(
            queue=TaskQueueQueue.UPLOAD,
            state=TaskQueueState.QUEUED,
            data=jobdata,
        )
        db.session.add(upload_task)
        db.session.commit()

        self.upload_q.put({'task_id' : upload_task.id})


    def upload_startrail(self, startrail_entry):
        if not self.config.get('FILETRANSFER', {}).get('UPLOAD_STARTRAIL'):
            logger.warning('Star trail uploading disabled')
            return


        now = datetime.now()

        # Parameters for string formatting
        file_data_dict = {
            'timestamp'    : now,
            'ts'           : now,  # shortcut
            'camera_uuid'  : startrail_entry.camera.uuid,
        }


        # Replace parameters in names
        remote_dir = self.config['FILETRANSFER']['REMOTE_STARTRAIL_FOLDER'].format(**file_data_dict)


        startrail_file_p = Path(startrail_entry.getFilesystemPath())
        remote_file_p = Path(remote_dir).joinpath(startrail_file_p.name)


        # tell worker to upload file
        jobdata = {
            'action'      : constants.TRANSFER_UPLOAD,
            'model'       : startrail_entry.__class__.__name__,
            'id'          : startrail_entry.id,
            'remote_file' : str(remote_file_p),
        }

        upload_task = IndiAllSkyDbTaskQueueTable(
            queue=TaskQueueQueue.UPLOAD,
            state=TaskQueueState.QUEUED,
            data=jobdata,
        )
        db.session.add(upload_task)
        db.session.commit()

        self.upload_q.put({'task_id' : upload_task.id})


    def upload_startrailvideo(self, startrail_video_entry):
        ### Upload video
        if not self.config.get('FILETRANSFER', {}).get('UPLOAD_STARTRAIL_VIDEO'):
            logger.warning('Startrail video uploading disabled')
            return


        now = datetime.now()

        # Parameters for string formatting
        file_data_dict = {
            'timestamp'    : now,
            'ts'           : now,  # shortcut
            'camera_uuid'  : startrail_video_entry.camera.uuid,
        }


        # Replace parameters in names
        remote_dir = self.config['FILETRANSFER']['REMOTE_STARTRAIL_VIDEO_FOLDER'].format(**file_data_dict)


        startrail_video_file_p = Path(startrail_video_entry.getFilesystemPath())
        remote_file_p = Path(remote_dir).joinpath(startrail_video_file_p.name)

        # tell worker to upload file
        jobdata = {
            'action'      : constants.TRANSFER_UPLOAD,
            'model'       : startrail_video_entry.__class__.__name__,
            'id'          : startrail_video_entry.id,
            'remote_file' : str(remote_file_p),
        }

        upload_task = IndiAllSkyDbTaskQueueTable(
            queue=TaskQueueQueue.UPLOAD,
            state=TaskQueueState.QUEUED,
            data=jobdata,
        )
        db.session.add(upload_task)
        db.session.commit()

        self.upload_q.put({'task_id' : upload_task.id})



    def mqtt_publish_image(self, upload_filename, mq_data):
        if not self.config.get('MQTTPUBLISH', {}).get('ENABLE'):
            #logger.warning('MQ publishing disabled')
            return

        # publish data to mq broker
        jobdata = {
            'action'      : constants.TRANSFER_MQTT,
            'local_file'  : str(upload_filename),
            'metadata'    : mq_data,
            'asset_type'  : constants.ASSET_MISC,
        }

        mqtt_task = IndiAllSkyDbTaskQueueTable(
            queue=TaskQueueQueue.UPLOAD,
            state=TaskQueueState.QUEUED,
            data=jobdata,
        )
        db.session.add(mqtt_task)
        db.session.commit()

        self.upload_q.put({'task_id' : mqtt_task.id})


    def s3_upload_image(self, asset_entry, asset_metadata):
        if not self.config.get('S3UPLOAD', {}).get('ENABLE'):
            #logger.warning('S3 uploading disabled')
            return


        if not asset_entry:
            #logger.warning('S3 uploading disabled')
            return


        logger.info('Uploading to S3 bucket')

        # publish data to s3 bucket
        jobdata = {
            'action'      : constants.TRANSFER_S3,
            'model'       : asset_entry.__class__.__name__,
            'id'          : asset_entry.id,
            'asset_type'  : constants.ASSET_IMAGE,
            'metadata'    : asset_metadata,
        }

        s3_task = IndiAllSkyDbTaskQueueTable(
            queue=TaskQueueQueue.UPLOAD,
            state=TaskQueueState.QUEUED,
            data=jobdata,
        )
        db.session.add(s3_task)
        db.session.commit()

        self.upload_q.put({'task_id' : s3_task.id})


    def s3_upload_video(self, asset_entry, asset_metadata):
        if not self.config.get('S3UPLOAD', {}).get('ENABLE'):
            #logger.warning('S3 uploading disabled')
            return


        if not asset_entry:
            #logger.warning('S3 uploading disabled')
            return


        logger.info('Uploading to S3 bucket')

        # publish data to s3 bucket
        jobdata = {
            'action'      : constants.TRANSFER_S3,
            'model'       : asset_entry.__class__.__name__,
            'id'          : asset_entry.id,
            'asset_type'  : constants.ASSET_TIMELAPSE,  # this is generic
            'metadata'    : asset_metadata,
        }

        s3_task = IndiAllSkyDbTaskQueueTable(
            queue=TaskQueueQueue.UPLOAD,
            state=TaskQueueState.QUEUED,
            data=jobdata,
        )
        db.session.add(s3_task)
        db.session.commit()

        self.upload_q.put({'task_id' : s3_task.id})


    def s3_upload_keogram(self, *args):
        self.s3_upload_video(*args)


    def s3_upload_startrail(self, *args):
        self.s3_upload_video(*args)


    def s3_upload_startrail_video(self, *args):
        self.s3_upload_video(*args)


    def syncapi_image(self, asset_entry, asset_metadata):
        ### sync camera
        if not self.config.get('SYNCAPI', {}).get('ENABLE'):
            return


        if self.config.get('SYNCAPI', {}).get('POST_S3'):
            # file is uploaded after s3 upload
            return


        if not asset_entry:
            # image was not saved
            return


        if not self.config.get('SYNCAPI', {}).get('UPLOAD_IMAGE'):
            #logger.warning('Image syncing disabled')
            return


        image_remain = asset_entry.id % int(self.config.get('SYNCAPI', {}).get('UPLOAD_IMAGE', 1))
        if image_remain != 0:
            next_image = int(self.config.get('SYNCAPI', {}).get('UPLOAD_IMAGE', 1)) - image_remain
            logger.info('Next image sync in %d images (%d s)', next_image, int(self.config['EXPOSURE_PERIOD'] * next_image))
            return


        # tell worker to upload file
        jobdata = {
            'action'      : constants.TRANSFER_SYNC_V1,
            'model'       : asset_entry.__class__.__name__,
            'id'          : asset_entry.id,
            'asset_type'  : constants.ASSET_IMAGE,
            'metadata'    : asset_metadata,
        }

        upload_task = IndiAllSkyDbTaskQueueTable(
            queue=TaskQueueQueue.UPLOAD,
            state=TaskQueueState.QUEUED,
            data=jobdata,
        )
        db.session.add(upload_task)
        db.session.commit()

        self.upload_q.put({'task_id' : upload_task.id})


    def syncapi_video(self, asset_entry, metadata):
        ### sync camera
        if not self.config.get('SYNCAPI', {}).get('ENABLE'):
            return

        if self.config.get('SYNCAPI', {}).get('POST_S3'):
            # file is uploaded after s3 upload
            return

        if not asset_entry:
            #logger.warning('S3 uploading disabled')
            return

        # tell worker to upload file
        jobdata = {
            'action'      : constants.TRANSFER_SYNC_V1,
            'model'       : asset_entry.__class__.__name__,
            'id'          : asset_entry.id,
            'asset_type'  : constants.ASSET_TIMELAPSE,  # this is generic
            'metadata'    : metadata,
        }

        upload_task = IndiAllSkyDbTaskQueueTable(
            queue=TaskQueueQueue.UPLOAD,
            state=TaskQueueState.QUEUED,
            data=jobdata,
        )
        db.session.add(upload_task)
        db.session.commit()

        self.upload_q.put({'task_id' : upload_task.id})


    def syncapi_keogram(self, *args):
        self.syncapi_video(*args)


    def syncapi_startrail(self, *args):
        self.syncapi_video(*args)


    def syncapi_startrailvideo(self, *args):
        self.syncapi_video(*args)

