#!/usr/bin/env python3

import sys
import argparse
import time
from datetime import datetime
from datetime import timedelta
from pathlib import Path
import signal
import logging

from sqlalchemy.orm.exc import NoResultFound


sys.path.append(str(Path(__file__).parent.absolute().parent))


from indi_allsky.flask.models import IndiAllSkyDbImageTable
from indi_allsky.flask.models import IndiAllSkyDbVideoTable
from indi_allsky.flask.models import IndiAllSkyDbKeogramTable
from indi_allsky.flask.models import IndiAllSkyDbStarTrailsTable
from indi_allsky.flask.models import IndiAllSkyDbStarTrailsVideoTable
from indi_allsky.flask.models import IndiAllSkyDbFitsImageTable
from indi_allsky.flask.models import IndiAllSkyDbPanoramaImageTable
from indi_allsky.flask.models import IndiAllSkyDbPanoramaVideoTable
from indi_allsky.flask.models import IndiAllSkyDbRawImageTable

from indi_allsky.config import IndiAllSkyConfig

from indi_allsky.flask import db
from indi_allsky.flask import create_app


logger = logging.getLogger('indi_allsky')
logger.setLevel(logging.INFO)


# setup flask context for db access
app = create_app()
app.app_context().push()


LOG_FORMATTER_STREAM = logging.Formatter('[%(levelname)s]: %(message)s')

LOG_HANDLER_STREAM = logging.StreamHandler()
LOG_HANDLER_STREAM.setFormatter(LOG_FORMATTER_STREAM)

logger.handlers.clear()  # remove syslog
logger.addHandler(LOG_HANDLER_STREAM)



