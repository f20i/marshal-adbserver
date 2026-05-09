from __future__ import annotations

import os
from kubernetes import client

POD_NAME = os.getenv("POD_NAME")
POD_UID = os.getenv("POD_UID")

class JobResource:
    @staticmethod
    def managed_by_label() -> dict[str, str]:
        return {
            "managed-by": "marshal-adbserver",
        }

    @staticmethod
    def device_labels(name: str) -> dict[str, str]:
        return {
            **JobResource.managed_by_label(),
            "device": name,
        }

    def build_clusterip_service(self, *, name: str, deployment: client.V1Deployment) -> client.V1Service:
        uid = deployment.metadata.uid if deployment.metadata else None
        return client.V1Service(
            api_version="v1",
            kind="Service",
            metadata=client.V1ObjectMeta(
                name=name,
                labels=JobResource.managed_by_label(),
                owner_references=[
                    client.V1OwnerReference(
                        api_version="apps/v1",
                        kind="Deployment",
                        name=name,
                        uid=uid,
                        controller=True,
                        block_owner_deletion=True,
                    )
                ]
                if uid
                else None,
            ),
            spec=client.V1ServiceSpec(
                type="ClusterIP",
                selector=JobResource.device_labels(name),
                ports=[
                    client.V1ServicePort(
                        name="http",
                        port=8000,
                        target_port=8000,
                        protocol="TCP",
                        # node_port=31009,
                    ),
                    client.V1ServicePort(
                        name="vnc",
                        port=6080,
                        target_port=6080,
                        protocol="TCP",
                        # node_port=31010,
                    ),
                ],
            ),
        )

    def build_deployment_resource(self, *, name: str, image: str, env: dict[str, str]) -> client.V1Deployment:
        return client.V1Deployment(
            api_version="apps/v1",
            kind="Deployment",
            metadata=client.V1ObjectMeta(
                name=name,
                labels=JobResource.device_labels(name),
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
            spec=client.V1DeploymentSpec(
                selector=client.V1LabelSelector(match_labels=JobResource.device_labels(name)),
                template=client.V1PodTemplateSpec(
                    metadata=client.V1ObjectMeta(labels=JobResource.device_labels(name)),
                    spec=client.V1PodSpec(
                        containers=[
                            client.V1Container(
                                env=[client.V1EnvVar(name=key, value=value) for key, value in env.items()],
                                name=name,
                                image=image,
                                image_pull_policy="IfNotPresent",
                                ports=[
                                    client.V1ContainerPort(name="http", container_port=8000, protocol="TCP"),
                                    client.V1ContainerPort(name="vnc", container_port=6080, protocol="TCP"),
                                ],
                                security_context=client.V1SecurityContext(
                                    capabilities=client.V1Capabilities(add=["SYS_NICE"]),
                                ),
                            )
                        ],
                    ),
                ),
            ),
        )
