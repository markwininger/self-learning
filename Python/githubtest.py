#!/usr/local/bin/python3.5
# #!/usr/bin/env python3.5    # Use the above for cron
import os
import sys
import queue
import socket
import smtplib
import requests
import threading
import configparser
from pytz import timezone
from jinja2 import Template
from datetime import datetime, timedelta
from hpe3parclient import client, exceptions
from hpe3parclient.exceptions import HTTPForbidden
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from requests.packages.urllib3.exceptions import InsecureRequestWarning
from socket import timeout

requests.packages.urllib3.disable_warnings(InsecureRequestWarning)
sys.path.append("/usr/local/lib/python3.5/site-packages/NetApp")
from NaServer import *


class ThreadTP(threading.Thread):
    def run(self):
        hostname = self.hostname
        user = self.username
        password = self.password

        cl = client.HPE3ParClient(
            "https://{}.mitchell.com:8080/api/v1".format(hostname)
        )
        try:
            cl.login(user, password)
        except exceptions.HTTPUnauthorized as ex:
            print("Login failed for host: " + hostname)

        #########
        # RCopy #
        #########

        data_list = []

        rcopy_dict = {"datatype": "rcopy", "array": hostname, "data": []}

        role_dict = {1: "Primary", 2: "Secondary"}
        state_dict = {
            1: "New",
            2: "Starting",
            3: "Started",
            4: "Restart",
            5: "Stopped",
            6: "Backup",
            7: "Failsafe",
            8: "Unknown",
            9: "Logging",
        }

        if "dc1" in hostname:
            host_color = "green"
        elif "dc2" in hostname:
            host_color = "darkorange"
        else:
            host_color = "black"

        try:
            rcopy = cl.getRemoteCopyGroups()
        except HTTPForbidden:
            # print("Error: " + hostname + " isn't licensed for RCopy.")
            pass
        else:
            for group in rcopy["members"]:
                for target in group["targets"]:

                    if state_dict[target["state"]] != "Started":
                        data_list.append(
                            [
                                [hostname, host_color],
                                [group["name"], "black_r"],
                                [role_dict[group["role"]], "black_r"],
                                [state_dict[target["state"]], "red_b_r"],
                            ]
                        )

            rcopy_dict["data"] = data_list
            self.queue_tp.put(rcopy_dict)

        cl.logout()

    def __init__(self, hostname, queue_tp, username, password):
        threading.Thread.__init__(self)
        self.hostname = hostname
        self.queue_tp = queue_tp
        self.username = username
        self.password = password


