from __future__ import annotations

import logging
import uuid

from kubernetes import client
from kubernetes.client import ApiException

from .resource import JobResource

logger = logging.getLogger(__name__)

DEVICE_JOB_NAME = "marshal-device"

class K8sJobManager(JobResource):
    @staticmethod
    def create_unique_job_name() -> str:
        return DEVICE_JOB_NAME + "-" + uuid.uuid4().hex[:12]

    def _rollback_job(self, *, name: str) -> None:
        try:
            self.delete_job(name=name, namespace=self.settings.namespace)
        except ApiException:
            logger.exception("Failed to rollback deployment")

    def create_job(self, env: dict[str, str]) -> client.V1Deployment:
        name = K8sJobManager.create_unique_job_name()
        deployment_body = self.build_deployment_resource(name=name, image=self.settings.job_image, env=env)
        apps_api = self._api()
        core_api = self._core_api()
        try:
            created = apps_api.create_namespaced_deployment(self.settings.namespace, deployment_body)
        except ApiException as error:
            print(error)
            logger.warning("Failed to create deployment: %s %s", error.status, error.reason)
            raise

        dep_uid = created.metadata.uid if created.metadata else None
        if not dep_uid:
            logger.error("Deployment created successfully but missing metadata.uid, rolling back deployment")
            self._rollback_job(name=name)
            raise RuntimeError("Deployment created response missing uid, cannot set ownerReferences for Service")

        service_resource = self.build_clusterip_service(name=name, deployment=created)
        try:
            core_api.create_namespaced_service(self.settings.namespace, service_resource)
        except ApiException as error:
            print(error)
            logger.warning(
                "Failed to create ClusterIP Service, rolling back deployment: %s %s",
                error.status,
                error.reason,
            )
            self._rollback_job(name=name)
            raise

        return created

    def read_job(self, *, name: str) -> client.V1Deployment | None:
        try:
            return self._api().read_namespaced_deployment(name, self.settings.namespace)
        except ApiException as e:
            if e.status == 404:
                return None

    def delete_job(self, *, name: str, namespace: str) -> bool:
        try:
            self._api().delete_namespaced_deployment(
                name,
                namespace,
                propagation_policy="Background",
            )
        except ApiException as e:
            if e.status == 404:
                return False