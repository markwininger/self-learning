#!/usr/bin/env python3

try:
    import json
    import logging
    import os
    import smtplib
    import sys
    from email.message import EmailMessage

    import pandas

except ImportError:
    print(f"{sys.exc_info()}")


def do_email():
    """
    It creates a HTML email with tables.
    """
    # with open("generalConfig.json", "r") as generalConfig:
    #     general_config = json.load(generalConfig)

    # general_config["send_mail"]["preferred_server"]
    email_title = os.environ["emailTitle"]
    table_names = os.environ["tableNames"]
    table_names = table_names.split(",")
    table_name = list(table_names)

    table_list = []
    infile = os.environ["csvFiles"]
    infile = infile.split(",")
    for file in infile:
        table = pandas.read_csv(file, index_col=False, sep=",", engine="python")
        table = table.to_dict()
        print(table)
        table_list.append(table)

    html_body = """\
        <br />
        <Center>
            <h2>{0}</h2>
        </center>
        <br />
    """.format(
        email_title
    )

    for i in range(len(table_name)):
        table = pandas.DataFrame.from_dict(table_list[i])
        table = table.to_html(index=False)
        html_body += """\
            <h3>
                {0}
            </h3>
            <br />
            <table>
                <tr>
                    <td class="table2-1" colspan="6">{1}</td>
                </tr>
            </table>
            <br />
            """.format(
            table_names[i], table
        )

    html_head = """\
    <style>
        body {
            font-family: "Courier New";
            font-size: 8pt;
            line-height: 5px;
        }

        table,
        th,
        td {
            white-space: nowrap;
            border: 1px solid #25724F;
            text-align: center;
            border-collapse: collapse;
            padding: 5px;
        }

        th {
            background-color: #3CC139;
            color: white;
        }

        tab5 {
            font-weight: bold;
            font-size: 10pt;
        }

        h1 {
            display: block;
            font-size: 11pt;
            margin-top: 0.67em;
            margin-bottom: 0.67em;
            margin-left: 0;
            margin-right: 0;
            font-weight: bold;
            padding-right: 20px;
            text-decoration: underline;
        }

        h2 {
            display: block;
            font-size: 10pt;
            margin-top: 0.67em;
            margin-bottom: 0.67em;
            margin-left: 0;
            margin-right: 0;
            font-weight: bold;
            text-decoration: underline;
        }

        h3 {
            display: block;
            font-size: 9pt;
            margin-top: 0.67em;
            margin-bottom: 0.67em;
            margin-left: 0;
            margin-right: 0;
            font-weight: bold;
            padding-right: 20px;
        }

        tab {
            display: inline-block;
            margin-left: 40px;
        }
    </style>
    """

    msg = EmailMessage()
    msg.set_content(
        """\
        <html>
            <head>
                {0}
            </head>
            <body>
                {1}
            </body>
        </html>
        """.format(
            html_head, html_body
        ),
        subtype="html",
    )
    msg["Subject"] = os.environ["subject"]
    msg["From"] = os.environ["sender"]
    msg["To"] = os.environ["recipient"]
    # msg["From"] = "script.test@enlyte.com"
    # msg["To"] = "mark.wininger@enlyte.com"

    # s = smtplib.SMTP(general_config["send_mail"]["preferred_server"])
    try:
        s = smtplib.SMTP()
        s.connect("localhost")
        s.send_message(msg)
        s.quit()
    except SMTPException:
        print("Error: unable to send email")