class ThreadNA(threading.Thread):
    def run(self):
        hostname = self.hostname
        user = self.username
        password = self.password
        ignore_vols = self.ignore_vols
        ignore_snapshots = self.ignore_snapshots
        ignore_events = self.ignore_events
        ignore_sm = self.ignore_sm
        ignore_vol_snapshots = self.ignore_vol_snapshots

        s = NaServer(hostname, 1, 31)
        s.set_server_type("Filer")  # Filer, DFM, or OCUM
        s.set_admin_user(user, password)
        s.set_transport_type("HTTPS")

        _create_unverified_https_context = ssl._create_unverified_context
        ssl._create_default_https_context = _create_unverified_https_context

        # Datetime stuff
        # Only include events in last 24 hours. 24 hours = 86400 seconds
        THREAD_START_TIME = int(datetime.now().timestamp())
        EVENT_TIME_START = int(datetime.now().timestamp()) - 86400  # 24 hours
        DATE_FORMAT = "%m/%d/%Y %H:%M:%S %Z"

        PST = timezone("US/Pacific")
        MAX_RETURN_RECORDS = "12500"  # Set just above the 12288 return values from 6-node cluster EMS logs

        ###############################
        # Processing Code Begins Here #
        ###############################

        ########
        # SVMs #
        ########

        uuid_to_svm_dict = (
            {}
        )  # Used for identifying SVMs from the wafl.maxdirsize event log message

        next_tag = "NA"
        while next_tag:
            nae_input = NaElement("vserver-get-iter")
            nae_input.child_add_string("max-records", MAX_RETURN_RECORDS)
            nae_input.child_add(
                desired_attr_defaults("svm")
            )  # Specify desired attributes

            if next_tag != "NA":
                nae_input.child_add_string("tag", next_tag)

            nae_output = s.invoke_elem(nae_input)
            if nae_output.results_errno() != 0:
                r = nae_output.results_reason()
                print(hostname + " failed: " + str(r))
            else:
                if nae_output.child_get_int("num-records") > 0:
                    if nae_output.child_get_int("num-records") == MAX_RETURN_RECORDS:
                        print(
                            "Warning: "
                            + hostname
                            + " returned "
                            + str(MAX_RETURN_RECORDS)
                            + " SVM records."
                        )

                    attr_list = nae_output.child_get(
                        "attributes-list"
                    )  # <attributes-list>
                    for svm in attr_list.children_get():  # <vserver-info>
                        svm_name = svm.child_get_string("vserver-name")
                        uuid = svm.child_get_string("uuid")

                        uuid_to_svm_dict[uuid] = svm_name

            next_tag = nae_output.child_get_string("next-tag")

        ##############
        # Aggregates #
        ##############

        aggr_dict = {}

        # aggr_dict format:
        # {'dc1_ntap_c2_01_SAS1': {'percent-used-capacity': 29,
        #                          'physical-used':         9364411510784,
        #                          'physical-used-percent': 19,
        #                          'size-available':        32665040871424,
        #                          'size-total':            46098597388288,
        #                          'size-used':             13433556516864}
        # }

        next_tag = "NA"
        while next_tag:
            nae_input = NaElement("aggr-get-iter")
            nae_input.child_add_string("max-records", MAX_RETURN_RECORDS)
            nae_input.child_add(
                desired_attr_defaults("aggregate")
            )  # Specify desired attributes

            if next_tag != "NA":
                nae_input.child_add_string("tag", next_tag)

            nae_output = s.invoke_elem(nae_input)
            if nae_output.results_errno() != 0:
                r = nae_output.results_reason()
                print(hostname + " failed: " + str(r))
            else:
                if nae_output.child_get_int("num-records") > 0:
                    if nae_output.child_get_int("num-records") == MAX_RETURN_RECORDS:
                        print(
                            "Warning: "
                            + hostname
                            + " returned "
                            + str(MAX_RETURN_RECORDS)
                            + " aggregate records."
                        )

                    attr_list = nae_output.child_get(
                        "attributes-list"
                    )  # <attributes-list>
                    for aggregate in attr_list.children_get():  # <aggr-attributes>
                        aggr_vals = {}

                        name = aggregate.child_get_string("aggregate-name")

                        aggr_space_attrs = aggregate.child_get("aggr-space-attributes")

                        # Stor aggr values in temp dict
                        aggr_vals[
                            "percent-used-capacity"
                        ] = aggr_space_attrs.child_get_int("percent-used-capacity")
                        aggr_vals["physical-used"] = aggr_space_attrs.child_get_int(
                            "physical-used"
                        )
                        aggr_vals[
                            "physical-used-percent"
                        ] = aggr_space_attrs.child_get_int("physical-used-percent")
                        aggr_vals["size-available"] = aggr_space_attrs.child_get_int(
                            "size-available"
                        )
                        aggr_vals["size-total"] = aggr_space_attrs.child_get_int(
                            "size-total"
                        )
                        aggr_vals["size-used"] = aggr_space_attrs.child_get_int(
                            "size-used"
                        )

                        # Add this aggregate info to aggr_dict
                        aggr_dict[name] = aggr_vals

            next_tag = nae_output.child_get_string("next-tag")

        ###########
        # Volumes #
        ###########

        MAX_PCT_USED = (
            84  # Any space usage above this percentage will show up on the dashboard
        )
        MAX_PCT_FILES_USED = (
            79  # Any inode usage above this percentage will show up on the dashboard
        )
        MAX_PCT_SNAP_USED = (
            99  # Any % snapshot space usage above this will show up on the dashboard
        )

        # ComCell (located in dc1) is the Commvault Management server
        # ignore_vols = ['vol0', 'CC_dc1_cvcs_', 'root', 'MDV_CRS', 'MDV_aud', 'temp_']
        IGNORE_SVMS = ["Cluster", "ntap", "dr."]

        vol_q_dict = {
            "datatype": "volume",
            "cluster": hostname,
            "data": [],
            "notes": [],
        }

        data_list = []
        next_tag = "NA"

        cv_locked_ss_vols = {
            "csgdev",
            "micsourcedataprod",
            "cm1ntrel",
            "splunkimport",
            "prod4nteditorial",
            "calllogs",
            "protel",
            "userhome",
            "dept",
            "iso",
        }

        while next_tag:
            nae_input = NaElement("volume-get-iter")
            nae_input.child_add_string("max-records", MAX_RETURN_RECORDS)
            nae_input.child_add(
                desired_attr_defaults("volume")
            )  # Specify desired attributes
            nae_input.child_add(
                build_query_element("volume-info")
            )  # Query only attributes values you want

            if next_tag != "NA":
                nae_input.child_add_string("tag", next_tag)

            nae_output = s.invoke_elem(nae_input)
            if nae_output.results_errno() != 0:
                r = nae_output.results_reason()
                print(hostname + " failed: " + str(r))
            else:
                if nae_output.child_get_int("num-records") > 0:
                    if nae_output.child_get_int("num-records") == MAX_RETURN_RECORDS:
                        print(
                            "Warning: "
                            + hostname
                            + " returned "
                            + str(MAX_RETURN_RECORDS)
                            + " volume records."
                        )

                    attr_list = nae_output.child_get(
                        "attributes-list"
                    )  # <attributes-list>
                    for volume in attr_list.children_get():  # <volume-attributes>
                        include_offline = (
                            adjust_space
                        ) = (
                            adjust_snapshot_space
                        ) = adjust_inodes = False  # Flags to include results
                        size = (
                            check_cmd
                        ) = fix_cmd = new_size = vol_notes = new_disp_size = ""
                        new_pct_snap_rsv = "-"

                        vol_id_attrs = volume.child_get("volume-id-attributes")
                        vol_state_attrs = volume.child_get("volume-state-attributes")
                        vol_inode_attrs = volume.child_get("volume-inode-attributes")
                        vol_space_attrs = volume.child_get("volume-space-attributes")
                        vol_state_attrs = volume.child_get("volume-state-attributes")

                        vol_name = vol_id_attrs.child_get_string("name")
                        # if vol_name in cv_locked_ss_vols:
                        #     vol_notes = 'SS space locked by CV'

                        svm_fqdn = svm = vol_id_attrs.child_get_string(
                            "owning-vserver-name"
                        )
                        aggr = vol_id_attrs.child_get_string(
                            "containing-aggregate-name"
                        )

                        vol_state = vol_state_attrs.child_get_string("state")

                        # Process all data
                        aggr_avail_float = bytes_to_x(
                            "t", aggr_dict[aggr]["size-available"]
                        )
                        aggr_avail = str(aggr_avail_float) + " TB"

                        # Include offline volumes
                        vol_notes_color = "black"
                        pct_used_color = (
                            pct_files_used_color
                        ) = pct_snap_used_color = "black_r"

                        # Cannot get inodes / space usage if offline
                        if vol_state == "offline" or vol_state == "restricted":
                            vol_notes += "Offline"
                            vol_notes_color = "red_b"
                            include_offline = True
                            files_tot = (
                                size
                            ) = (
                                files_used
                            ) = (
                                pct_files_used
                            ) = (
                                size_b
                            ) = (
                                size_user_used
                            ) = (
                                pct_used
                            ) = (
                                pct_snap_rsv
                            ) = (
                                pct_snap_used
                            ) = (
                                size_user_total
                            ) = size_snap_used = size_snap_reserve = "-"
                            check_cmd = (
                                "vol show -vserver "
                                + svm_fqdn
                                + " -volume "
                                + vol_name
                                + " -fields state"
                            )
                            fix_cmd = (
                                "# vol delete -vserver "
                                + svm_fqdn
                                + " -volume "
                                + vol_name
                            )
                        else:
                            try:
                                files_tot = vol_inode_attrs.child_get_int("files-total")
                                files_used = vol_inode_attrs.child_get_int("files-used")
                                pct_files_used = int(
                                    round(files_used / files_tot * 100, 0)
                                )

                                size_b = vol_space_attrs.child_get_int("size")
                                size_user_used_b = vol_space_attrs.child_get_int(
                                    "size-used"
                                )
                                pct_used = vol_space_attrs.child_get_int(
                                    "percentage-size-used"
                                )
                                pct_snap_rsv = vol_space_attrs.child_get_int(
                                    "percentage-snapshot-reserve"
                                )
                                pct_snap_used = vol_space_attrs.child_get_int(
                                    "percentage-snapshot-reserve-used"
                                )

                                size_user_total = vol_space_attrs.child_get_int(
                                    "size-total"
                                )  # size available to user in B
                                size_snap_reserve = vol_space_attrs.child_get_int(
                                    "snapshot-reserve-size"
                                )  # total size in B for snapshots
                                size_snap_used = vol_space_attrs.child_get_int(
                                    "size-used-by-snapshots"
                                )  # size used in B by snapshots

                            except AttributeError:
                                print(
                                    "Could not get volume info for "
                                    + str(hostname)
                                    + ":"
                                    + "\n    SVM:   "
                                    + str(svm_fqdn)
                                    + "\n    Name:  "
                                    + str(vol_name)
                                    + "\n    State: "
                                    + str(vol_state)
                                )
                                continue

                        # Strip domain from SVM names
                        for domain in [
                            ".mitchell.com",
                            ".local.mitchellsmartadvisor.local",
                            ".production.int",
                            ".staging.int",
                            ".corp.int",
                            ".prod.mitchellsmartadvisor.com",
                            ".prodsaca.int",
                            ".uatsaca.int",
                        ]:
                            svm = svm.replace(domain, "")

                        # Skip      volumes                        and         svms     in "ignore" lists
                        if any(x in vol_name for x in ignore_vols) or any(
                            x in svm_fqdn for x in IGNORE_SVMS
                        ):
                            continue

                        # Shorten aggr name, e.g.: dc1_ntap_c1_01_SAS1 to c11_01_SAS1
                        aggr = aggr.replace("dc", "c").replace("_ntap_c", "")

                        # Determine what actions need to happen
                        if vol_state == "online":
                            if (
                                pct_used > MAX_PCT_USED
                                and "CC_dc1_cvcs" not in vol_name
                            ):
                                adjust_space = True
                            if pct_used >= 100 and "CC_dc1_cvcs" in vol_name:
                                adjust_space = True
                            if (
                                pct_snap_used > MAX_PCT_SNAP_USED
                                and "CC_dc1_cvcs" not in vol_name
                            ):
                                adjust_snapshot_space = True
                            if (
                                pct_files_used > MAX_PCT_FILES_USED
                                and "CC_dc1_cvcs" not in vol_name
                            ):
                                adjust_inodes = True

                            # If volume needs resizing
                            if adjust_space or adjust_snapshot_space:
                                # Calculate new USEABLE volume space
                                if adjust_space:
                                    if size_b > 10995116277760:
                                        new_size_user_total = int(
                                            size_user_used_b / 0.8
                                        )  # Grow to 80% full if volume > 10tb
                                    else:
                                        new_size_user_total = int(
                                            size_user_used_b / 0.75
                                        )  # Grow to 75% full otherwise
                                    pct_used_color = "red_b_r"

                                else:
                                    new_size_user_total = size_user_total

                                # Calculate new SNAPSHOT volume space
                                if adjust_snapshot_space:
                                    new_size_snap_reserve = int(size_snap_used / 0.90)
                                    pct_snap_used_color = "red_b_r"
                                else:
                                    new_size_snap_reserve = size_snap_reserve

                                # Combine useable and snapshot for TOTAL volume size
                                new_size_b = new_size_snap_reserve + new_size_user_total

                                # Calculate new SNAP PERCENT
                                new_pct_snap = int(
                                    new_size_snap_reserve / new_size_b * 100
                                )
                                if new_pct_snap < 5:
                                    new_pct_snap = 5
                                new_pct_snap_rsv = str(new_pct_snap) + " %"

                            else:
                                new_size_b = size_b  # Here to let the new_size calculate in the next if statement

                            if new_size_b > 1073741824000:
                                # If larger than 1000g, use TB sizing
                                size = (
                                    str(bytes_to_x("t", size_b)).replace(".0", "")
                                    + " TB"
                                )  # Display size
                                size_user_used = (
                                    str(bytes_to_x("t", size_user_used_b)) + " TB"
                                )  # Display used size
                                new_size = (
                                    str(bytes_to_x("t", new_size_b)).replace(".0", "")
                                    + "t"
                                )  # New size for resize command
                                new_disp_size = new_size.replace(
                                    "t", " TB"
                                )  # New size for comparison - displayed in green

                            elif new_size_b < 5368709120:
                                # If less than 5g, round up to nearest 1gb
                                size = (
                                    str(bytes_to_x("g", size_b)).replace(".0", "")
                                    + " GB"
                                )  # Display size
                                size_user_used = (
                                    str(bytes_to_x("g", size_user_used_b)).replace(
                                        ".0", ""
                                    )
                                    + " GB"
                                )  # Display used size

                                new_size_g = bytes_to_x("g", new_size_b)
                                new_size = (
                                    str(int(new_size_g + 1 - new_size_g % 1)) + "g"
                                )  # New size for resize command - int() to remove .0 and .00000000x, etc.
                                new_disp_size = new_size.replace(
                                    "g", " GB"
                                )  # New size for comparison - displayed in green

                            else:
                                # Between 5g and 1000g, round to nearest 5g
                                size = (
                                    str(bytes_to_x("g", size_b)).replace(".0", "")
                                    + " GB"
                                )  # Display size
                                size_user_used = (
                                    str(bytes_to_x("g", size_user_used_b)).replace(
                                        ".0", ""
                                    )
                                    + " GB"
                                )  # Display used size

                                new_size_g = bytes_to_x("g", new_size_b)
                                new_size = (
                                    str(int(new_size_g + 5 - new_size_g % 5)) + "g"
                                )  # New size for resize command
                                new_disp_size = new_size.replace(
                                    "g", " GB"
                                )  # New size for comparison - displayed in green

                            # If VOLUME and/or SNAPSHOT SPACE is full
                            if adjust_space or adjust_snapshot_space:
                                fix_cmd += (
                                    "# vol modify -vserver "
                                    + svm_fqdn
                                    + " -volume "
                                    + vol_name
                                    + " -size "
                                    + new_size
                                    + " -percent-snapshot-space "
                                    + new_pct_snap_rsv.replace(" %", "")
                                )

                                if adjust_snapshot_space:
                                    check_cmd += "snap list " + vol_name
                                    check_cmd += (
                                        "<BR>vol show -vserver "
                                        + svm_fqdn
                                        + " -volume "
                                        + vol_name
                                        + " -fields size,used,percent-used,percent-snapshot-space,snapshot-space-used,aggregate"
                                    )
                                else:
                                    check_cmd += (
                                        "vol show -vserver "
                                        + svm_fqdn
                                        + " -volume "
                                        + vol_name
                                        + " -fields size,used,percent-used,percent-snapshot-space,snapshot-space-used,aggregate"
                                    )

                            # If INODES are full
                            if adjust_inodes:
                                if (
                                    not adjust_space and not adjust_snapshot_space
                                ):  # Remove display size if space/snapshot space isn't being adjusted
                                    new_disp_size = "-"

                                pct_files_used_color = "red_b_r"

                                if check_cmd != "":
                                    check_cmd += "<BR>"
                                check_cmd += "df -i " + vol_name

                                if fix_cmd != "":
                                    fix_cmd += "<BR>"
                                # Set inodes to 75% full:     -->  -    -    -    -    -    -    -    -    -    -    -    -    -    -    -    -   v
                                fix_cmd += (
                                    "# vol modify -vserver "
                                    + svm_fqdn
                                    + " -volume "
                                    + vol_name
                                    + " -files "
                                    + str(round(float(files_used) / 0.75, 0)).replace(
                                        ".0", ""
                                    )
                                )

                        if (
                            include_offline
                            or adjust_inodes
                            or adjust_space
                            or adjust_snapshot_space
                        ):
                            data_list.append(
                                [
                                    [hostname, color_code_cluster(hostname)],
                                    [svm, "black"],
                                    [vol_name, "black"],
                                    [str(size), "black_r"],
                                    [str(new_disp_size), "green_r"],  # Proposed size
                                    [str(size_user_used), "black_r"],
                                    [str(pct_used) + " %", pct_used_color],
                                    [str(pct_snap_rsv) + " %", "black_r"],
                                    [
                                        str(new_pct_snap_rsv),
                                        "green_r",
                                    ],  # Proposed snapshot %
                                    [str(pct_snap_used) + " %", pct_snap_used_color],
                                    [aggr, "black"],
                                    [str(aggr_avail), "black_r"],
                                    [str(files_tot), "black_r"],
                                    [str(pct_files_used) + " %", pct_files_used_color],
                                    [vol_notes, vol_notes_color],
                                    [check_cmd, "black"],
                                    [fix_cmd, "black"],
                                ]
                            )

            next_tag = nae_output.child_get_string("next-tag")

        # if len(data_list) > 0:
        vol_q_dict["data"] = data_list
        self.queue_na.put(vol_q_dict)

        ##################
        # Cron Schedules #
        ##################

        cron_dict = {"datatype": "cron", "cluster": hostname, "data": []}

        data_list = []

        next_tag = "NA"
        while next_tag:
            nae_input = NaElement("job-schedule-cron-get-iter")
            nae_input.child_add_string("max-records", MAX_RETURN_RECORDS)

            if next_tag != "NA":
                nae_input.child_add_string("tag", next_tag)

            nae_output = s.invoke_elem(nae_input)
            if nae_output.results_errno() != 0:
                r = nae_output.results_reason()
                print(hostname + " failed: " + str(r))
            else:
                if nae_output.child_get_int("num-records") > 0:
                    if nae_output.child_get_int("num-records") == MAX_RETURN_RECORDS:
                        print(
                            "Warning: "
                            + hostname
                            + " returned "
                            + str(MAX_RETURN_RECORDS)
                            + " cron records."
                        )

                    attr_list = nae_output.child_get(
                        "attributes-list"
                    )  # <attributes-list>

                    for (
                        cron_sched
                    ) in attr_list.children_get():  # <job-schedule-cron-info>
                        name = cron_sched.child_get_string("job-schedule-name")
                        data_list.append(name)

            next_tag = nae_output.child_get_string("next-tag")

        cron_dict["data"] = data_list
        self.queue_na.put(cron_dict)

        ###############
        # SnapMirrors #
        ###############

        sm_q_dict = {"datatype": "snapmirror", "cluster": hostname, "data": []}
        data_list = []

        sync_24h_svms = [
            "farcv01nas",
            "nearcv01nas",
            "torcv01nas",
            "vancv01nas",
            "prod16nas",
        ]

        next_tag = "NA"
        while next_tag:
            nae_input = NaElement("snapmirror-get-iter")
            nae_input.child_add_string("max-records", MAX_RETURN_RECORDS)
            nae_input.child_add(
                desired_attr_defaults("snapmirror")
            )  # Specify desired attributes
            nae_input.child_add(
                build_query_element("snapmirror-info")
            )  # Query only attribute values you want

            if next_tag != "NA":
                nae_input.child_add_string("tag", next_tag)

            nae_output = s.invoke_elem(nae_input)
            if nae_output.results_errno() != 0:
                r = nae_output.results_reason()
                print(hostname + " failed: " + str(r))
            else:
                # dc1-ntap-c1 and dc3-ntap-c1 do not have snapmirror destinations
                if nae_output.child_get_int("num-records") > 0:
                    if nae_output.child_get_int("num-records") == MAX_RETURN_RECORDS:
                        print(
                            "Warning: "
                            + hostname
                            + " returned "
                            + str(MAX_RETURN_RECORDS)
                            + " Snapmirror records."
                        )

                    # print(hostname + ' ' + nae_output.child_get_string('num-records'))
                    attr_list = nae_output.child_get(
                        "attributes-list"
                    )  # <attributes-list>
                    for snapmirror in attr_list.children_get():  # <snapmirror-info>
                        dest = snapmirror.child_get_string("destination-location")
                        dest_vserver = snapmirror.child_get_string(
                            "destination-vserver"
                        )
                        # dest_vol = snapmirror.child_get_string('destination-volume')
                        healthy = snapmirror.child_get_string("is-healthy")

                        # Skip any destinations in "ignore" list
                        if any(x in dest for x in ignore_sm):
                            continue

                        if snapmirror.child_get_string("lag-time") is not None:
                            lagtime = round(
                                snapmirror.child_get_int("lag-time") / 3600, 1
                            )  # Convert to hours
                        else:
                            lagtime = "NA"  # Account for when snapmirrors are broken - lag-time DNE

                        state = snapmirror.child_get_string("mirror-state")
                        unhealthy_reason = snapmirror.child_get_string(
                            "unhealthy-reason"
                        )
                        # source = snapmirror.child_get_string('source-location')
                        ident_preserve = snapmirror.child_get_string(
                            "identity-preserve"
                        )

                        if healthy == "true":
                            unhealthy_reason = ""

                        lagtime_color = (
                            healthy_color
                        ) = state_color = unhealthy_reason_color = "black"

                        # Filter out vserver DR destinations (e.g. "prod01nas.mitchell.com:")
                        if ident_preserve is None:

                            include_snapmirror_vol = False
                            # If any filter matches, include the result in the dashboard and set the color of the cell that has an issue
                            if (
                                type(lagtime) != str
                            ):  # Handle if snapmirrors are broken w/no lagtime value
                                if lagtime > 2 and not any(
                                    x in dest_vserver for x in sync_24h_svms
                                ):
                                    include_snapmirror_vol = True
                                    lagtime_color = "red_b"
                                if lagtime > 24 and any(
                                    x in dest_vserver for x in sync_24h_svms
                                ):
                                    include_snapmirror_vol = True
                                    lagtime_color = "red_b"
                            if healthy != "true":
                                include_snapmirror_vol = True
                                healthy_color = "red_b"
                                unhealthy_reason_color = "red_b"
                            if state != "snapmirrored":
                                include_snapmirror_vol = True
                                state_color = "red_b"

                            if include_snapmirror_vol:
                                data_list.append(
                                    [
                                        [hostname, color_code_cluster(hostname)],
                                        [dest, "black"],
                                        [state, state_color],
                                        [str(lagtime), lagtime_color],
                                        [healthy, healthy_color],
                                        [unhealthy_reason, unhealthy_reason_color],
                                    ]
                                )

            next_tag = nae_output.child_get_string("next-tag")

        sm_q_dict["data"] = data_list
        self.queue_na.put(sm_q_dict)

        #############
        # Snapshots #
        #############

        SS_33_DAYS = int(datetime.now().timestamp()) - 2851200
        SS_91_DAYS = int(datetime.now().timestamp()) - 7862400
        # SS_365_DAYS = int(datetime.now().timestamp()) - 31708800  # 367 days actually
        # SS_365_DAYS = int(datetime.now().timestamp()) - 34560000  # 400 days - Tim has monthly snapshots that roll off at a year + 1 month.
        SS_365_DAYS = (
            int(datetime.now().timestamp()) - 37152000
        )  # 430 days - 2020-03-20 - Temporarily set to 430 to reduce clutter in dashboard. Tim has a case with commvault for why monthly's are rolling off a month late.
        MAX_SS_RECORDS = (
            "100"  # Snapshots are slow with API, limit them so timeouts don't occur
        )

        ss_q_dict = {"datatype": "snapshot", "cluster": hostname, "data": []}
        data_list = []

        next_tag = "NA"
        while next_tag:
            nae_input = NaElement("snapshot-get-iter")
            nae_input.child_add_string("max-records", MAX_SS_RECORDS)
            nae_input.child_add(
                desired_attr_defaults("snapshot")
            )  # Specify desired attributes

            if next_tag != "NA":
                nae_input.child_add_string("tag", next_tag)

            nae_output = s.invoke_elem(nae_input)
            if nae_output.results_errno() != 0:
                r = nae_output.results_reason()
                print(hostname + " failed: " + str(r))
            else:
                if nae_output.child_get_int("num-records") > 0:
                    if nae_output.child_get_int("num-records") == MAX_RETURN_RECORDS:
                        print(
                            "Warning: "
                            + hostname
                            + " returned "
                            + str(MAX_RETURN_RECORDS)
                            + " snapshot records."
                        )

                    attr_list = nae_output.child_get(
                        "attributes-list"
                    )  # <attributes-list>

                    for snapshot in attr_list.children_get():  # <snapshot-info>
                        create_time = snapshot.child_get_int("access-time")
                        snapshot_name = snapshot.child_get_string("name")
                        volume = snapshot.child_get_string("volume")
                        svm_fqdn = svm = snapshot.child_get_string("vserver")

                        snapshot_age_color = "black_r"

                        include_snapshot = False

                        # Strip domain from SVM names
                        for domain in [
                            ".mitchell.com",
                            ".local.mitchellsmartadvisor.local",
                            ".production.int",
                            ".staging.int",
                            ".corp.int",
                            ".prod.mitchellsmartadvisor.com",
                        ]:
                            svm = svm.replace(domain, "")

                        if "dr." in svm_fqdn:
                            continue

                        if "usrtmp" in volume:
                            if create_time < SS_91_DAYS:
                                include_snapshot = True
                                snapshot_age = str(
                                    timedelta(seconds=(THREAD_START_TIME - create_time))
                                )
                                snapshot_age_color = "red_b_r"

                        elif (
                            "torcv01nas" in svm
                            or "vancv01nas" in svm
                            or "nearcv01nas" in svm
                            or "farcv01nas" in svm
                        ):
                            if create_time < SS_365_DAYS:
                                include_snapshot = True
                                snapshot_age = str(
                                    timedelta(seconds=(THREAD_START_TIME - create_time))
                                )
                                snapshot_age_color = "red_b_r"

                        elif create_time < SS_33_DAYS:
                            include_snapshot = True
                            snapshot_age = str(
                                timedelta(seconds=(THREAD_START_TIME - create_time))
                            )
                            snapshot_age_color = "red_b_r"

                        if include_snapshot:
                            # Ignore if it is on the "ignore" list
                            if any(x in snapshot_name for x in ignore_snapshots):
                                continue

                            # Skip all snapshots for specified volumes in "ignoreTheseVolumeSnapshots" file
                            if any(x in volume for x in ignore_vol_snapshots):
                                continue

                            # Fix formatting from 1:23:45 to 01:23:45
                            if snapshot_age[-8] == " ":
                                new_age = snapshot_age[:-7] + "0" + snapshot_age[-7:]
                                snapshot_age = new_age

                            delete_cmd = (
                                "# snapshot delete -vserver "
                                + svm_fqdn
                                + " -volume "
                                + volume
                                + " -snapshot "
                                + snapshot_name
                            )
                            # delete_cmd = '' # command above is too wide for email display

                            data_list.append(
                                [
                                    [hostname, color_code_cluster(hostname)],
                                    [svm, "black"],
                                    [volume, "black"],
                                    [snapshot_name, "black"],
                                    [snapshot_age, snapshot_age_color],
                                    [delete_cmd, "black"],
                                ]
                            )

            next_tag = nae_output.child_get_string("next-tag")

        ss_q_dict["data"] = data_list
        self.queue_na.put(ss_q_dict)

        ########
        # LIFs #
        ########

        lif_q_dict = {"datatype": "lif", "cluster": hostname, "data": []}
        data_list = []

        next_tag = "NA"
        while next_tag:
            nae_input = NaElement("net-interface-get-iter")
            nae_input.child_add_string("max-records", MAX_RETURN_RECORDS)
            nae_input.child_add(
                desired_attr_defaults("lif")
            )  # Specify desired attributes

            if next_tag != "NA":
                nae_input.child_add_string("tag", next_tag)

            nae_output = s.invoke_elem(nae_input)
            if nae_output.results_errno() != 0:
                r = nae_output.results_reason()
                print(hostname + " failed: " + str(r))
            else:
                if nae_output.child_get_int("num-records") > 0:
                    if nae_output.child_get_int("num-records") == MAX_RETURN_RECORDS:
                        print(
                            "Warning: "
                            + hostname
                            + " returned "
                            + str(MAX_RETURN_RECORDS)
                            + " LIF records."
                        )

                    attr_list = nae_output.child_get(
                        "attributes-list"
                    )  # <attributes-list>
                    for lif in attr_list.children_get():  # <net-interface-info>
                        # address = lif.child_get_string('address')
                        administrative_status = lif.child_get_string(
                            "administrative-status"
                        )
                        # current_node = lif.child_get_string('current-node')
                        # current_port = lif.child_get_string('current-port')
                        # home_node = lif.child_get_string('home-node')
                        # home_port = lif.child_get_string('home-port')
                        lif_name = lif.child_get_string("interface-name")
                        is_home = lif.child_get_string("is-home")
                        operational_status = lif.child_get_string("operational-status")
                        role = lif.child_get_string("role")
                        vserver = lif.child_get_string("vserver")

                        operational_status_color = (
                            administrative_status_color
                        ) = is_home_color = "black"

                        include_lif = False

                        if is_home != "true":
                            include_lif = True
                            is_home_color = "red_b"

                        if (
                            "dr." not in vserver
                            and operational_status != administrative_status
                        ):
                            include_lif = True
                            operational_status_color = "red_b"
                            administrative_status_color = "red_b"

                        if include_lif:
                            data_list.append(
                                [
                                    [hostname, color_code_cluster(hostname)],
                                    [vserver, "black"],
                                    [lif_name, "black"],
                                    [role, "black"],
                                    [
                                        administrative_status,
                                        administrative_status_color,
                                    ],
                                    [operational_status, operational_status_color],
                                    [is_home.title(), is_home_color],
                                ]
                            )

            next_tag = nae_output.child_get_string("next-tag")

        lif_q_dict["data"] = data_list
        self.queue_na.put(lif_q_dict)

        #########
        # Disks #
        #########

        MAX_DISK_RECORDS = (
            "100"  # Snapshots are slow with API, limit them so timeouts don't occur
        )

        disk_q_dict = {"datatype": "disk", "cluster": hostname, "data": []}
        data_list = []

        next_tag = "NA"
        while next_tag:
            nae_input = NaElement("storage-disk-get-iter")
            nae_input.child_add_string("max-records", MAX_DISK_RECORDS)
            nae_input.child_add(
                desired_attr_defaults("disk")
            )  # Specify desired attributes

            if next_tag != "NA":
                nae_input.child_add_string("tag", next_tag)

            nae_output = s.invoke_elem(nae_input)
            if nae_output.results_errno() != 0:
                r = nae_output.results_reason()
                print(hostname + " failed: " + str(r))
            else:
                if nae_output.child_get_int("num-records") > 0:
                    if nae_output.child_get_int("num-records") == MAX_RETURN_RECORDS:
                        print(
                            "Warning: "
                            + hostname
                            + " returned "
                            + str(MAX_RETURN_RECORDS)
                            + " disk records."
                        )

                    attr_list = nae_output.child_get(
                        "attributes-list"
                    )  # <attributes-list>
                    for disk in attr_list.children_get():  # <storage-disk-info>

                        # nae_storage_disk_info = disk.child_get('storage-disk-info')

                        owner_node = (
                            is_zeroed
                        ) = (
                            is_zeroed_color
                        ) = (
                            container_type
                        ) = serial_number = disk_name = owner_node = is_failed = ""

                        nae_disk_inventory_info = disk.child_get("disk-inventory-info")
                        nae_disk_ownership_info = disk.child_get("disk-ownership-info")
                        nae_disk_raid_info = disk.child_get("disk-raid-info")

                        # disk_type = nae_disk_inventory_info.child_get_string('disk-type')
                        serial_number = nae_disk_inventory_info.child_get_string(
                            "serial-number"
                        )

                        is_failed = nae_disk_ownership_info.child_get_string(
                            "is-failed"
                        )
                        owner_node = nae_disk_ownership_info.child_get_string(
                            "owner-node-name"
                        )

                        container_type = nae_disk_raid_info.child_get_string(
                            "container-type"
                        )

                        disk_name = disk.child_get_string("disk-name")
                        is_zeroed_color = (
                            is_failed_color
                        ) = container_type_color = "black"
                        include_disk = False

                        if is_failed == "true":
                            include_disk = True
                            is_failed_color = "red_b"

                        if container_type == "spare":
                            nae_disk_spare_info = nae_disk_raid_info.child_get(
                                "disk-spare-info"
                            )
                            is_zeroed = nae_disk_spare_info.child_get_string(
                                "is-zeroed"
                            )

                            if is_zeroed == "false":
                                include_disk = True
                                is_zeroed_color = "red_b"

                        elif any(
                            x in container_type
                            for x in [
                                "broken",
                                "foreign",
                                "unassigned",
                                "unknown",
                                "unsupported",
                            ]
                        ):
                            include_disk = True
                            container_type_color = "red_b"
                            is_zeroed = "N/A"

                        if include_disk:
                            data_list.append(
                                [
                                    [hostname, color_code_cluster(hostname)],
                                    [owner_node, "black"],
                                    [disk_name, "black"],
                                    [serial_number, "black"],
                                    [container_type, container_type_color],
                                    [is_failed.title(), is_failed_color],
                                    [is_zeroed.title(), is_zeroed_color],
                                ]
                            )

            next_tag = nae_output.child_get_string("next-tag")

        disk_q_dict["data"] = data_list
        self.queue_na.put(disk_q_dict)

        ##########
        # Events #
        ##########

        maxdir_dict = {}

        # Common messages - message count variables
        secd_conn_auth_failure_count = 0
        dns_server_timed_out_count = 0
        secd_dns_server_timed_out_count = 0
        secd_nameTrans_noNameMapping_count = 0
        secd_nfsAuth_noNameMap_count = 0
        ontap_8_max_dir_size_set = set()

        event_q_dict = {"datatype": "event", "cluster": hostname, "data": []}
        data_list = []

        next_tag = "NA"
        while next_tag:
            nae_input = NaElement("ems-message-get-iter")
            nae_input.child_add_string("max-records", MAX_RETURN_RECORDS)
            nae_input.child_add(
                desired_attr_defaults("event")
            )  # Specify desired attributes

            if next_tag != "NA":
                nae_input.child_add_string("tag", next_tag)

            nae_output = s.invoke_elem(nae_input)
            if nae_output.results_errno() != 0:
                r = nae_output.results_reason()
                print(hostname + " failed: " + str(r))
            else:
                if nae_output.child_get_int("num-records") > 0:
                    if nae_output.child_get_int("num-records") == MAX_RETURN_RECORDS:
                        print(
                            "Warning: "
                            + hostname
                            + " returned "
                            + str(MAX_RETURN_RECORDS)
                            + " event records."
                        )

                    attr_list = nae_output.child_get(
                        "attributes-list"
                    )  # <attributes-list>
                    for event in attr_list.children_get():  # <ems-message-info>
                        ems_time_color = "black"
                        include_event = False

                        message_name = event.child_get_string("message-name")
                        time = event.child_get_int("time")
                        node = event.child_get_string("node")[-1]
                        severity = event.child_get_string(
                            "severity"
                        ).title()  # Capitalize first letter
                        ems_message = event.child_get_string("event")

                        # Ignore specific messages here, and filter for within last 24 hours
                        # Ignore specific event messages
                        if (
                            any(x in message_name for x in ignore_events)
                            or time < EVENT_TIME_START
                        ):
                            continue

                        # Obtain quantity of common messages and take care of it after iterating through the API
                        if "secd.nameTrans.noNameMapping" in message_name:  # 8.3
                            secd_nameTrans_noNameMapping_count += 1
                            continue

                        if "secd.nfsAuth.noNameMap" in message_name:  # 9.1
                            secd_nfsAuth_noNameMap_count += 1
                            continue

                        if "dns.server.timed.out" in message_name:
                            dns_server_timed_out_count += 1
                            continue

                        if "secd.dns.server.timed.out" in message_name:
                            secd_dns_server_timed_out_count += 1
                            continue

                        if "secd.conn.auth.failure" in message_name:
                            secd_conn_auth_failure_count += 1
                            continue

                        # Reduce # of messages for wafl.dir.size.max.warning and display filepath/vserver
                        if "wafl.dir.size.max.warning" in message_name:
                            # Parse message: 'wafl.dir.size.max.warning: Directory size for fileid 8353856 in volume \
                            # ecdsharedev@vserver:7f4c869e-44fb-11e4-bf82-123478563412 is approaching the maxdirsize limit.'

                            if (
                                hostname == "dc1-ntap-c1"
                                or hostname == "dc3-ntap-c1"
                                or hostname == "dc2-ntap-c2"
                                or hostname == "dc1-ntap-c2"
                            ):  # ONTAP 9.1 filers. Fix this.
                                directory_id = ems_message.split(" ")[5]
                                vol_svm_uuid = ems_message.split(" ")[8]

                                # Sometimes a (1) is appended to the vol name:
                                # dpimporteruat(1)@vserver:b8d45799-8163-11e4-bf82-123478563412
                                svm_uuid = vol_svm_uuid[vol_svm_uuid.find(":") + 1 :]
                                vol_name = vol_svm_uuid[
                                    : vol_svm_uuid.find("@")
                                ].replace("(1)", "")

                                try:
                                    svm_name = uuid_to_svm_dict[svm_uuid]
                                except KeyError:
                                    print(
                                        "Could not find "
                                        + svm_name
                                        + " in uuid_to_svm_dict"
                                    )
                                    continue

                                if svm_name not in maxdir_dict:
                                    get_path = NaServer(hostname, 1, 31)
                                    get_path.set_server_type(
                                        "Filer"
                                    )  # Filer, DFM, or OCUM
                                    get_path.set_admin_user(user, password)
                                    get_path.set_transport_type("HTTPS")
                                    get_path.set_vserver(svm_name)
                                    get_path.set_transport_type("HTTPS")
                                    _create_unverified_https_context = (
                                        ssl._create_unverified_context
                                    )
                                    ssl._create_default_https_context = (
                                        _create_unverified_https_context
                                    )

                                    # Build query element
                                    nae_query = NaElement("query")
                                    nae_inode_info = NaElement("inode-info")
                                    nae_inode_info.child_add_string("volume", vol_name)
                                    nae_inode_info.child_add_string(
                                        "inode-number", directory_id
                                    )
                                    nae_query.child_add(nae_inode_info)

                                    # Query vserver
                                    nae_dir_input = NaElement(
                                        "file-inode-info-get-iter"
                                    )
                                    nae_dir_input.child_add(nae_query)
                                    nae_dir_output = get_path.invoke_elem(nae_dir_input)

                                    # Parse output
                                    try:
                                        dir_attr_list = nae_dir_output.child_get(
                                            "attributes-list"
                                        )
                                        dir_inode_info = dir_attr_list.child_get(
                                            "inode-info"
                                        )
                                        directory = dir_inode_info.child_get_string(
                                            "file-path"
                                        )
                                    except AttributeError:
                                        print(
                                            "Error getting directory for cluster: "
                                            + hostname
                                            + " SVM: "
                                            + svm_name
                                            + " Volume: "
                                            + vol_name
                                            + ". The file may have been deleted already."
                                        )
                                        directory = "ERROR_Possibly_Deleted_Already"

                                    # Add to list of directories over the limit
                                    maxdir_dict[svm_name] = [vol_name, directory]

                                    # Print time for latest result to not clutter the log
                                    time = "Multiple. Most recent:<BR>" + PST.localize(
                                        datetime.fromtimestamp(time)
                                    ).strftime(DATE_FORMAT)

                                    # Print the new more useable ems_message with the path and vserver name instead of fileid and vserver uuid
                                    ems_message = (
                                        "wafl.dir.size.max.warning: Directory size for "
                                        + directory
                                        + " on "
                                        + svm_name
                                        + ":"
                                        + vol_name
                                        + " is approaching the maxdirsize limit."
                                    )
                                    ems_time_color = "coral_b"
                                else:
                                    continue
                            else:
                                directory = ems_message.split()[2]
                                if directory not in ontap_8_max_dir_size_set:
                                    ontap_8_max_dir_size_set.add(directory)
                                    continue
                                else:
                                    continue

                        # Ignore vifmgr.lifs.noredundancy for ndmp LIFs
                        if (
                            message_name == "vifmgr.lifs.noredundancy"
                            and "ndmp" in ems_message
                        ) or (
                            message_name == "vifmgr.lifs.noredundancy"
                            and "cluspeer" in ems_message
                        ):
                            continue

                        # Ignore farcv01nas LS mirror snapmirror update failures:
                        if (
                            message_name == "mgmt.snapmir.update.fail"
                            and "farcv01nas_root" in ems_message
                        ):
                            continue

                        # Ignore name-mapping error event caused by DBA script bug
                        # if 'secd.nameTrans.noNameMapping' in message_name and 'could not map name (101)' in ems_message:
                        #    if DBA_error_included:
                        #        continue
                        #    else:
                        #        DBA_error_included = True
                        #        time = 'Multiple. Most recent:<BR>' + PST.localize(datetime.fromtimestamp(time)).strftime(DATE_FORMAT)
                        #        ems_time_color = 'black_b'

                        # Check for specific messages
                        # if 'wafl.vol.autoSize' in message_name:
                        #     include_event = True
                        #     severity_color = 'black'

                        # Check for important messages
                        if severity == "Emergency":
                            include_event = True
                            severity_color = "red_b"
                        elif severity == "Alert":
                            include_event = True
                            severity_color = "orangered_b"
                        elif severity == "Error":
                            include_event = True
                            severity_color = "goldenrod_b"
                        elif (
                            severity == "Critical"
                        ):  # Delete this after all filers are on 9.x
                            include_event = True
                            severity_color = "red_b"

                        if include_event:

                            # Place <br> in long ems messages so table width isn't too long
                            step = 170  # When ems_message is longer than this number, break it into smaller chunks
                            if len(ems_message) > step:
                                new_str = ""
                                if len(ems_message) > step:
                                    start = 0
                                    stop = step

                                    while stop <= len(ems_message):
                                        new_str += ems_message[start:stop] + "<BR>"
                                        # new_str += '<BR>'
                                        start += step
                                        stop += step
                                    new_str += ems_message[start:stop]
                                    ems_message = new_str

                            # Convert time to human-readable format
                            if (
                                type(time) != str
                            ):  # Either int or string depending on if the time was changed to 'Most Recent:' to only show one entry.
                                time = PST.localize(
                                    datetime.fromtimestamp(time)
                                ).strftime(DATE_FORMAT)

                            data_list.append(
                                [
                                    [hostname, color_code_cluster(hostname)],
                                    [node, "black_c"],
                                    [severity, severity_color],
                                    [time, ems_time_color],
                                    [ems_message, "black"],
                                ]
                            )

            next_tag = nae_output.child_get_string("next-tag")

        # Reduce common messages down to a count of how many
        if secd_conn_auth_failure_count > 0:
            data_list.insert(
                0,
                [
                    [hostname, color_code_cluster(hostname)],
                    ["All", "black_c"],
                    ["Warning", "black"],
                    ["Multiple - " + str(secd_conn_auth_failure_count), "black_b"],
                    [
                        "secd.conn.auth.failure: SVM (< svm >) could not make a connection over the network to server (ip < ip address >, port < port >) via interface < ip address >. Error: Operation timed out or was reset by peer.",
                        "black",
                    ],
                ],
            )

        if secd_dns_server_timed_out_count > 0:
            data_list.insert(
                0,
                [
                    [hostname, color_code_cluster(hostname)],
                    ["All", "black_c"],
                    ["Warning", "black"],
                    ["Multiple - " + str(secd_dns_server_timed_out_count), "black_b"],
                    [
                        "dns.server.timed.out: DNS server < ip address > did not respond to SVM = < svm > within timeout interval. ",
                        "black",
                    ],
                ],
            )

        if dns_server_timed_out_count > 0:
            data_list.insert(
                0,
                [
                    [hostname, color_code_cluster(hostname)],
                    ["All", "black_c"],
                    ["Warning", "black"],
                    ["Multiple - " + str(dns_server_timed_out_count), "black_b"],
                    [
                        "secd.dns.server.timed.out: DNS server < ip address > did not respond to SVM = < svm > within timeout interval. ",
                        "black",
                    ],
                ],
            )

        if secd_nameTrans_noNameMapping_count > 0:
            data_list.insert(
                0,
                [
                    [hostname, color_code_cluster(hostname)],
                    ["All", "black_c"],
                    ["Warning", "black"],
                    [
                        "Multiple - " + str(secd_nameTrans_noNameMapping_count),
                        "black_b",
                    ],
                    [
                        "secd.nameTrans.noNameMapping: SVM (< svm >) could not map name (< name >). Reason: No rule exists to map name of user from unix-win.",
                        "black",
                    ],
                ],
            )

        if secd_nfsAuth_noNameMap_count > 0:
            data_list.insert(
                0,
                [
                    [hostname, color_code_cluster(hostname)],
                    ["All", "black_c"],
                    ["Warning", "black"],
                    ["Multiple - " + str(secd_nfsAuth_noNameMap_count), "black_b"],
                    [
                        "secd.nfsAuth.noNameMap: vserver (< svm >) Cannot map Unix name to CIFS name.",
                        "black",
                    ],
                ],
            )

        if len(ontap_8_max_dir_size_set) > 0:
            for maxdir in ontap_8_max_dir_size_set:
                data_list.insert(
                    0,
                    [
                        [hostname, color_code_cluster(hostname)],
                        ["-", "black_b_c"],
                        ["Warning", "black"],
                        ["Multiple", "black_b"],
                        [
                            "wafl.dir.size.max.warning: Directory "
                            + maxdir
                            + " is approaching the maxdirsize limit.",
                            "black",
                        ],
                    ],
                )

        event_q_dict["data"] = data_list
        self.queue_na.put(event_q_dict)
        # print(hostname + ' completed')

    def __init__(
        self,
        hostname,
        queue_na,
        username,
        password,
        ignore_vols,
        ignore_snapshots,
        ignore_events,
        ignore_sm,
        ignore_vol_snapshots,
    ):
        threading.Thread.__init__(self)
        self.hostname = hostname
        self.queue_na = queue_na
        self.username = username
        self.password = password
        self.ignore_vols = ignore_vols
        self.ignore_snapshots = ignore_snapshots
        self.ignore_events = ignore_events
        self.ignore_sm = ignore_sm
        self.ignore_vol_snapshots = ignore_vol_snapshots


