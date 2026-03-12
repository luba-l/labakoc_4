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

class CreateRequest(BaseModel):

    type: str
    os: str
    cpu: int
    ram: int | None = None
    disk_size: int | None = None

IMAGES = {

    "ubuntu": {
        "file": "ubuntu.img",
        "url": "https://cloud-images.ubuntu.com/jammy/current/jammy-server-cloudimg-amd64.img",
        "user": "ubuntu",
        "password": "ubuntu"
    },

    "debian": {
        "file": "debian.qcow2",
        "url": "https://cloud.debian.org/images/cloud/bookworm/latest/debian-12-genericcloud-amd64.qcow2",
        "user": "debian",
        "password": "debian"
    },

    "ubuntu-minimal": {
        "file": "ubuntu-minimal.img",
        "url": "https://cloud-images.ubuntu.com/minimal/releases/jammy/release/ubuntu-22.04-minimal-cloudimg-amd64.img",
        "user": "ubuntu",
        "password": "ubuntu"
    }

}