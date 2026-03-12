import streamlit as st
import requests

API = "http://127.0.0.1:8000"

st.title("Сервис для аренды Виртуальных машин и контейнеров")

st.header("Создание")

instance_type = st.selectbox(
    "Тип",
    ["vm", "container"]
)
if instance_type == "vm":

    os_name = st.selectbox(
        "ОС",
        ["ubuntu", "debian", "ubuntu-minimal"]
    )

    cpu = st.slider("CPU", 1, 4, 1)

    ram = st.slider("RAM (MB)", 256, 4096, 1024)

    disk = st.slider("Размер диска (GB)", 5, 100, 20)

    if st.button("Создать ВМ"):

        data = {
            "type": "vm",
            "os": os_name,
            "cpu": cpu,
            "ram": ram,
            "disk_size": disk
        }

        r = requests.post(API + "/create_vm", json=data)

        st.success("ВМ создана")
        st.json(r.json())

else:

    os_name = st.selectbox(
        "Docker образ",
        ["ubuntu", "debian"]
    )

    cpu = st.slider("CPU", 1, 4, 1)

    if st.button("Создать контейнер"):

        data = {
            "type": "container",
            "os": os_name,
            "cpu": cpu
        }

        r = requests.post(API + "/create_container", json=data)

        st.success("Контейнер создан")
        st.json(r.json())

st.header("Запущенные ВМ/контейнеры")

try:

    r = requests.get(API + "/instances")

    instances = r.json()

    if len(instances) == 0:
        st.write("ВМ/контейнеров нет")

    for name, info in instances.items():
        st.subheader(name)
        st.write("Тип:", info["type"])
        if info["type"] == "vm":
            st.code(
                f"ssh {info['user']}@localhost -p {info['port']}"
            )

            st.write("Логин:", info["user"])
            st.write("Пароль:", info["password"])
            st.write("RAM:", info["ram"], "MB")
            st.write("Disk:", info["disk_size"], "GB")

        if info["type"] == "container":

            st.code(
                f"docker exec -it {name} bash"
            )

        if st.button("Удалить", key=name):
            requests.delete(API + f"/delete/{name}")
            st.warning("ВМ/контейнер удалён")
            st.rerun()
        st.write("---")

except:

    st.error("Backend не запущен")