def desired_attr_defaults(info_type):
    if info_type == "svm":
        nae_desired = NaElement("desired-attributes")
        nae_svm_info = NaElement("vserver-info")

        nae_svm_protocols = NaElement("allowed-protocols")
        nae_svm_protocols.child_add_string("protocol", "")
        nae_svm_info.child_add(nae_svm_protocols)

        nae_svm_info.child_add_string("language", "")
        nae_svm_info.child_add_string("operational-state", "")
        nae_svm_info.child_add_string("root-volume-security-style", "")
        nae_svm_info.child_add_string("state", "")
        nae_svm_info.child_add_string("uuid", "")
        nae_svm_info.child_add_string("vserver-name", "")
        nae_svm_info.child_add_string("vserver-subtype", "")
        nae_svm_info.child_add_string("vserver-type", "")

        nae_desired.child_add(nae_svm_info)
        return nae_desired

    elif info_type == "aggregate":
        nae_desired = NaElement("desired-attributes")
        nae_aggr_attributes = NaElement("aggr-attributes")

        nae_aggr_space_attributes = NaElement("aggr-space-attributes")

        nae_aggr_space_attributes.child_add_string("hybrid-cache-size-total", "")
        nae_aggr_space_attributes.child_add_string("percent-used-capacity", "")
        nae_aggr_space_attributes.child_add_string("physical-used", "")
        nae_aggr_space_attributes.child_add_string("physical-used-percent", "")
        nae_aggr_space_attributes.child_add_string("size-available", "")
        nae_aggr_space_attributes.child_add_string("size-total", "")
        nae_aggr_space_attributes.child_add_string("size-used", "")
        nae_aggr_space_attributes.child_add_string("total-reserved-space", "")

        nae_aggr_attributes.child_add(nae_aggr_space_attributes)
        nae_aggr_attributes.child_add_string("aggregate-name", "")

        nae_desired.child_add(nae_aggr_attributes)

        return nae_desired

    elif info_type == "volume":
        nae_desired = NaElement("desired-attributes")
        nae_volume_attributes = NaElement("volume-attributes")

        # Create sub-elements
        nae_volume_autosize_attributes = NaElement("volume-autosize-attributes")
        nae_volume_id_attributes = NaElement("volume-id-attributes")
        nae_volume_inode_attributes = NaElement("volume-inode-attributes")
        nae_volume_snapshot_attributes = NaElement("volume-snapshot-attributes")
        nae_volume_space_attributes = NaElement("volume-space-attributes")
        nae_volume_state_attributes = NaElement("volume-state-attributes")

        # Add all specs to sub-elements
        nae_volume_autosize_attributes.child_add_string("grow-threshold-percent", "")
        nae_volume_autosize_attributes.child_add_string("increment-size", "")
        nae_volume_autosize_attributes.child_add_string(
            "is-enabled", ""
        )  # true or false
        nae_volume_autosize_attributes.child_add_string("maximum-size", "")
        nae_volume_autosize_attributes.child_add_string(
            "mode", ""
        )  # grow_shrink, grow, etc.
        nae_volume_autosize_attributes.child_add_string("shrink-threshold-percent", "")
        nae_volume_autosize_attributes.child_add_string("increment-size", "")

        nae_volume_id_attributes.child_add_string("containing-aggregate-name", "")
        nae_volume_id_attributes.child_add_string("name", "")
        nae_volume_id_attributes.child_add_string("owning-vserver-name", "")
        nae_volume_id_attributes.child_add_string("type", "")

        nae_volume_inode_attributes.child_add_string("files-private-used", "")
        nae_volume_inode_attributes.child_add_string("files-total", "")
        nae_volume_inode_attributes.child_add_string("files-used", "")
        nae_volume_inode_attributes.child_add_string("inodefile-private-capacity", "")
        nae_volume_inode_attributes.child_add_string("inodefile-public-capacity", "")

        nae_volume_snapshot_attributes.child_add_string("snapshot-count", "")
        nae_volume_snapshot_attributes.child_add_string("snapshot-policy", "")

        nae_volume_space_attributes.child_add_string(
            "percentage-size-used", ""
        )  # (Includes snapshot space used) Effective size used (to end user)
        nae_volume_space_attributes.child_add_string("percentage-snapshot-reserve", "")
        nae_volume_space_attributes.child_add_string(
            "percentage-snapshot-reserve-used", ""
        )
        nae_volume_space_attributes.child_add_string("physical-used", "")
        nae_volume_space_attributes.child_add_string(
            "physical-used-percent", ""
        )  # (Includes snapshot space used) Size actually used (accounting for compression/dedupe savings)
        nae_volume_space_attributes.child_add_string(
            "size", ""
        )  # User and SS size combined
        nae_volume_space_attributes.child_add_string("size-available", "")
        nae_volume_space_attributes.child_add_string("size-available-for-snapshots", "")
        nae_volume_space_attributes.child_add_string(
            "size-total", ""
        )  # Size avail to user
        nae_volume_space_attributes.child_add_string("size-used", "")
        nae_volume_space_attributes.child_add_string("size-used-by-snapshots", "")
        nae_volume_space_attributes.child_add_string("snapshot-reserve-size", "")
        nae_volume_state_attributes.child_add_string("is-node-root", "")
        nae_volume_state_attributes.child_add_string("is-vserver-root", "")
        nae_volume_state_attributes.child_add_string("state", "")

        # Attach all sub-elements
        nae_volume_attributes.child_add(nae_volume_autosize_attributes)
        nae_volume_attributes.child_add(nae_volume_id_attributes)
        nae_volume_attributes.child_add(nae_volume_inode_attributes)
        nae_volume_attributes.child_add(nae_volume_snapshot_attributes)
        nae_volume_attributes.child_add(nae_volume_space_attributes)
        nae_volume_attributes.child_add(nae_volume_state_attributes)

        nae_desired.child_add(nae_volume_attributes)
        return nae_desired

    elif info_type == "snapmirror":
        nae_desired = NaElement("desired-attributes")
        nae_snapmirror_info = NaElement("snapmirror-info")

        nae_snapmirror_info.child_add_string("destination-location", "")
        nae_snapmirror_info.child_add_string("destination-volume", "")
        nae_snapmirror_info.child_add_string("destination-vserver", "")
        nae_snapmirror_info.child_add_string("is-healthy", "")
        nae_snapmirror_info.child_add_string("lag-time", "")
        nae_snapmirror_info.child_add_string("mirror-state", "")
        nae_snapmirror_info.child_add_string("unhealthy-reason", "")
        nae_snapmirror_info.child_add_string("source-location", "")
        nae_snapmirror_info.child_add_string("identity-preserve", "")

        nae_desired.child_add(nae_snapmirror_info)
        return nae_desired

    elif info_type == "snapshot":
        nae_desired = NaElement("desired-attributes")

        nae_snapshot_info = NaElement("snapshot-info")

        nae_snapshot_info.child_add_string("access-time", "")
        nae_snapshot_info.child_add_string("name", "")
        nae_snapshot_info.child_add_string("volume", "")
        nae_snapshot_info.child_add_string("vserver", "")

        nae_desired.child_add(nae_snapshot_info)
        return nae_desired

    elif info_type == "lif":
        nae_desired = NaElement("desired-attributes")
        nae_lif_info = NaElement("net-interface-info")

        nae_lif_protocols = NaElement("data-protocols")
        nae_lif_protocols.child_add_string("data-protocol", "")

        nae_lif_info.child_add(nae_lif_protocols)
        nae_lif_info.child_add_string("address", "")
        nae_lif_info.child_add_string("administrative-status", "")
        nae_lif_info.child_add_string("current-node", "")
        nae_lif_info.child_add_string("current-port", "")
        nae_lif_info.child_add_string("home-node", "")
        nae_lif_info.child_add_string("home-port", "")
        nae_lif_info.child_add_string("interface-name", "")
        nae_lif_info.child_add_string("is-home", "")
        nae_lif_info.child_add_string("operational-status", "")
        nae_lif_info.child_add_string("role", "")
        nae_lif_info.child_add_string("vserver", "")

        nae_desired.child_add(nae_lif_info)
        return nae_desired

    elif info_type == "disk":
        nae_desired = NaElement("desired-attributes")
        nae_storage_disk_info = NaElement("storage-disk-info")

        # Create sub-elements
        nae_disk_inventory_info = NaElement("disk-inventory-info")
        nae_disk_ownership_info = NaElement("disk-ownership-info")
        nae_disk_raid_info = NaElement("disk-raid-info")
        nae_disk_spare_info = NaElement("disk-spare-info")

        # Add all specs to sub-elements
        nae_disk_inventory_info.child_add_string("disk-type", "")
        nae_disk_inventory_info.child_add_string("serial-number", "")

        nae_disk_ownership_info.child_add_string("is-failed", "")
        nae_disk_ownership_info.child_add_string("owner-node-name", "")

        nae_disk_raid_info.child_add_string("container-type", "")
        nae_disk_spare_info.child_add_string("is-zeroed", "")
        nae_disk_raid_info.child_add(nae_disk_spare_info)

        # Attach all sub-elements
        nae_storage_disk_info.child_add(nae_disk_inventory_info)
        nae_storage_disk_info.child_add(nae_disk_ownership_info)
        nae_storage_disk_info.child_add(nae_disk_raid_info)
        nae_storage_disk_info.child_add_string("disk-name", "")

        nae_desired.child_add(nae_storage_disk_info)
        return nae_desired

    elif info_type == "event":
        nae_desired = NaElement("desired-attributes")
        nae_event_info = NaElement("ems-message-info")

        nae_event_info.child_add_string("event", "")
        nae_event_info.child_add_string("message-name", "")
        nae_event_info.child_add_string("node", "")
        nae_event_info.child_add_string("severity", "")
        nae_event_info.child_add_string("time", "")

        nae_event_parameters = NaElement("parameters")
        nae_event_parameters_parameter = NaElement("parameter")
        nae_event_parameters_parameter.child_add_string("name", "")
        nae_event_parameters_parameter.child_add_string("value", "")
        nae_event_parameters.child_add(nae_event_parameters_parameter)
        nae_event_info.child_add(nae_event_parameters)

        nae_desired.child_add(nae_event_info)
        return nae_desired


