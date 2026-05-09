import os
import logging
from typing import Callable
from sqlalchemy.orm import Session
from sqlalchemy import or_
import adbutils
from kubernetes import client
from marshal_adbserver_k8s import K8sManager
from marshal_database import Device, with_deleted_filter
from datetime import datetime

logger = logging.getLogger("adbserver")

RTMP_ENDPOINT = os.getenv("RTMP_ENDPOINT")
POD_NAME = os.getenv("POD_NAME")
POD_UID = os.getenv("POD_UID")
POD_IP = os.getenv("POD_IP")
ADB_SERVER_HOST = os.getenv("ADB_SERVER_HOST")

def register(session_factory: Callable[[], Session], k8s_manager: K8sManager, *, adb_service: client.V1Service = None) -> None:
    session = session_factory()
    node_port = adb_service.spec.ports[0].node_port if adb_service else None

    try:
        adb = adbutils.AdbClient(host="127.0.0.1", port=5037)
        devices = []
        conditions = []

        for info in adb.list(extended=True):
            logger.info(f"info: {info}")
            devices.append(
                {
                    "serial": info.serial,
                    "state": info.state,
                }
            )
            conditions.append(Device.serial == info.serial)
    
        existing_devices = (
            with_deleted_filter(
                session.query(Device).filter(or_(*conditions)),
                Device,
                include_deleted=True,
            ).all()
        )

        existing_devices_hash_table = dict()
        for device in existing_devices:
            existing_devices_hash_table.setdefault(device.serial, device)

        incoming_by_serial = {item["serial"]: item for item in devices}

        adb_server_host = POD_IP

        # Insert devices that are present in adb.list but not in DB.
        for serial, payload in incoming_by_serial.items():
            state = payload.get("state")
            deployament_env = {
                "ADB_SERVER_HOST": adb_server_host,
                "ADB_SERVER_PORT": f"{5037}",
                "ADB_SERVER_SOCKET": f"tcp:{adb_server_host}:{5037}",
                "DEVICE_SERIAL": serial,
                "RTMP_ENDPOINT": f"{RTMP_ENDPOINT}/{serial}",
                "RESOLUTION": "540x960",
            }
            meta = {
                "pod_name": POD_NAME,
                "pod_ip": POD_IP,
                "pod_uid": POD_UID,
                "adb_server_host": adb_server_host,
                "adb_server_port": 5037,
                "adb_server_public_port": node_port,
                "namespace": k8s_manager.settings.namespace,
            }
            existing_device = existing_devices_hash_table.get(serial)
            if existing_device is not None:
                device = existing_device
                if state == "device" and device.deleted_at is not None:
                    k8s_manager.delete_job(name=device.meta.get("job_id", ""), namespace=k8s_manager.settings.namespace)
                    deployment = k8s_manager.create_job(env=deployament_env)
                    device.meta = { **meta, "job_id": deployment.metadata.name }
                    if device.status == "offline":
                        device.status = "waiting"
                    device.updated_at = datetime.now()
                    device.deleted_at = None
                else:
                    k8s_manager.delete_job(name=device.meta.get("job_id", ""), namespace=k8s_manager.settings.namespace)
                    device.status = "offline"
                    device.meta = {}
                    device.updated_at = datetime.now()
                    device.deleted_at = datetime.now()
            else:
                if state == "device":
                    deployment = k8s_manager.create_job(env=deployament_env)
                    new_device = Device(name=serial, serial=serial, status="waiting", meta={ **meta, "job_id": deployment.metadata.name })
                    session.add(new_device)

        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()