class ExpireImages(object):

    def __init__(self):
        try:
            self._config_obj = IndiAllSkyConfig()
            #logger.info('Loaded config id: %d', self._config_obj.config_id)
        except NoResultFound:
            logger.error('No config file found, please import a config')
            sys.exit(1)

        self.config = self._config_obj.config


        self._image_days = 30
        self._video_days = 365


        if self.config['IMAGE_FOLDER']:
            self.image_dir = Path(self.config['IMAGE_FOLDER']).absolute()
        else:
            self.image_dir = Path(__file__).parent.parent.joinpath('html', 'images').absolute()


        self._shutdown = False


    @property
    def image_days(self):
        return self._image_days

    @image_days.setter
    def image_days(self, new_image_days):
        self._image_days = int(new_image_days)


    @property
    def video_days(self):
        return self._video_days

    @video_days.setter
    def video_days(self, new_video_days):
        self._video_days = int(new_video_days)


    def sigint_handler_main(self, signum, frame):
        logger.warning('Caught INT signal, shutting down')

        # set flag for program to stop processes
        self._shutdown = True



    def main(self):
        logger.info('Cutoff for images: %d days', self.image_days)
        logger.info('Cutoff for videos: %d days', self.video_days)

        time.sleep(5)


        # Old image files need to be pruned
        cutoff_age_images = datetime.now() - timedelta(days=self.image_days)
        cutoff_age_images_date = cutoff_age_images.date()  # cutoff date based on dayDate attribute, not createDate

        old_images = IndiAllSkyDbImageTable.query\
            .filter(IndiAllSkyDbImageTable.dayDate < cutoff_age_images_date)
        old_fits_images = IndiAllSkyDbFitsImageTable.query\
            .filter(IndiAllSkyDbFitsImageTable.dayDate < cutoff_age_images_date)
        old_raw_images = IndiAllSkyDbRawImageTable.query\
            .filter(IndiAllSkyDbRawImageTable.dayDate < cutoff_age_images_date)
        old_panorama_images = IndiAllSkyDbPanoramaImageTable.query\
            .filter(IndiAllSkyDbPanoramaImageTable.dayDate < cutoff_age_images_date)


        cutoff_age_timelapse = datetime.now() - timedelta(days=self.video_days)
        cutoff_age_timelapse_date = cutoff_age_timelapse.date()  # cutoff date based on dayDate attribute, not createDate

        old_videos = IndiAllSkyDbVideoTable.query\
            .filter(IndiAllSkyDbVideoTable.dayDate < cutoff_age_timelapse_date)
        old_keograms = IndiAllSkyDbKeogramTable.query\
            .filter(IndiAllSkyDbKeogramTable.dayDate < cutoff_age_timelapse_date)
        old_startrails = IndiAllSkyDbStarTrailsTable.query\
            .filter(IndiAllSkyDbStarTrailsTable.dayDate < cutoff_age_timelapse_date)
        old_startrails_videos = IndiAllSkyDbStarTrailsVideoTable.query\
            .filter(IndiAllSkyDbStarTrailsVideoTable.dayDate < cutoff_age_timelapse_date)
        old_panorama_videos = IndiAllSkyDbPanoramaVideoTable.query\
            .filter(IndiAllSkyDbPanoramaVideoTable.dayDate < cutoff_age_timelapse_date)


        logger.warning('Found %d expired images to delete', old_images.count())
        logger.warning('Found %d expired FITS images to delete', old_fits_images.count())
        logger.warning('Found %d expired RAW images to delete', old_raw_images.count())
        logger.warning('Found %d expired Panorama images to delete', old_panorama_images.count())
        logger.warning('Found %d expired videos to delete', old_videos.count())
        logger.warning('Found %d expired keograms to delete', old_keograms.count())
        logger.warning('Found %d expired star trails to delete', old_startrails.count())
        logger.warning('Found %d expired star trail videos to delete', old_startrails_videos.count())
        logger.warning('Found %d expired panorama videos to delete', old_panorama_videos.count())
        logger.info('Proceeding in 10 seconds')

        time.sleep(10)
        logger.info('Building id lists...')


        ### Getting IDs first then deleting each file is faster than deleting all files with
        ### thumbnails with a single query.  Deleting associated thumbnails causes sqlalchemy
        ### to recache after every delete which cause a 1-5 second lag for each delete

        image_id_list = list()
        for entry in old_images:
            image_id_list.append(entry.id)

        fits_id_list = list()
        for entry in old_fits_images:
            fits_id_list.append(entry.id)

        raw_id_list = list()
        for entry in old_raw_images:
            raw_id_list.append(entry.id)

        panorama_image_id_list = list()
        for entry in old_panorama_images:
            panorama_image_id_list.append(entry.id)


        video_id_list = list()
        for entry in old_videos:
            video_id_list.append(entry.id)

        keogram_id_list = list()
        for entry in old_keograms:
            keogram_id_list.append(entry.id)

        startrail_image_id_list = list()
        for entry in old_startrails:
            startrail_image_id_list.append(entry.id)

        startrail_video_id_list = list()
        for entry in old_startrails_videos:
            startrail_video_id_list.append(entry.id)

        panorama_video_id_list = list()
        for entry in old_panorama_videos:
            panorama_video_id_list.append(entry.id)


        logger.warning('Deleting...')

        # catch signals to perform cleaner shutdown
        signal.signal(signal.SIGINT, self.sigint_handler_main)

        self._deleteAssets(IndiAllSkyDbImageTable, image_id_list)
        self._deleteAssets(IndiAllSkyDbFitsImageTable, fits_id_list)
        self._deleteAssets(IndiAllSkyDbRawImageTable, raw_id_list)
        self._deleteAssets(IndiAllSkyDbPanoramaImageTable, panorama_image_id_list)
        self._deleteAssets(IndiAllSkyDbVideoTable, video_id_list)
        self._deleteAssets(IndiAllSkyDbKeogramTable, keogram_id_list)
        self._deleteAssets(IndiAllSkyDbStarTrailsTable, startrail_image_id_list)
        self._deleteAssets(IndiAllSkyDbStarTrailsVideoTable, startrail_video_id_list)
        self._deleteAssets(IndiAllSkyDbPanoramaVideoTable, panorama_video_id_list)



        # Remove empty folders
        dir_list = list()
        self._getFolderFolders(self.image_dir, dir_list)

        empty_dirs = filter(lambda p: not any(p.iterdir()), dir_list)
        for d in empty_dirs:
            logger.info('Removing empty directory: %s', d)

            try:
                d.rmdir()
            except OSError as e:
                logger.error('Cannot remove folder: %s', str(e))
            except PermissionError as e:
                logger.error('Cannot remove folder: %s', str(e))


    def _deleteAssets(self, table, entry_id_list):
        for entry_id in entry_id_list:
            entry = table.query\
                .filter(table.id == entry_id)\
                .one()

            logger.info('Removing old %s entry: %s', entry.__class__.__name__, entry.filename)

            try:
                entry.deleteAsset()
            except OSError as e:
                logger.error('Cannot remove file: %s', str(e))
                continue

            db.session.delete(entry)
            db.session.commit()


            if self._shutdown:
                sys.exit(1)


    def _getFolderFolders(self, folder, dir_list):
        for item in Path(folder).iterdir():
            if item.is_dir():
                dir_list.append(item)
                self._getFolderFolders(item, dir_list)  # recursion



if __name__ == "__main__":
    argparser = argparse.ArgumentParser()
    argparser.add_argument(
        '--days',
        '-d',
        help='Images older than days will be deleted',
        type=int,
        default=30,
    )
    argparser.add_argument(
        '--timelapse_days',
        '-t',
        help='Videos older than days will be deleted',
        type=int,
        default=365,
    )


    args = argparser.parse_args()


    ei = ExpireImages()
    ei.image_days = args.days
    ei.video_days = args.timelapse_days

    ei.main()