def build_query_element(info_type):
    if info_type == "volume-info":
        nae_query = NaElement("query")

        nae_volume_attributes = NaElement(info_type)

        nae_volume_id_attributes = NaElement("volume-id-attributes")
        nae_volume_state_attributes = NaElement("volume-state-attributes")

        nae_volume_id_attributes.child_add_string("type", "rw")  # RW volumes only

        nae_volume_state_attributes.child_add_string(
            "is-vserver-root", "false"
        )  # Remove LS mirror and root volumes
        # nae_volume_state_attributes.child_add_string('state', 'online') # Online volumes only

        nae_volume_attributes.child_add(nae_volume_id_attributes)
        nae_volume_attributes.child_add(nae_volume_state_attributes)

        nae_query.child_add(nae_volume_attributes)
        return nae_query

    elif info_type == "snapmirror-info":
        nae_query = NaElement("query")
        nae_snapmirror_info = NaElement("snapmirror-info")
        nae_snapmirror_info.child_add_string(
            "relationship-type", "data_protection"
        )  # Remove LS mirror relationships
        nae_query.child_add(nae_snapmirror_info)
        return nae_query


def build_html_table(tablename, headings, data):
    table_string = "<p>" + tablename + "</p>"

    # Build heading column
    heading_text = '\n<table id="{{ tablename }}">\n  <tr bgcolor="#AAAAAA">{% for col in headings %}\n    <th>{{ col }}</th>{% endfor %}'
    heading_template = Template(heading_text)
    table_string += heading_template.render(headings=headings, tablename=tablename)
    table_string += "\n  </tr>"

    # Build data rows
    template_text = "{% for row in table %}\n  <tr{{ loop.cycle(' bgcolor=\"#F2F2F2\"', '') }}>\n  {% for col in row %}    <td{% if col[1] is defined %}{{ ' class=\"' + col[1] + '\"' }}{% endif %}>{{ col[0] }}</td>\n  {% endfor %}</tr>{% endfor %}"
    table_template = Template(template_text)
    table_string += table_template.render(table=data)

    table_string += "\n</table>"
    table_string += "\n<p></p>"

    return table_string


