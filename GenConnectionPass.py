# Возможно потребуется установить pip install paramiko scp, на linux - pip3 install paramiko scp

import platform
import subprocess
from paramiko import SSHClient, AutoAddPolicy
from scp import SCPClient
from contextlib import contextmanager


# Берем ip адрес из списка и пробуем пинговать, если пинг идет, то записываем в файл file_ipaddr_avail, если нет, то в file_ipaddr_unavail (с дописыванием на следующую строку)
@contextmanager
def ping(ipaddr):
    global ip_ping_status
    if platform.system().lower() == 'windows':
        command = ['ping', '-n', str(1), '-w', str(1000), ipaddr]
        result = subprocess.run(command, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, creationflags=0x08000000)
        if b'TTL=' in result.stdout:
            ip_ping_status = 1
            print("Хост доступен:", ipaddr)
            # with open(file_ipaddr_avail, 'w') as f:
            #     f.write(ipaddr)
        else:
            print("\033[31m{}".format("Хост недоступен:"), "\033[0m{}".format(ipaddr))
            with open(file_ipaddr_unavail, 'a') as f:
                f.write(ipaddr + '\n')
            ip_ping_status = 0
        return result.returncode == 0 and b'TTL=' in result.stdout
    else:
        command = ['ping', '-c', str(1), '-w', str(1000), ipaddr]
        try:
            subprocess.check_output(["ping", "-c", "1", ipaddr])
            print("Хост доступен:", ipaddr)
            ip_ping_status = 1
        except subprocess.CalledProcessError:
            print("\033[31m{}".format("Хост недоступен:"), "\033[0m{}".format(ipaddr))
            with open(file_ipaddr_unavail, 'a') as f:
                f.write(ipaddr + '\n')
            ip_ping_status = 0
        

# Функция подключения к хостам через ssh
@contextmanager
def ssh_connection(ipaddr, sshpass, cmd_line):
    global ssh_result
    #print(ipaddr, sshpass)
    ssh = SSHClient()
    ssh.set_missing_host_key_policy(AutoAddPolicy())
    try:
        ssh.connect(hostname=ipaddr, username=user, password=sshpass, port=port, timeout=5)
        ssh_stdin, ssh_stdout, ssh_stderr = ssh.exec_command(cmd_line)
        ssh_result = ssh_stdout.read()
    except Exception:
        ssh_result = 0
    #print(ssh_result)
    ssh.close()

# Копирование файла по scp
@contextmanager
def scp_connection(file_rsa, rem_path):
    ssh = SSHClient()
    ssh.load_system_host_keys()
    ssh.set_missing_host_key_policy(AutoAddPolicy())
    ssh.connect(hostname=ipaddr, username=user, password=sshpass, port=port, timeout=5)
    scp = SCPClient(ssh.get_transport())
    scp.put(file_rsa, recursive=True, remote_path=rem_path)
    ssh.close()

# Определение операционной системы
@contextmanager
def detect_os(ssh_result):
    global system_os
    global device
    print('Пароль подошел')
    if b'Linux 3.9.11 armv7l\n' in ssh_result:
        system_os = 'OpenWRT'
        device = 'MPSB'
    elif b'Linux 3.14.16 armv7l\n' in ssh_result:
        system_os = 'OpenWRT'
        device = 'TMSB'
    elif b'Linux 2.6.39.2iRZ armv4tl\n' in ssh_result:
        system_os = 'OpenWRT'
        device = 'IRZ'
    else:
        system_os = False
        print('Система отлична от OpenWRT')
        with open(file_no_access, 'a') as f:
            f.write(ipaddr + '\n')
        device =''
    if device != '':
        with open(file_ipaddr_avail, 'a') as f:
            f.write(ipaddr +  ';' + user + ';' + sshpass + ';' + device + ';' + system_os +'\n')

# Переменные
file_ipaddr = 'ipaddresses.csv'
file_ipaddr_avail = 'ip_avail.csv'
file_ipaddr_unavail = 'ip_unavail.csv'
file_no_access = 'no_access.csv'
user = 'root'
file_secret = 'ssh_pass.txt'
port = '22'
file_rsa = 'id_rsa.pub'
rem_path = '/tmp'
device = ''
system_os = False
ssh_result = 0

# Подключаемся к файлам со списком ip адресов устройств и паролей и считываем его построчно
inv_ip = open(file_ipaddr, 'rt')
list_sshpass = open(file_secret, 'rt')


# Подключаемся по ssh к устойствам, которые доступны по пингу

for ipaddr in inv_ip:
    ipaddr = ipaddr.translate({ord(i): None for i in '\n'})
    ping(ipaddr)
    if ip_ping_status == 1:
        for sshpass in list_sshpass:
            sshpass = sshpass.translate({ord(i): None for i in '\n'})
            try:
                cmd_line = "uname -srm"
                ssh_connection(ipaddr, sshpass, cmd_line)
                if ssh_result != 0:
                    detect_os(ssh_result)
                    list_sshpass = open(file_secret, 'rt')
                    break
            except Exception:
                ssh_result = 0

    if ssh_result != 0 and system_os != False and ip_ping_status == 1:
        try:
            scp_connection(file_rsa, rem_path)
            cmd_line = 'cd /etc/dropbear/ && ls && cat /tmp/id_*.pub >> authorized_keys && chmod 0600 authorized_keys'
            ssh_connection(ipaddr, sshpass, cmd_line)
            print('RSA ключ записан и установлен')
        except Exception:
            if ip_ping_status == 1:
                print('Ключ не установлен')
    else:
        if ip_ping_status == 1 and system_os != False or ssh_result == 0:
            with open(file_no_access, 'a') as f:
                    f.write(ipaddr + '\n')
            print("Пароли не подходят или устройство недоступно по ssh.")
            list_sshpass = open(file_secret, 'rt')
