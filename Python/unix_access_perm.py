#!/usr/local/bin python3.6

try:
    import sys
    import re
    import pyodbc
    from doCommand import do_command
except ImportError:
    print(f"{sys.exc_info()}")

def get_unix_permissions(unix_username, unix_user_id):
    vserver_fqdn = ""
    group_id = ""
    netapp_array = input("Input NetApp array IP: ")
    share_location = input("Input share location: ")
    operator_username = input("Input your username (ex. corp\XX#####)): ")
    operator_password = input("Input your password: ")
    parse_share = share_location.split('\\')
    vserver = parse_share[2]
    cifs_share_name = parse_share[3]
    show_vserver = do_command("vserver show",my_url=netapp_array,my_user=operator_username,my_pass=operator_password,protocol="ssh")
    for line in show_vserver:
        if f"{vserver}." in line:
            vserver_fqdn = line.split(" ")[0]
    cifs_share_show = f"cifs share show -vserver {vserver_fqdn} -share-name {cifs_share_name} -fields vserver,share-name,path,volume"
    get_share_path = do_command(cifs_share_show,my_url=netapp_array,my_user=operator_username,my_pass=operator_password,protocol="ssh")
    for line in get_share_path:
        if cifs_share_name in line:
            share_path = re.split("\s*", line)[2]
    file_dir_location = share_location.replace(f"{vserver}\{cifs_share_name}",f"{share_path}").replace("\\","/").replace("//","")
    file_dir_show = f"file-dir show -vserver {vserver_fqdn} -path {file_dir_location} -fields vserver,path,group-id,security-style"
    file_dir_cmd = do_command(file_dir_show,my_url=netapp_array,my_user=operator_username,my_pass=operator_password,protocol="ssh")
    for line in file_dir_cmd:
        if file_dir_location in line:
            if "unix" in line:
                group_id = re.split("\s*", line)[3]
            else:
                print (f"Not a unix share")
    unix_group_show = f"unix-group show -vserver {vserver_fqdn} -id {group_id}"
    get_unix_group_name = do_command(unix_group_show,my_url=netapp_array,my_user=operator_username,my_pass=operator_password,protocol="ssh")
    for line in get_unix_group_name:
        if group_id in line:
                group_name = re.split("\s*", line)[1]
    unix_group_show_membership = f"unix-group show -vserver {vserver_fqdn} -name {group_name} -mem"
    get_group_membership = do_command(unix_group_show_membership,my_url=netapp_array,my_user=operator_username,my_pass=operator_password,protocol="ssh")
    for line in get_group_membership:
        if "Users:" in line:
            if unix_username not in line:
                name_mapping_show = f"name-mapping show -vserver {vserver_fqdn} -direction win-unix -replacement {unix_username}"
                get_name_mapping = do_command(name_mapping_show,my_url=netapp_array,my_user=operator_username,my_pass=operator_password,protocol="ssh")
                print (f"{get_name_mapping}")
            else:
                print (f"User already has permissions")

# dont add to group of below
# 0
# 1
# anything 10 or less
# 65535
# 65534

def modify_unix_permissions_table():
    user_given_name = input("Input user given name: ")
    unix_username = ""
    unix_user_id = ""
    conn = pyodbc.connect(r'Driver={Microsoft Access Driver (*.mdb, *.accdb)};DBQ=\\dept01nas\Dept\SSC\unix\x8400\Unix_UID.accdb;')
    cursor = conn.cursor()
    cursor.execute(f"SELECT * FROM master WHERE UID < 6000 AND User IN ('{user_given_name}')")
    for row in cursor.fetchall():
        if user_given_name in row:
            unix_username = row[0]
            unix_user_id = row[2]
            print(f"{unix_username} {unix_user_id}")
        else:
            print(f"User not found")
            
    conn.close()
    return unix_username, unix_user_id

# copy of access db for test

# def set_unix_permissions(my_url, my_user, my_pass):
#     """
#         # \\\\dept01nas\\Dept\\SSC\\unix\\x8400\\Unix_UID.accdb

#         # TODO: 
#         # identify if user in unix table
#         # if user not in unix table, add user
#         # if user in table, get unix id
#         # create name mapping
#         # create user
#         # add user to group
#         # validate user added
#     """
#     name_mapping_create = f"name-mapping create -vserver {vserver_fqdn} -direction win-unix -position {unix_user_id} -pattern CORP\\{unix_username} -replacement {unix_username}"
#     set_name_mapping = do_command(name_mapping_create,my_url,protocol="ssh")
#     unix_user_create = f"unix-user create -vserver {vserver_fqdn} -user {unix_username} -id {unix_user_id} -primary-gid {unix_user_id} -full-name "{user_given_name}""
#     set_unix_user = do_command(unix_user_create,my_url,protocol="ssh")
#     unix_group_show_membership = f"unix-group show -vserver {vserver_fqdn} -name {group_name} -mem"
#     get_group_membership = do_command(unix_group_show_membership,my_url,protocol="ssh")

# logging.basicConfig(
#     format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.WARNING
# )
# logger = logging.getLogger(__name__)


if __name__ == "__main__":
    unix_username, unix_user_id = modify_unix_permissions_table()
    get_unix_permissions(unix_username, unix_user_id)
