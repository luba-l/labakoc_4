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
def ensure_image(os_name):
    image = IMAGES[os_name]
    path = os.path.join(VM_DIR, image["file"])
    if not os.path.exists(path):
        print("Downloading", os_name)
        urllib.request.urlretrieve(image["url"], path)
    return path

def get_format(path):
    result = subprocess.run(
        ["qemu-img", "info", path],
        capture_output=True,
        text=True
    )
    for line in result.stdout.splitlines():
        if "file format" in line:
            return line.split(":")[1].strip()
    return "qcow2"

def create_seed(user, password):

    user_data = f"""#cloud-config
users:
- name: {user}
    sudo: ALL=(ALL) NOPASSWD:ALL
    shell: /bin/bash
    lock_passwd: false
    plain_text_passwd: '{password}'
ssh_pwauth: True
"""

    meta_data = """instance-id: iid-local01
local-hostname: vm
"""

    with open("user-data", "w") as f:
        f.write(user_data)

    with open("meta-data", "w") as f:
        f.write(meta_data)

    seed = os.path.join(VM_DIR, "seed.iso")

    subprocess.run([
        "genisoimage",
        "-output", seed,
        "-volid", "cidata",
        "-joliet",
        "-rock",
        "user-data",
        "meta-data"
    ])

    return seed

@app.post("/create_vm")
def create_vm(req: CreateRequest):
    name = f"vm_{uuid.uuid4().hex[:6]}"
    image = IMAGES[req.os]
    base_image = ensure_image(req.os)
    fmt = get_format(base_image)
    seed = create_seed(image["user"], image["password"])
disk = f"/tmp/{name}.qcow2"
disk_size = f"{req.disk_size}G"

subprocess.run([
    "qemu-img",
    "create",
    "-f", "qcow2",
    "-F", fmt,
    "-b", base_image,
    disk,
    "-o", f"size={disk_size}"
], check=True)

subprocess.Popen([

    "qemu-system-x86_64",

    "-m", str(req.ram),
    "-smp", str(req.cpu),

    "-drive", f"file={disk},format=qcow2,if=virtio",
    "-drive", f"file={seed},media=cdrom",

    "-netdev", f"user,id=net0,hostfwd=tcp::{port}-:22",
    "-device", "virtio-net-pci,netdev=net0",

    "-nographic"

])