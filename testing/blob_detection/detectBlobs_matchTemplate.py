#!/usr/bin/env python3

import argparse
import time
import logging
#import math
import tempfile
import shutil
from pathlib import Path
#from pprint import pformat
import cv2
import numpy


logging.basicConfig(level=logging.INFO)
logger = logging


class DetectBlob(object):

    _detectionThreshold = 0.55
    _distanceThreshold = 10

    def __init__(self):
        self.x_offset = 0
        self.y_offset = 0

        # start with a black image
        template = numpy.zeros([15, 15], dtype=numpy.uint8)

        # draw a white circle
        cv2.circle(
            img=template,
            center=(7, 7),
            radius=3,
            color=(255, 255, 255),
            thickness=cv2.FILLED,
        )

        # blur circle to simulate a star
        self.star_template = cv2.blur(
            src=template,
            ksize=(2, 2),
        )

        self.star_template_w, self.star_template_h = self.star_template.shape[::-1]

        #cv2.imwrite('star.jpg', self.star_template, [cv2.IMWRITE_JPEG_QUALITY, 90])


    def detectObjects(self, image_file):
        logger.info('Opening image')
        original_data = cv2.imread(str(image_file), cv2.IMREAD_UNCHANGED)

        image_height, image_width = original_data.shape[:2]

        logger.warning('Using central ROI for blob calculations')
        x1 = int((image_width / 2) - (image_width / 4))
        y1 = int((image_height / 2) - (image_height / 4))
        x2 = int((image_width / 2) + (image_width / 4))
        y2 = int((image_height / 2) + (image_height / 4))

        self.x_offset = x1
        self.y_offset = y1

        roi_data = original_data[
            y1:y2,
            x1:x2,
        ]


        if len(original_data.shape) == 2:
            # gray scale or bayered
            sep_data = roi_data
        else:
            # assume color
            logger.info('Extract luminance')
            #sep_data = cv2.cvtColor(original_data, cv2.COLOR_BGR2GRAY)
            lab = cv2.cvtColor(roi_data, cv2.COLOR_BGR2LAB)
            l, a, b = cv2.split(lab)
            sep_data = l.copy()

        #sep_data = cv2.equalizeHist(sep_data)

        sep_start = time.time()

        result = cv2.matchTemplate(sep_data, self.star_template, cv2.TM_CCOEFF_NORMED)
        result_filter = numpy.where(result >= self._detectionThreshold)

        sep_elapsed_s = time.time() - sep_start
        sep_dedup_start = time.time()

        blobs = list()
        for pt in zip(*result_filter[::-1]):
            for blob in blobs:
                #d = math.sqrt(((pt[0] - blob[0]) ** 2) + ((pt[1] - blob[1]) ** 2))
                if (abs(pt[0] - blob[0]) < self._distanceThreshold) and (abs(pt[1] - blob[1]) < self._distanceThreshold):
                    break

            else:
                # if none of the points are under the distance threshold, then add it
                blobs.append(pt)


        sep_dedup_elapsed_s = time.time() - sep_dedup_start
        total_elapsed_s = time.time() - sep_start

        logger.info('SEP processing in %0.4f s', sep_elapsed_s)
        logger.info('Deduplication in %0.4f s', sep_dedup_elapsed_s)
        logger.info('Total in %0.4f s', total_elapsed_s)


        logger.info('Found %d objects', len(blobs))

        self.drawCircles(original_data, blobs, (x1, y1, x2, y2))

        return blobs


    def drawCircles(self, original_data, blob_list, box):
        sep_data = original_data.copy()

        logger.info('Draw box around ROI')
        cv2.rectangle(
            img=sep_data,
            pt1=(box[0], box[1]),
            pt2=(box[2], box[3]),
            color=(128, 128, 128),
            thickness=1,
        )

        logger.info('Draw circles around objects')
        for blob in blob_list:
            x, y = blob

            center = (
                int(x + (self.star_template_w / 2)) + self.x_offset + 1,
                int(y + (self.star_template_h / 2)) + self.y_offset + 1,
            )

            cv2.circle(
                img=sep_data,
                center=center,
                radius=6,
                color=(0, 0, 255),
                #thickness=cv2.FILLED,
                thickness=1,
            )


        f_tmpfile = tempfile.NamedTemporaryFile(mode='w+b', delete=False, suffix='.jpg')
        f_tmpfile.close()

        tmpfile_name = Path(f_tmpfile.name)
        tmpfile_name.unlink()  # remove tempfile, will be reused below


        cv2.imwrite(str(tmpfile_name), sep_data, [cv2.IMWRITE_JPEG_QUALITY, 90])

        sep_file = Path('blobs_matchTemplate.jpg')

        shutil.copy2(f_tmpfile.name, str(sep_file))  # copy file in place
        sep_file.chmod(0o644)

        tmpfile_name.unlink()  # cleanup



if __name__ == "__main__":
    argparser = argparse.ArgumentParser()
    argparser.add_argument(
        'image',
        help='Image',
        type=str,
    )
    args = argparser.parse_args()

    db = DetectBlob()
    db.detectObjects(args.image)

