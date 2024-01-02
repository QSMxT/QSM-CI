#!/usr/bin/env python

import webdav3.client
import os

def webdav_connect():
    try:
        webdav_login = os.environ['RDM_USER']
        webdav_password = os.environ['RDM_KEY']
    except KeyError as e:
        raise Exception("WEBDAV_LOGIN and/or WEBDAV_PASSWORD not found!") from e

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
        remote_path="QSMFUNCTOR-Q0748/qsm-challenge-and-head-phantom/data.tar",
        local_path=os.path.join(os.path.abspath('.'), "data.tar")
    )

if __name__ == "__main__":
    get_maps()


