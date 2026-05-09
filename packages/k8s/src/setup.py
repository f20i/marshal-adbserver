from kubernetes import client

from logging import getLogger

logger = getLogger(__name__)

class K8sSetup:
    def prepare(self) -> None:
        logger.debug("Preparing Kubernetes setup")
        self.prepare_namespace()

    def prepare_namespace(self) -> None:
        ns = client.V1Namespace(
            metadata=client.V1ObjectMeta(name=self.settings.namespace)
        )
        
        try:
            self._core_api().create_namespace(body=ns)
        except client.exceptions.ApiException as e:
            if e.status == 409: logger.debug(f"Namespace '{self.settings.namespace}' already exists")
            else: raise
