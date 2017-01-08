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
    backup(options)
    clean(options)

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
        for mount in own_container.attrs['Mounts']:
            if mount['Destination'] == ('/volumes/' + data_type_details['data-location'] + '/raw').replace('//', '/'):
                raw_dir = mount['Destination']
                tmp_dump_dir = (raw_dir + '/dockplicity_backup').replace('//', '/')
                dump_volume = raw_dir[:len(raw_dir) - 4]
                dump_dir = (dump_volume + '/' + options['data_type']).replace('//', '/')
    return {
        'passphrase': os.environ['PASSPHRASE'],
        'raw_dir': raw_dir,
        'access_key': os.environ['ACCESS_KEY'],
        'secret_key': os.environ['SECRET_KEY'],
        'target_url': options['target_url'],
        'storage_backend': storage_backend,
        'bucket': bucket,
        'tmp_dump_dir': tmp_dump_dir,
        'dump_dir': dump_dir,
        'encrypt': True if os.environ['ENCRYPT'] == 'true' else False,
        'data_type': options['data_type'],
        'dump_volume': dump_volume,
        'data_type_details': data_type_details,
        'service': os.environ['SERVICE'],
        'container_id': os.environ['CONTAINER_ID'],
        'yearly': os.environ['YEARLY'],
        'monthly': os.environ['MONTHLY'],
        'mounts': mounts,
        'weekly': os.environ['WEEKLY'],
        'daily': os.environ['DAILY'],
        'hourly': os.environ['HOURLY'],
        'keep_within': os.environ['KEEP_WITHIN']
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
            setting['backup'] = setting['backup'].replace('<' + env + '>', os.environ[env] if env in os.environ else '')
        setting['backup'] = ('/bin/sh -c "' + setting['backup'] + '"').replace('%DUMP%', setting['data-location'] + '/dockplicity_backup/' + setting['backup-file']).replace('//', '/')
        return setting
    else:
        return 'raw'

def mount_storage(options):
    os.system('''
    mkdir -p /project
    echo ''' + options['access_key'] + ':' + options['secret_key'] + ''' > /project/auth.txt
    chmod 600 /project/auth.txt
    ''')
    if options['storage_backend'] == 'gs':
        os.system('''
        mkdir /borg
        s3fs ''' + options['bucket'] + ''' /borg \
        -o nomultipart \
        -o passwd_file=/project/auth.txt \
        -o sigv2 \
        -o url=https://storage.googleapis.com
        ''')

def backup(options):
    os.environ['BORG_PASSPHRASE'] = os.environ['PASSPHRASE']
    os.environ['BORG_REPO'] = '/borg'
    if options['data_type'] != 'raw':
        os.system('rm -rf ' + options['tmp_dump_dir'])
        container = client.containers.get(options['container_id'])
        os.system('mkdir -p ' + options['tmp_dump_dir'])
        response = container.exec_run(options['data_type_details']['backup'])
        print(response)
        os.system('mv ' + options['tmp_dump_dir'] + ' ' + options['dump_dir'] + '''
        chmod -R 700 ''' + options['dump_dir'] + '''
        umount ''' + options['raw_dir'] + '''
        rm -d ''' + options['raw_dir'] + '''
        ''')
    no_encrypt = ''
    if (options['encrypt'] == False):
        no_encrypt = '--encryption=none '
    if os.path.isdir('/borg') == False or os.listdir('/borg') == []:
        os.system('(echo ' + options['passphrase'] + '; echo ' + options['passphrase'] + '; echo) | borg init ' + no_encrypt + '/borg')
    for mount in options['mounts']:
        name = options['service'] + ':' + mount['Destination'].replace('/', '#') + '-{now}'
        command = '(echo y) | borg create ::' + name + ' ' + mount['Destination']
        os.system(command)

def clean(options):
    prefixes = list()
    for mount in options['mounts']:
        name = options['service'] + mount['Destination'].replace('/', '#')
        command = '(echo y) | borg prune --prefix=' + name + ' --keep-within=' + options['keep_within'] + ' --keep-hourly=' + options['hourly'] + ' --keep-daily=' + options['daily'] + ' --keep-weekly=' + options['weekly'] + ' --keep-monthly=' + options['monthly'] + ' --keep-yearly=' + options['yearly']
        os.system(command)

def get_own_container():
    ip = socket.gethostbyname(socket.gethostname())
    for container in client.containers.list():
        if (container.attrs['NetworkSettings']['Networks']['bridge']['IPAddress'] == ip):
            return container

main()
