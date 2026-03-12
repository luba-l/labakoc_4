import os
import subprocess
import uuid
import socket
import urllib.request

from fastapi import FastAPI
from pydantic import BaseModel
import docker

app = FastAPI()
docker_client = docker.from_env()

INSTANCES = {}

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
VM_DIR = os.path.join(BASE_DIR, "vm_images")

os.makedirs(VM_DIR, exist_ok=True)
