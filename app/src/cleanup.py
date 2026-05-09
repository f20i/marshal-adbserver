import os
import uuid
from datetime import datetime
from typing import Callable

from sqlalchemy.orm import Session

from marshal_database import Device, with_deleted_filter

POD_IP = os.getenv("POD_IP")

def cleanup(session_factory: Callable[[], Session]) -> None:
    session = session_factory()
    try:
        devices = (
            with_deleted_filter(
                session.query(Device).filter(Device.meta.contains({"pod_ip": POD_IP})),
                Device,
                include_deleted=False,
            ).all()
        )

        for device in devices:
            device.meta = {}
            device.status = "offline"
            device.updated_at = datetime.now()
            device.deleted_at = datetime.now()

        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