def bytes_to_x(conv_to, val):
    # Converts values returned in Bytes by API to KB, MB, GB, or TB and returns it as an int (g and under) or float (terabytes)
    choice = conv_to.lower()
    if choice == "k":
        return int(round((val / 1024), 0))  # Returns whole number
    elif choice == "m":
        return int(round((val / 1024 ** 2), 0))  # Returns whole number
    elif choice == "g":
        return round((val / 1024 ** 3), 1)  # Returns to tenths place
    elif choice == "t":
        return round((val / 1024 ** 4), 1)  # Rounds to tenths places
    else:
        raise Exception("Cannot convert to user-specified value: " + conv_to)


def color_code_cluster(cluster_string):
    if cluster_string == "dc1-ntap-c1":
        return "darkblue"
    elif cluster_string == "dc1-ntap-c2" or cluster_string == "dc1-ntap-c3":
        return "green"
    elif cluster_string == "dc2-ntap-c2" or cluster_string == "dc2-ntap-c3":
        return "darkorange"
    elif cluster_string == "dc3-ntap-c1":
        return "red"
    elif cluster_string == "dc4-ntap-c1":
        return "cornflowerblue"
    elif cluster_string == "dc5-ntap-c1":
        return "fuchsia"
    else:
        return "Error coloring-coding cluster."


