#!/usr/bin/env python3


from datetime import datetime
from datetime import timedelta
#from datetime import timezone
import math
import ephem
import logging


logging.basicConfig(level=logging.INFO)
logger = logging



LATITUDE  = 33.0
LONGITUDE = -84.0

#LATITUDE  = 62.9
#LONGITUDE = -160.0


class DayNightStop(object):
    def main(self):


        obs = ephem.Observer()
        sun = ephem.Sun()
        obs.lat = math.radians(LATITUDE)
        obs.lon = math.radians(LONGITUDE)


        now = datetime.now()
        now = datetime.now() - timedelta(hours=12)


        utc_offset = now.astimezone().utcoffset()
        start_day = datetime.strptime(now.strftime('%Y%m%d'), '%Y%m%d')
        start_day_utc = start_day - utc_offset

        obs.date = start_day_utc
        sun.compute(obs)

        today_transit = obs.next_transit(sun).datetime()
        if now - utc_offset < today_transit:
            night_stop = today_transit
        else:
            night_stop = today_transit + timedelta(hours=12)

        obs.date = night_stop
        sun.compute(obs)
        end_night_alt = math.degrees(sun.alt)

        day_stop = night_stop + timedelta(hours=12)
        obs.date = day_stop
        sun.compute(obs)
        end_day_alt = math.degrees(sun.alt)

        logger.info('Start Day:       %s', start_day)
        logger.info('Start Day UTC:   %s', start_day_utc)
        logger.info('UTC Offset:      %s', utc_offset)
        logger.info('Today Transit:   %s', today_transit + utc_offset)
        logger.info('Night Hard Stop: %s, %0.1f', night_stop + utc_offset, end_night_alt)
        logger.info('Day Hard Stop:   %s, %0.1f', day_stop + utc_offset, end_day_alt)



if __name__ == "__main__":
    DayNightStop().main()

