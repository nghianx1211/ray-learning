#!/usr/bin/env python3
"""
Health check endpoint for Ray Serve on Kubernetes.
This provides a simple HTTP endpoint for K8s liveness/readiness probes.
"""
from fastapi import FastAPI
from ray import serve
import logging

logger = logging.getLogger(__name__)

health_app = FastAPI()


@health_app.get("/-/healthz")
@health_app.get("/-/health")
async def health_check():
    """Health check endpoint for K8s probes."""
    return {"status": "healthy", "service": "ray-serve"}


@health_app.get("/-/ready")
async def readiness_check():
    """Readiness check endpoint."""
    return {"status": "ready", "service": "ray-serve"}


@serve.deployment(
    name="health-check",
    route_prefix="/-",
    num_replicas=1,
    ray_actor_options={"num_cpus": 0.1},
)
@serve.ingress(health_app)
class HealthCheck:
    """
    Health check deployment for Kubernetes probes.
    This is a lightweight deployment that doesn't use GPU.
    """

    def __init__(self):
        logger.info("Health check deployment initialized")


def deploy_health_check():
    """Deploy the health check endpoint."""
    serve.run(HealthCheck.bind(), name="health-check", route_prefix="/-")
    logger.info("Health check endpoint deployed at /-/healthz")
