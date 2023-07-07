import webdav3.client
import os

def webdav_connect():
    try:
        webdav_login = os.environ['RDM_USER']
        webdav_password = os.environ['RDM_KEY']
    except KeyError as e:
        print(f"Could not connect to WEBDAV - missing WEBDAV_LOGIN and/or WEBDAV_PASSWORD")
        raise e

    try:
        client = webdav3.client.Client({
            'webdav_hostname': f"https://cloud.rdm.uq.edu.au/remote.php/dav/files/{webdav_login}/",
            'webdav_login':    webdav_login,
            'webdav_password': webdav_password,
            'webdav_timeout': 120
        })
    except Exception as e:
        print(f"Could not connect to WEBDAV - connection error!")
        raise e

    return client

def get_maps():
    client = webdav_connect()            
    client.download_sync(
        remote_path="QSMFUNCTOR-Q0748/qsm-challenge-and-head-phantom/head-phantom-maps.tar",
        local_path=os.path.join(tmp_dir, "head-phantom-maps.tar")
    )

if __name__ == "__main__":
    get_maps()