def main():
    os.chdir(
        os.path.dirname(os.path.realpath(__file__))
    )  # change to dir that contains the script

    parser = configparser.RawConfigParser()
    parser.read("config.py")

    USERNAME = parser.get("login_info", "USERNAME")
    PASSWORD = parser.get("login_info", "PASSWORD")

    # Open cluster & array lists
    with open("/usr/local/bin/controllers/cDOT") as f:
        hosts_netapp_sorted = f.read().splitlines()

    with open("/usr/local/bin/controllers/3par") as f:
        hosts_3par_sorted = f.read().splitlines()

    # Misc. Information
    with open("ignoreTheseVolumes") as f:
        ignoreTheseVols = f.read().splitlines()

    with open("ignoreTheseSnapshots") as f:
        ignoreTheseSnapshots = f.read().splitlines()

    with open("ignoreTheseEvents") as f:
        ignoreTheseEvents = f.read().splitlines()

    with open("ignoreTheseSnapmirrorDestinations") as f:
        ignoreTheseSnapmirrorDestinations = f.read().splitlines()

    with open("ignoreTheseVolumeSnapshots") as f:
        ignoreTheseVolumeSnapshots = f.read().splitlines()

    q_netapp = queue.Queue()
    q_3par = queue.Queue()

    host_timeouts = []
    threads = []

    for hostname in hosts_netapp_sorted:
        s = socket.socket()
        s.settimeout(3)
        # Test SSL connection before opening thread. Must have DNS configured on the server for this to work using hostnames.
        try:
            s.connect((hostname, 443))
        except timeout:
            host_timeouts.append(hostname)
            print(
                "Unexpected error - could not connect to :"
                + hostname
                + str(sys.exc_info()[0])
            )
            continue
        finally:
            s.close()

        # print('Starting thread ' + hostname)
        current_thread = ThreadNA(
            hostname,
            q_netapp,
            USERNAME,
            PASSWORD,
            ignoreTheseVols,
            ignoreTheseSnapshots,
            ignoreTheseEvents,
            ignoreTheseSnapmirrorDestinations,
            ignoreTheseVolumeSnapshots,
        )
        threads.append(current_thread)
        current_thread.start()

    for hostname in hosts_3par_sorted:
        s = socket.socket()
        s.settimeout(3)
        # Test port 8080 connection before opening thread. Must have DNS configured on the server for this to work using hostnames.
        try:
            s.connect((hostname, 8080))
        except timeout:
            host_timeouts.append(hostname)
            print(
                "Unexpected error - could not connect to :"
                + hostname
                + str(sys.exc_info()[0])
            )
            continue
        finally:
            s.close()

        current_thread = ThreadTP(hostname, q_3par, USERNAME, PASSWORD)
        threads.append(current_thread)
        current_thread.start()

    for t in threads:
        t.join()

    output_table_list = []

    #######################
    # Process NetApp Data #
    #######################

    # Create lists for each data type, to sort by priority
    vol_data = []
    sm_data = []
    ss_data = []
    lif_data = []
    disk_data = []
    event_data = []
    cron_data = dict()

    # Move netapp queue objects to lists
    for i in range(0, q_netapp.qsize()):
        item = q_netapp.get()
        if item["datatype"] == "volume":
            vol_data.append(item)
        if item["datatype"] == "snapmirror":
            sm_data.append(item)
        if item["datatype"] == "snapshot":
            ss_data.append(item)
        if item["datatype"] == "lif":
            lif_data.append(item)
        if item["datatype"] == "disk":
            disk_data.append(item)
        if item["datatype"] == "event":
            event_data.append(item)
        if item["datatype"] == "cron":
            cron_data[item["cluster"]] = item["data"]

    # Create a dictionary for sorting output
    order_netapp = {key: i for i, key in enumerate(hosts_netapp_sorted)}

    # Sort data lists by cluster priority
    vol_data = sorted(vol_data, key=lambda d: order_netapp[d["cluster"]])
    sm_data = sorted(sm_data, key=lambda d: order_netapp[d["cluster"]])
    ss_data = sorted(ss_data, key=lambda d: order_netapp[d["cluster"]])
    lif_data = sorted(lif_data, key=lambda d: order_netapp[d["cluster"]])
    disk_data = sorted(disk_data, key=lambda d: order_netapp[d["cluster"]])
    event_data = sorted(event_data, key=lambda d: order_netapp[d["cluster"]])

    ###########
    # Volumes #
    ###########

    column_titles = [
        "Cluster",
        "SVM",
        "Volume",
        "Size",
        "New Size",
        "Used",
        "% Used",
        "% Snap",
        "New % Snap",
        "% Snap Used",
        "Aggregate",
        "Aggr Avail",
        "Files Total",
        "% Files Used",
        "Notes",
    ]
    vol_output = []
    check_fix_output = []

    for item in vol_data:
        if len(item["data"]) > 0:
            for vol in item["data"]:
                check = []

                # Move check/fix commands to new list, remove from original list, add in cluster
                check.append(vol[0])  # Populate cluster name
                check.append(vol[-2])  # Move check command
                check.append(vol[-1])  # Move fix command
                del vol[-2]
                del vol[-1]

                # Build vol data table
                vol_output.append(vol)
                check_fix_output.append(check)

    volume_table = build_html_table("Volumes", column_titles, vol_output)

    ############
    # Fix Vols #
    ############

    column_titles = ["Cluster", "Check", "Fix"]
    fix_vol_table = build_html_table(
        "Check & Fix Volumes", column_titles, check_fix_output
    )

    ##################
    # Cron schedules #
    ##################

    # cron_dict = {'datatype': 'cron',
    #              'cluster': hostname,
    #              'data': []}

    # if item['datatype'] == 'cron':
    #     cron_data[item['cluster']] = item['data']

    column_titles = ["Cluster", "Missing Cron Schedule"]
    cron_output = []

    # Build list of all NetApp cluster cron jobs
    us_dr_clusters = ["dc1-ntap-c2", "dc2-ntap-c2"]
    us_cron_list = []
    us_cron_output = []
    can_dr_clusters = ["dc4-ntap-c1", "dc5-ntap-c1"]
    can_cron_list = []
    can_cron_output = []

    # Create lists of cron schedules for U.S. and Canada
    for cluster in cron_data.keys():
        if cluster in us_dr_clusters:
            us_cron_list.extend(x for x in cron_data[cluster] if x not in us_cron_list)
        if cluster in can_dr_clusters:
            can_cron_list.extend(
                x for x in cron_data[cluster] if x not in can_cron_list
            )

    for cluster in cron_data.keys():
        # Find U.S. missing schedules
        if cluster in us_dr_clusters:
            missing_us_schedules = [
                x for x in us_cron_list if x not in cron_data[cluster]
            ]

            for sched in missing_us_schedules:
                us_cron_output.append(
                    [[cluster, color_code_cluster(cluster)], [sched, "red_b"]]
                )

        # Find Canada missing schedules
        if cluster in can_dr_clusters:
            missing_can_schedules = [
                x for x in can_cron_list if x not in cron_data[cluster]
            ]

            for sched in missing_can_schedules:
                can_cron_output.append(
                    [[cluster, color_code_cluster(cluster)], [sched, "red_b"]]
                )

    cron_output = us_cron_output + can_cron_output

    cron_table = build_html_table("Cron Schedules", column_titles, cron_output)

    ###############
    # SnapMirrors #
    ###############

    column_titles = [
        "Cluster",
        "Destination",
        "State",
        "Lag-Time (Hrs)",
        "Healthy",
        "Unhealthy Reason",
    ]
    sm_output = []

    for item in sm_data:
        if len(item["data"]) > 0:
            for sm in item["data"]:
                sm_output.append(sm)

    snapmirror_table = build_html_table("SnapMirrors", column_titles, sm_output)

    #############
    # Snapshots #
    #############

    column_titles = ["Cluster", "SVM", "Volume", "Snapshot", "Age", "Delete?"]
    ss_output = []

    for item in ss_data:
        if len(item["data"]) > 0:
            for ss in item["data"]:
                ss_output.append(ss)

    snapshot_table = build_html_table("Snapshots", column_titles, ss_output)

    ########
    # LIFs #
    ########

    column_titles = [
        "Cluster",
        "SVM",
        "LIF",
        "Role",
        "Adm. Status",
        "Op. Status",
        "Is Home",
    ]
    lif_output = []

    for item in lif_data:
        if len(item["data"]) > 0:
            for lif in item["data"]:
                lif_output.append(lif)

    lif_table = build_html_table("LIFs", column_titles, lif_output)

    #########
    # Disks #
    #########

    column_titles = [
        "Cluster",
        "Node",
        "Disk",
        "Serial",
        "Container Type",
        "Failed",
        "Zeroed",
    ]
    disk_output = []

    for item in disk_data:
        if len(item["data"]) > 0:
            for disk in item["data"]:
                disk_output.append(disk)

    disk_table = build_html_table("Disks", column_titles, disk_output)

    ##########
    # Events #
    ##########

    column_titles = ["Cluster", "Node", "Severity", "Time", "Message"]
    event_output = []

    for item in event_data:
        if len(item["data"]) > 0:
            for event in item["data"]:
                event_output.append(event)

    event_table = build_html_table("Events", column_titles, event_output)

    #####################
    # Process 3PAR Data #
    #####################

    rcopy_data = []

    # Move netapp queue objects to new queues
    for i in range(0, q_3par.qsize()):
        item = q_3par.get()
        if item["datatype"] == "rcopy":
            rcopy_data.append(item)

    order_3par = {key: i for i, key in enumerate(hosts_3par_sorted)}

    rcopy_data = sorted(rcopy_data, key=lambda d: order_3par[d["array"]])

    #########
    # RCopy #
    #########

    column_titles = ["Array", "Group", "Role", "State"]
    rcopy_output = []

    for item in rcopy_data:
        if len(item["data"]) > 0:
            for group in item["data"]:
                rcopy_output.append(group)

    rcopy_table = build_html_table("RCopy Groups", column_titles, rcopy_output)

    output_table_list.append(volume_table)
    output_table_list.append(fix_vol_table)
    output_table_list.append(cron_table)
    output_table_list.append(snapmirror_table)
    output_table_list.append(snapshot_table)
    output_table_list.append(lif_table)
    output_table_list.append(disk_table)
    output_table_list.append(rcopy_table)  # 3PAR RCopy listing before NetApp event logs
    output_table_list.append(event_table)

    #####################
    # Write Output File #
    #####################

    with open("mailout.html", "w") as text_file:
        print(
            '<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Strict//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-strict.dtd">',
            file=text_file,
        )
        print("<head>", file=text_file)
        print(
            '<meta http-equiv="Content-Type" content="text/html; charset=utf-8">',
            file=text_file,
        )
        print(
            '<meta name="viewport" content="width=device-width, initial-scale=1.0">',
            file=text_file,
        )
        print("<title></title>", file=text_file)
        print("<style>", file=text_file)
        print("  table {", file=text_file)
        print("    border:solid 1px #ddd;", file=text_file)
        print("    padding: 1px 4px 1px 4px;", file=text_file)
        print("    font-size: 14px;", file=text_file)
        print("    font-family: Tahoma;", file=text_file)
        print("    border-collapse: collapse;", file=text_file)
        print("    width: 600px", file=text_file)
        print("  }", file=text_file)
        print("  td {", file=text_file)
        print("    border:solid 1px #ddd;", file=text_file)
        print("    padding: 1px 4px 1px 4px;", file=text_file)
        print("    font-size: 14px;", file=text_file)
        print("    white-space: nowrap;}", file=text_file)
        print("  th {", file=text_file)
        print("    border:solid 1px #ddd;", file=text_file)
        print("    padding: 1px 4px 1px 4px;", file=text_file)
        print("    text-align: left;", file=text_file)
        print("    font-size: 14px;", file=text_file)
        print("    font-weight:bold;", file=text_file)
        print("    white-space: nowrap;", file=text_file)
        print("  }", file=text_file)
        print("  p {", file=text_file)
        print("    background: white; color: black;", file=text_file)
        print("    font-style: normal;", file=text_file)
        print("    font-weight: bold;", file=text_file)
        print("    font-size: 25px;", file=text_file)
        print("    line-height: 0px", file=text_file)
        print("  }", file=text_file)
        print("", file=text_file)
        print("  .darkblue {color:darkblue;}", file=text_file)
        print("  .green {color:green;}", file=text_file)
        print("  .green_r {color:green;text-align:right;}", file=text_file)
        print("  .darkorange {color:darkorange;}", file=text_file)
        print("  .red {color:red;}", file=text_file)
        print("  .red_b {color:red;font-weight:bold}", file=text_file)
        print(
            "  .red_b_r {color:red;font-weight:bold;text-align:right;}", file=text_file
        )
        print("  .cornflowerblue {color:cornflowerblue;}", file=text_file)
        print("  .fuchsia {color:fuchsia;}", file=text_file)
        print("  .gold {color:gold;}", file=text_file)
        print("  .seagreen {color:seagreen;}", file=text_file)
        print("  .royalblue {color:royalblue;}", file=text_file)
        print("  .darkslateblue {color:darkslateblue;}", file=text_file)
        print("  .mediumvioletred {color:mediumvioletred;}", file=text_file)
        print("  .black {color:black;}", file=text_file)
        print("  .black_b {color:black;font-weight:bold}", file=text_file)
        print("  .black_c {color:black;text-align:center;}", file=text_file)
        print(
            "  .black_b_c {color:black;font-weight:bold;text-align:center;}",
            file=text_file,
        )
        print("  .black_r {color:black;text-align:right;}", file=text_file)
        print("  .orangered {color:orangered;}", file=text_file)
        print("  .orangered_b {color:orangered;font-weight:bold}", file=text_file)
        print(
            "  .orangered_b_r {color:orangered;font-weight:bold;text-align:right;}",
            file=text_file,
        )
        print("  .coral {color:coral;}", file=text_file)
        print("  .coral_b {color:coral;font-weight:bold}", file=text_file)
        print("  .goldenrod {color:goldenrod;}", file=text_file)
        print("  .goldenrod_b {color:goldenrod;font-weight:bold}", file=text_file)
        print("</style>", file=text_file)
        print("</head>", file=text_file)
        print("<body>", file=text_file)

        ##############################
        # Failed Connection Warnings #
        ##############################
        if host_timeouts:
            for hostname in host_timeouts:
                print(
                    '<p class="orangered_b">WARNING: Failed to connect to '
                    + hostname
                    + "</p>",
                    file=text_file,
                )

        ############################
        # Table printing goes here #
        ############################
        for table in output_table_list:
            print(table, file=text_file)
            print("<p></p>", file=text_file)

        print("</body>", file=text_file)

    ##############
    # Send Email #
    ##############

    RECIPIENTS = ["storage@mitchell.com"]
    # RECIPIENTS = ['alex.hempy@mitchell.com']

    FROM_ADDR = "storagesvc@mitchell.com"

    # Create message container - the correct MIME type is multipart/alternative.
    msg = MIMEMultipart("alternative")
    msg["Subject"] = "Mitchell Storage Dashboard"
    msg["From"] = FROM_ADDR
    msg["To"] = ", ".join(RECIPIENTS)

    with open("mailout.html", "r") as input_file:
        body = input_file.read()

    msg.attach(MIMEText(body, "html"))

    s = smtplib.SMTP("mail.mitchell.com")
    s.sendmail(FROM_ADDR, RECIPIENTS, msg.as_string())
    s.quit()

    ###############################
    # Processing Output Ends Here #
    ###############################


if __name__ == "__main__":
    main()
