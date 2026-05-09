from __future__ import annotations

import logging
import uuid
import os
from kubernetes import client
from kubernetes.client import ApiException

logger = logging.getLogger(__name__)

POD_NAME = os.getenv("POD_NAME")
POD_UID = os.getenv("POD_UID")
POD_IP = os.getenv("POD_IP")

class ADBServerService:
    def _rollback_job(self, *, name: str) -> None:
        try:
            self.delete_job(name=name, namespace=self.settings.namespace)
        except ApiException:
            logger.exception("Failed to rollback deployment")

    def _create_service_resource(self) -> client.V1Service:
        return client.V1Service(
            kind="Service",
            metadata=client.V1ObjectMeta(
                name=POD_NAME,
                owner_references=[
                    client.V1OwnerReference(
                        api_version="v1",
                        kind="Pod",
                        name=POD_NAME,
                        uid=POD_UID,
                        controller=True,
                        block_owner_deletion=True,
                    )
                ] if POD_UID else None,
            ),
            spec=client.V1ServiceSpec(
                type="NodePort",
                ports=[
                    client.V1ServicePort(
                        name="adb",
                        port=5037,
                        target_port=5037,
                        protocol="TCP",
                    ),
                ],
            ),
        )

    def _create_endpoints_resource(
        self,
        *,
        service_name: str,
        service_uid: str,
    ) -> client.V1Endpoints:
        return client.V1Endpoints(
            kind="Endpoints",
            metadata=client.V1ObjectMeta(
                name=service_name,
                owner_references=[
                    client.V1OwnerReference(
                        api_version="v1",
                        kind="Service",
                        name=service_name,
                        uid=service_uid,
                        controller=True,
                        block_owner_deletion=True
                    )
                ] if service_uid else None,
            ),
            subsets=[
                client.V1EndpointSubset(
                    addresses=[client.V1EndpointAddress(
                        ip=POD_IP,
                        # target_ref=client.V1ObjectReference(
                        #     kind="Pod",
                        #     name=pod_name,
                        #     namespace=self.settings.namespace,
                        # )
                    )],
                    ports=[client.CoreV1EndpointPort(port=5037)]
                )
            ]
        )

    def create_service(self):
        core_api = self._core_api()

        service_name = None
        service_uid = None
        service = None
        endpoints = None

        try:
            service = core_api.read_namespaced_service(POD_NAME, self.settings.namespace)
            if service is not None:
                endpoints = core_api.read_namespaced_endpoints(service.metadata.name, self.settings.namespace)
        except ApiException:
            logger.info("Service or endpoints not found, creating new service and endpoints")

        try:
            if service is None:
                service = core_api.create_namespaced_service(self.settings.namespace, body=self._create_service_resource())
                service_name = service.metadata.name if service.metadata else None
                service_uid = service.metadata.uid if service.metadata else None

            if endpoints is None:
                core_api.create_namespaced_endpoints(self.settings.namespace, body=self._create_endpoints_resource(
                    service_name=service_name,
                    service_uid=service_uid,
                ))
            return service
        except ApiException as error:
            logger.warning(
                "Failed to create ClusterIP Service, rolling back deployment: %s %s",
                error.status,
                error.reason,
            )
            if service_name:
                self._rollback_job(name=service_name)
            raise