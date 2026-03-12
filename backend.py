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

class CreateRequest(BaseModel):

    type: str
    os: str
    cpu: int
    ram: int | None = None
    disk_size: int | None = None

@app.post("/create_container")
def create_container(req: CreateRequest):

    name = f"cont_{uuid.uuid4().hex[:6]}"

    container = docker_client.containers.run(
        req.os,
        name=name,
        detach=True,
        tty=True,
        stdin_open=True,
        nano_cpus=req.cpu * 1_000_000_000,
        command="/bin/bash"
    )

    INSTANCES[name] = {
        "type": "container",
        "id": container.id

    }

    return {
        "name": name,
        "connect": f"docker exec -it {name} bash"

    }

def wait_ssh(host, port):
    for _ in range(40):
        try:
            s = socket.create_connection((host, port), timeout=2)
            s.close()
            return True
        except:
            pass
    return False

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

    s = socket.socket()
    s.bind(('', 0))
    port = s.getsockname()[1]
    s.close()

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

    wait_ssh("127.0.0.1", port)

    INSTANCES[name] = {

        "type": "vm",
        "disk": disk,
        "port": port,
        "user": image["user"],
        "password": image["password"],
        "ram": req.ram,
        "disk_size": req.disk_size

    }

    return {

        "name": name,
        "ssh": f"ssh {image['user']}@localhost -p {port}",
        "password": image["password"]

    }

@app.get("/instances")
def list_instances():
    return INSTANCES


@app.delete("/delete/{name}")
def delete_instance(name: str):
    if name not in INSTANCES:
        return {"error": "not found"}
    inst = INSTANCES[name]

    if inst["type"] == "container":
        try:
            cont = docker_client.containers.get(name)
            cont.stop()
            cont.remove()
        except:
            pass

    if inst["type"] == "vm":
        subprocess.run(["pkill", "-f", inst["disk"]])
        if os.path.exists(inst["disk"]):
            os.remove(inst["disk"])

    del INSTANCES[name]

    return {"status": "deleted"}
