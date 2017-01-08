import socket
import time
import os
import yaml
import glob
import re
import docker
client = docker.DockerClient(base_url='unix://var/run/docker.sock')

def main():
    options = get_options()
    mount_storage(options)
    restore(options)

def get_options():
    options = {
        'data_type': os.environ['DATA_TYPE'],
        'target_url': os.environ['TARGET_URL']
    }
    storage_backend = False
    bucket = ''
    if options['target_url'] != '':
        storage_backend = options['target_url'][:options['target_url'].index(':')]
        bucket = options['target_url'][options['target_url'].index(':') + 3:]
    data_type_details = ''
    raw_dir = ''
    tmp_dump_dir = ''
    dump_volume = ''
    dump_dir = ''
    mounts = list()
    own_container = get_own_container()
    for mount in own_container.attrs['Mounts']:
        if mount['Destination'] != '/var/run/docker.sock' and mount['Destination'] != '/volumes' and mount['Destination'] != '/borg':
            mounts.append(mount)
    if options['data_type'] != 'raw':
        data_type_details = get_data_type_details(options['data_type'])
        own_container = get_own_container()
        for mount in own_container.attrs['Mounts']:
            if options['data_type'] != 'raw' and mount['Destination'] == ('/volumes/' + data_type_details['data-location'] + '/raw').replace('//', '/'):
                raw_dir = mount['Destination']
                tmp_dump_dir = (raw_dir + '/dockplicity_backup').replace('//', '/')
                dump_volume = raw_dir[:len(raw_dir) - 4]
                dump_dir = (dump_volume + '/' + options['data_type']).replace('//', '/')
    return {
        'passphrase': os.environ['PASSPHRASE'] if 'PASSPHRASE' in os.environ else 'hellodocker',
        'google_application_credentials': os.environ['GOOGLE_APPLICATION_CREDENTIALS'],
        'service': os.environ['SERVICE'],
        'access_key': os.environ['ACCESS_KEY'],
        'secret_key': os.environ['SECRET_KEY'],
        'target_url': options['target_url'],
        'storage_backend': storage_backend,
        'bucket': bucket,
        'raw_dir': raw_dir,
        'tmp_dump_dir': tmp_dump_dir,
        'dump_dir': dump_dir,
        'data_type': options['data_type'],
        'dump_volume': dump_volume,
        'time': os.environ['TIME'],
        'data_type_details': data_type_details,
        'mounts': mounts,
        'container_id': os.environ['CONTAINER_ID'] if 'CONTAINER_ID' in os.environ else ''
    }

def get_data_type_details(data_type):
    if data_type != 'raw':
        files = ""
        for file in glob.glob("/scripts/config/*.yml"):
            files += open(file, 'r').read()
        settings = yaml.load(files)
        setting = settings[data_type]
        envs = re.findall('(?<=\<)[A-Z\d\-\_]+(?=\>)', setting['restore'])
        for env in envs:
            setting['restore'] = setting['restore'].replace('<' + env + '>', os.environ[env] if env in os.environ else '')
        setting['restore'] = ('/bin/sh -c "' + setting['restore'] + '"').replace('%DUMP%', setting['data-location'] + '/dockplicity_backup/' + setting['backup-file']).replace('//', '/')
        return setting
    else:
        return 'raw'

def mount_storage(options):
    os.system('''
    mkdir -p /project
    echo ''' + options['access_key'] + ':' + options['secret_key'] + ''' > /project/auth.txt
    chmod 600 /project/auth.txt
    mkdir /borg
    ''')
    if options['storage_backend'] == 'gs':
        os.system('s3fs ' + options['bucket'] + ''' /borg \
        -o nomultipart \
        -o passwd_file=/project/auth.txt \
        -o sigv2 \
        -o url=https://storage.googleapis.com
        ''')

def restore(options):
    restore_volume = ''
    restore_dir = '/volumes'
    if (options['restore_volume']):
        file_to_restore = options['restore_volume']
        if file_to_restore[0] == '/':
            file_to_restore = file_to_restore[1:]
        restore_volume = '--file-to-restore ' + file_to_restore + ' '
        restore_dir = (options['restore_dir'] + '/' + options['restore_volume']).replace('//', '/')
    no_encrypt = ''
    if (options['encrypt'] == False):
        no_encrypt = '--encryption=none '
    for mount in options['mounts']:
        name = options['service'] + ':' + mount['Destination'].replace('/', '#') + options['time']
        command = '(echo y) | borg extract ::' + name
        os.system(command)
    if options['data_type'] != 'raw':
        os.system('rm -rf ' + options['tmp_dump_dir'])
        container = client.containers.get(options['container_id'])
        os.system('mv ' + options['dump_dir'] + ' ' + options['tmp_dump_dir'])
        response = container.exec_run(options['data_type_details']['restore'])
        print(response)
        os.system('rm -rf ' + options['tmp_dump_dir'])

def get_own_container():
    ip = socket.gethostbyname(socket.gethostname())
    for container in client.containers.list():
        if (container.attrs['NetworkSettings']['Networks']['bridge']['IPAddress'] == ip):
            return container

main()
