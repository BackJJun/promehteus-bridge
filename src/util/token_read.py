import datetime
import pytz
from loguru import logger


def print_exp_from_payload(payload):
    exp_timestamp = payload.get("exp")
    if exp_timestamp:
        utc_time = datetime.datetime.utcfromtimestamp(exp_timestamp).replace(tzinfo=pytz.utc)
        kst_time = utc_time.astimezone(pytz.timezone('Asia/Seoul'))
        logger.info(f"토큰 만료 시간(KST): {kst_time}")

        now_kst = datetime.datetime.now(pytz.timezone('Asia/Seoul'))
        remaining_time = kst_time - now_kst
        remaining_hours = remaining_time.total_seconds() / 3600
        logger.info(f"남은 시간: {remaining_hours:.2f}시간")

    logger.info(f"payload={payload}")
